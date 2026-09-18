from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import calculate_ssq_trends, calculate_trends, load_dlt_history, load_ssq_history  # noqa: E402
from research_v2 import bootstrap_mean_ci, history_through_issue  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402


BLOCKS = (
    ("development", 0),
    ("v1_consumed_holdout", 50),
    ("v21_fresh_holdout", 100),
)


def score_auc(score_rows: list[dict], winners: list[int], pool_size: int) -> float:
    """Probability that a winning number outranks a non-winning number.

    0.5 is random ordering. Ties contribute 0.5. This evaluates the scorer
    directly and does not depend on any ticket generator or budget.
    """
    score_by_number = {int(row["number"]): float(row.get("total_score", 0.0)) for row in score_rows}
    winner_set = set(int(number) for number in winners)
    losers = [number for number in range(1, pool_size + 1) if number not in winner_set]
    if not winner_set or not losers:
        return 0.5

    wins = 0.0
    comparisons = 0
    for winner in winner_set:
        winner_score = score_by_number.get(winner, 0.0)
        for loser in losers:
            loser_score = score_by_number.get(loser, 0.0)
            comparisons += 1
            if winner_score > loser_score:
                wins += 1.0
            elif winner_score == loser_score:
                wins += 0.5
    return wins / comparisons if comparisons else 0.5


def top_fraction_hit_delta(
    score_rows: list[dict],
    winners: list[int],
    pool_size: int,
    fraction: float = 0.25,
) -> float:
    """Winner share in the score-table top fraction minus random expectation."""
    top_count = max(1, math.ceil(pool_size * fraction))
    ranked = sorted(
        ((int(row["number"]), float(row.get("total_score", 0.0))) for row in score_rows),
        key=lambda item: (-item[1], item[0]),
    )
    top_numbers = {number for number, _ in ranked[:top_count]}
    winner_set = set(int(number) for number in winners)
    observed = len(winner_set & top_numbers) / max(1, len(winner_set))
    expected = top_count / pool_size
    return observed - expected


def ci(values: list[float], seed: str) -> dict:
    result = bootstrap_mean_ci(values, seed=seed)
    return {
        "mean": round(float(result["mean"]), 4),
        "ci95_low": round(float(result["low"]), 4),
        "ci95_high": round(float(result["high"]), 4),
    }


def audit_block(
    *,
    game: str,
    full_history: list[dict],
    excluded_recent_points: int,
    periods: int,
    window: int,
) -> dict:
    if excluded_recent_points:
        history = full_history[:-excluded_recent_points]
    else:
        history = full_history
    if len(history) < periods + 31:
        raise ValueError("not enough history for scorer audit block")

    if game == "DLT":
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        front_pool = 35
        back_pool = 12
    else:
        trend_builder = calculate_ssq_trends
        front_scorer = score_ssq_front_numbers
        back_scorer = score_ssq_back_numbers
        front_pool = 33
        back_pool = 16

    end_source = len(history) - 2
    start_source = end_source - periods + 1
    front_auc_advantages: list[float] = []
    back_auc_advantages: list[float] = []
    front_top_quartile_deltas: list[float] = []
    back_top_quartile_deltas: list[float] = []
    outcome_issues: list[str] = []

    for index in range(start_source, end_source + 1):
        source_issue = str(history[index]["issue"])
        actual = history[index + 1]
        training = history_through_issue(history, source_issue)
        trends = trend_builder(training, window=min(window, len(training)))
        front_scores = front_scorer(trends)
        back_scores = back_scorer(trends)

        front_auc_advantages.append(score_auc(front_scores, actual["front"], front_pool) - 0.5)
        back_auc_advantages.append(score_auc(back_scores, actual["back"], back_pool) - 0.5)
        front_top_quartile_deltas.append(
            top_fraction_hit_delta(front_scores, actual["front"], front_pool)
        )
        back_top_quartile_deltas.append(
            top_fraction_hit_delta(back_scores, actual["back"], back_pool)
        )
        outcome_issues.append(str(actual["issue"]))

    block_name = next(name for name, excluded in BLOCKS if excluded == excluded_recent_points)
    return {
        "game": game,
        "block": block_name,
        "excluded_recent_points": excluded_recent_points,
        "window": window,
        "periods": len(outcome_issues),
        "first_outcome_issue": outcome_issues[0],
        "last_outcome_issue": outcome_issues[-1],
        "metrics": {
            "front_auc_advantage_over_random": ci(
                front_auc_advantages, f"{game}-{block_name}-{window}-front-auc"
            ),
            "back_auc_advantage_over_random": ci(
                back_auc_advantages, f"{game}-{block_name}-{window}-back-auc"
            ),
            "front_top_quartile_hit_rate_delta": ci(
                front_top_quartile_deltas, f"{game}-{block_name}-{window}-front-topq"
            ),
            "back_top_quartile_hit_rate_delta": ci(
                back_top_quartile_deltas, f"{game}-{block_name}-{window}-back-topq"
            ),
        },
    }


def diagnosis(rows: list[dict], game: str) -> dict:
    game_rows = [row for row in rows if row["game"] == game]
    fresh = [row for row in game_rows if row["block"] == "v21_fresh_holdout"]
    front_positive = sum(
        row["metrics"]["front_auc_advantage_over_random"]["ci95_low"] > 0
        for row in fresh
    )
    front_negative = sum(
        row["metrics"]["front_auc_advantage_over_random"]["ci95_high"] < 0
        for row in fresh
    )
    back_positive = sum(
        row["metrics"]["back_auc_advantage_over_random"]["ci95_low"] > 0
        for row in fresh
    )
    back_negative = sum(
        row["metrics"]["back_auc_advantage_over_random"]["ci95_high"] < 0
        for row in fresh
    )

    if front_positive >= 2 and back_positive >= 2:
        status = "BOTH_SCORERS_SHOW_SIGNAL"
    elif front_positive >= 2 and back_positive < 2:
        status = "FRONT_SIGNAL_BACK_WEAK"
    elif back_positive >= 2 and front_positive < 2:
        status = "BACK_SIGNAL_FRONT_WEAK"
    elif front_negative >= 2 or back_negative >= 2:
        status = "SCORER_ANTI_SIGNAL_RISK"
    else:
        status = "NO_STABLE_SCORER_SIGNAL"

    return {
        "status": status,
        "fresh_holdout_front_significant_positive_windows": front_positive,
        "fresh_holdout_front_significant_negative_windows": front_negative,
        "fresh_holdout_back_significant_positive_windows": back_positive,
        "fresh_holdout_back_significant_negative_windows": back_negative,
        "note": (
            "AUC is generator-independent: 0.5 is random ordering. The report stores AUC-0.5, "
            "so positive values mean winning numbers tended to rank above non-winning numbers. "
            "Correlated windows are diagnostic evidence, not independent hypothesis tests."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CEWAY scorer signal independently of ticket generation")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v2_scorer_signal_audit.json",
    )
    args = parser.parse_args()

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows: list[dict] = []
    for game in ("DLT", "SSQ"):
        for block_name, excluded in BLOCKS:
            for window in windows:
                print(
                    f"SCORER AUDIT {game}: block={block_name}, window={window}, periods={args.periods}",
                    flush=True,
                )
                row = audit_block(
                    game=game,
                    full_history=histories[game],
                    excluded_recent_points=excluded,
                    periods=args.periods,
                    window=window,
                )
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)

    report = {
        "schema_version": "ceway.v2.scorer-signal-audit.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Diagnose residual CEWAY-vs-matched-random underperformance after V2.1 largely removed "
            "portfolio concentration. This audit evaluates scorer ordering directly, independent of the generator."
        ),
        "settings": {"periods": args.periods, "windows": windows},
        "rows": rows,
        "diagnosis": {
            "DLT": diagnosis(rows, "DLT"),
            "SSQ": diagnosis(rows, "SSQ"),
        },
        "guardrail": (
            "All three reported blocks are already consumed research data. Results may guide architecture diagnosis, "
            "but any scorer change must be evaluated on an older untouched block or frozen prospective draws."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["diagnosis"], ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
