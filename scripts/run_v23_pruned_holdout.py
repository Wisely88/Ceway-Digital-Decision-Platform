from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import calculate_ssq_trends, calculate_trends, load_dlt_history, load_ssq_history  # noqa: E402
from generator import generate_plans, generate_ssq_plans  # noqa: E402
from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single  # noqa: E402
from random_control_v2 import robust_structure_matched_random_plan  # noqa: E402
from research_v2 import DLT, SSQ, bootstrap_mean_ci, diversity_summary, expand_plan_tickets, history_through_issue  # noqa: E402
from review import review_plan, review_ssq_plan  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402
from scorer_v23 import (  # noqa: E402
    SCORER_V23_VERSION,
    score_dlt_back_v23,
    score_dlt_front_v23,
    score_ssq_back_v23,
    score_ssq_front_v23,
)


WINDOWS = (50, 100, 200)
FRESH_EXCLUDED_RECENT_POINTS = 200
DLT_MAIN_ZONES = ((1, 12), (13, 24), (25, 35))
DLT_BACK_ZONES = ((1, 6), (7, 12))
SSQ_MAIN_ZONES = ((1, 11), (12, 22), (23, 33))
SSQ_BACK_ZONES = ((1, 8), (9, 16))


def ci(values: list[float], seed: str) -> dict:
    result = bootstrap_mean_ci(values, seed=seed)
    return {
        "mean": round(float(result["mean"]), 4),
        "ci95_low": round(float(result["low"]), 4),
        "ci95_high": round(float(result["high"]), 4),
    }


def best_hit_units(review: dict) -> float:
    best = review.get("best") or {}
    return float(best.get("front_hits", 0) + best.get("back_hits", 0))


def mean_ticket_hit_units(review: dict) -> float:
    details = review.get("details") or []
    if not details:
        return 0.0
    return mean(float(row.get("front_hits", 0) + row.get("back_hits", 0)) for row in details)


def record_hit(review: dict) -> float:
    return 1.0 if review.get("hit_tickets", 0) > 0 else 0.0


def front_jaccard(plan: dict, spec) -> float:
    tickets = expand_plan_tickets(plan, spec)
    return float(diversity_summary(ticket["front"] for ticket in tickets)["mean_jaccard"])


def score_auc(score_rows: list[dict], winners: list[int], pool_size: int) -> float:
    scores = {int(row["number"]): float(row.get("total_score", 0.0)) for row in score_rows}
    winner_set = set(int(number) for number in winners)
    losers = [number for number in range(1, pool_size + 1) if number not in winner_set]
    wins = 0.0
    comparisons = 0
    for winner in winner_set:
        winner_score = scores.get(winner, 0.0)
        for loser in losers:
            loser_score = scores.get(loser, 0.0)
            comparisons += 1
            if winner_score > loser_score:
                wins += 1.0
            elif winner_score == loser_score:
                wins += 0.5
    return wins / comparisons if comparisons else 0.5


def average_score_tables(tables: list[list[dict]], label: str) -> list[dict]:
    """Average same-scale V2.3 scores across fixed 50/100/200 windows.

    This is only used where V2.3 retains a history-dependent feature (DLT back).
    It avoids choosing a single window after looking at outcomes. Neutral SSQ and
    static DLT-front rules bypass this helper.
    """
    if not tables:
        return []
    by_number = []
    number_set = {int(row["number"]) for row in tables[0]}
    if any({int(row["number"]) for row in table} != number_set for table in tables[1:]):
        raise ValueError("score tables must contain identical number sets")
    maps = [{int(row["number"]): row for row in table} for table in tables]
    for number in sorted(number_set):
        source = dict(maps[0][number])
        source["total_score"] = round(mean(float(mapping[number]["total_score"]) for mapping in maps), 4)
        source["score"] = source["total_score"]
        source["scorer_version"] = SCORER_V23_VERSION
        source["scorer_label"] = label
        source["explanation"] = (
            "V2.3固定多窗口降噪：50/100/200期同尺度候选分数等权平均；"
            "窗口权重未使用开奖结果调参。"
        )
        by_number.append(source)
    by_number.sort(key=lambda row: (-float(row["total_score"]), int(row["number"])))
    for rank, row in enumerate(by_number, start=1):
        row["rank"] = rank
    return by_number


def build_candidate_scores(game: str, training: list[dict]) -> tuple[list[dict], list[dict], dict[int, tuple[list[dict], list[dict]]]]:
    window_sources: dict[int, tuple[list[dict], list[dict]]] = {}
    transformed_front = []
    transformed_back = []

    for window in WINDOWS:
        if game == "DLT":
            trends = calculate_trends(training, window=min(window, len(training)))
            raw_front = score_front_numbers(trends)
            raw_back = score_back_numbers(trends)
            front = score_dlt_front_v23(raw_front)
            back = score_dlt_back_v23(raw_back)
        else:
            trends = calculate_ssq_trends(training, window=min(window, len(training)))
            raw_front = score_ssq_front_numbers(trends)
            raw_back = score_ssq_back_numbers(trends)
            front = score_ssq_front_v23(raw_front)
            back = score_ssq_back_v23(raw_back)
        window_sources[window] = (raw_front, raw_back)
        transformed_front.append(front)
        transformed_back.append(back)

    if game == "DLT":
        # DLT front balance-only is history-independent, so all three are the
        # same ordering. DLT back retains heat and is averaged across windows.
        candidate_front = transformed_front[0]
        candidate_back = average_score_tables(transformed_back, "DLT.back.heat_balance_equal.multiwindow")
    else:
        # Both SSQ zones deliberately encode no ranking claim.
        candidate_front = transformed_front[0]
        candidate_back = transformed_back[0]
    return candidate_front, candidate_back, window_sources


def block_provenance(history: list[dict], periods: int = 50) -> dict:
    n = len(history)

    def block(end_exclusive: int) -> dict:
        rows = history[end_exclusive - periods : end_exclusive]
        return {
            "count": len(rows),
            "first_issue": rows[0]["issue"],
            "last_issue": rows[-1]["issue"],
        }

    return {
        "development": block(n),
        "v1_holdout": block(n - 50),
        "v21_holdout": block(n - 100),
        "v22_quarantined_block": block(n - 150),
        "v23_fresh_holdout": block(n - 200),
        "blocks_overlap": False,
        "rule": "V2.3 scorer candidate may read only outcomes older than the four newer 50-outcome blocks.",
    }


def run_game(
    *,
    game: str,
    full_history: list[dict],
    periods: int,
    baseline_seeds: int,
    budget: int,
    strategy: str,
) -> dict:
    history = full_history[:-FRESH_EXCLUDED_RECENT_POINTS]
    if len(history) < periods + max(WINDOWS) + 1:
        raise ValueError(f"not enough history for {game} V2.3 holdout")

    if game == "DLT":
        spec = DLT
        legacy_builder = generate_plans
        v21_builder = generate_dlt_exposure_single
        candidate_builder = generate_dlt_exposure_single
        reviewer = review_plan
        main_zones = DLT_MAIN_ZONES
        bonus_zones = DLT_BACK_ZONES
        bonus_sum_tolerance = 2
        front_pool = 35
        back_pool = 12
    else:
        spec = SSQ
        legacy_builder = generate_ssq_plans
        v21_builder = generate_ssq_exposure_single
        candidate_builder = generate_ssq_exposure_single
        reviewer = review_ssq_plan
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_sum_tolerance = None
        front_pool = 33
        back_pool = 16

    end_source = len(history) - 2
    start_source = end_source - periods + 1
    candidate_vs_random_best = []
    candidate_vs_random_ticket = []
    candidate_vs_random_record = []
    front_auc_advantages = []
    back_auc_advantages = []
    candidate_jaccards = []
    random_jaccards = []
    baseline_diffs = {
        window: {"legacy": [], "v21": []}
        for window in WINDOWS
    }
    outcome_issues = []

    for index in range(start_source, end_source + 1):
        source_issue = str(history[index]["issue"])
        actual = history[index + 1]
        training = history_through_issue(history, source_issue)
        candidate_front, candidate_back, window_sources = build_candidate_scores(game, training)
        candidate_plan = candidate_builder(budget, candidate_front, candidate_back, strategy)
        candidate_review = reviewer(candidate_plan, actual)

        front_auc_advantages.append(score_auc(candidate_front, actual["front"], front_pool) - 0.5)
        back_auc_advantages.append(score_auc(candidate_back, actual["back"], back_pool) - 0.5)

        for window, (raw_front, raw_back) in window_sources.items():
            legacy_plan = legacy_builder(
                budget=budget,
                strategy=strategy,
                score_table=raw_front,
                back_scores=raw_back,
            )[0]
            v21_plan = v21_builder(budget, raw_front, raw_back, strategy)
            legacy_review = reviewer(legacy_plan, actual)
            v21_review = reviewer(v21_plan, actual)
            candidate_best = best_hit_units(candidate_review)
            baseline_diffs[window]["legacy"].append(candidate_best - best_hit_units(legacy_review))
            baseline_diffs[window]["v21"].append(candidate_best - best_hit_units(v21_review))

        random_plans = []
        random_reviews = []
        for seed_index in range(max(1, baseline_seeds)):
            random_plan = robust_structure_matched_random_plan(
                candidate_plan,
                spec,
                seed=f"v23-pruned-{game}-{source_issue}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_sum_tolerance,
            )
            random_plans.append(random_plan)
            random_reviews.append(reviewer(random_plan, actual))

        candidate_best = best_hit_units(candidate_review)
        random_best = mean(best_hit_units(review) for review in random_reviews)
        random_ticket = mean(mean_ticket_hit_units(review) for review in random_reviews)
        random_record = mean(record_hit(review) for review in random_reviews)
        candidate_vs_random_best.append(candidate_best - random_best)
        candidate_vs_random_ticket.append(mean_ticket_hit_units(candidate_review) - random_ticket)
        candidate_vs_random_record.append(record_hit(candidate_review) - random_record)
        candidate_jaccards.append(front_jaccard(candidate_plan, spec))
        random_jaccards.append(mean(front_jaccard(plan, spec) for plan in random_plans))
        outcome_issues.append(str(actual["issue"]))

    baseline_comparisons = []
    for window in WINDOWS:
        baseline_comparisons.append(
            {
                "baseline_window": window,
                "candidate_vs_legacy_best_hit": ci(
                    baseline_diffs[window]["legacy"], f"v23-{game}-{window}-legacy"
                ),
                "candidate_vs_v21_best_hit": ci(
                    baseline_diffs[window]["v21"], f"v23-{game}-{window}-v21"
                ),
            }
        )

    metrics = {
        "candidate_vs_random_best_hit": ci(candidate_vs_random_best, f"v23-{game}-random-best"),
        "candidate_vs_random_mean_ticket_hit": ci(candidate_vs_random_ticket, f"v23-{game}-random-ticket"),
        "candidate_vs_random_record_hit": ci(candidate_vs_random_record, f"v23-{game}-random-record"),
        "front_auc_advantage_over_random": ci(front_auc_advantages, f"v23-{game}-front-auc"),
        "back_auc_advantage_over_random": ci(back_auc_advantages, f"v23-{game}-back-auc"),
        "candidate_front_mean_jaccard": round(mean(candidate_jaccards), 4),
        "random_front_mean_jaccard": round(mean(random_jaccards), 4),
        "baseline_comparisons": baseline_comparisons,
    }
    return {
        "game": game,
        "scorer_version": SCORER_V23_VERSION,
        "periods": len(outcome_issues),
        "first_outcome_issue": outcome_issues[0],
        "last_outcome_issue": outcome_issues[-1],
        "baseline_seeds": baseline_seeds,
        "metrics": metrics,
    }


def gate(game: str, metrics: dict) -> dict:
    target_jaccard = 0.15 if game == "DLT" else 0.18
    baseline_rows = metrics["baseline_comparisons"]
    structural_ok = metrics["candidate_front_mean_jaccard"] <= target_jaccard
    legacy_positive_all = all(row["candidate_vs_legacy_best_hit"]["mean"] > 0 for row in baseline_rows)
    legacy_significant_two = sum(
        row["candidate_vs_legacy_best_hit"]["ci95_low"] > 0 for row in baseline_rows
    ) >= 2
    v21_nonnegative_two = sum(
        row["candidate_vs_v21_best_hit"]["mean"] >= 0 for row in baseline_rows
    ) >= 2
    random_best_not_worse = metrics["candidate_vs_random_best_hit"]["ci95_high"] >= 0
    random_record_not_worse = metrics["candidate_vs_random_record_hit"]["ci95_high"] >= 0
    front_not_antisignal = metrics["front_auc_advantage_over_random"]["ci95_high"] >= 0
    back_not_antisignal = metrics["back_auc_advantage_over_random"]["ci95_high"] >= 0

    if (
        structural_ok
        and legacy_positive_all
        and legacy_significant_two
        and v21_nonnegative_two
        and random_best_not_worse
        and random_record_not_worse
        and front_not_antisignal
        and back_not_antisignal
    ):
        if (
            metrics["front_auc_advantage_over_random"]["mean"] <= 0
            and metrics["back_auc_advantage_over_random"]["mean"] <= 0
        ):
            decision = "ADVANCE_COVERAGE_ONLY_SHADOW"
            reason = "portfolio gate passes but scorer shows no positive ranking mean; forward use must remain coverage-only"
        else:
            decision = "ADVANCE_TO_FORWARD_SHADOW"
            reason = "V2.3 passes fresh scorer and portfolio non-inferiority gates"
    elif not structural_ok:
        decision = "REJECT"
        reason = "V2.3 misses structural diversity target"
    elif not front_not_antisignal or not back_not_antisignal:
        decision = "REJECT"
        reason = "V2.3 scorer is significantly anti-signal in at least one zone"
    elif not random_best_not_worse or not random_record_not_worse:
        decision = "REJECT"
        reason = "V2.3 portfolio is significantly worse than matched random on best-hit or record-hit"
    else:
        decision = "HOLD"
        reason = "V2.3 fresh holdout evidence is mixed; do not advance"

    return {
        "decision": decision,
        "reason": reason,
        "target_front_mean_jaccard": target_jaccard,
        "structural_ok": structural_ok,
        "legacy_positive_all_windows": legacy_positive_all,
        "legacy_significant_in_at_least_two_windows": legacy_significant_two,
        "v21_nonnegative_in_at_least_two_windows": v21_nonnegative_two,
        "random_best_not_significantly_worse": random_best_not_worse,
        "random_record_not_significantly_worse": random_record_not_worse,
        "front_scorer_not_significantly_antisignal": front_not_antisignal,
        "back_scorer_not_significantly_antisignal": back_not_antisignal,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh exclude=200 holdout for frozen CEWAY V2.3 pruned scorer")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v23_pruned_holdout.json",
    )
    args = parser.parse_args()

    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows = []
    gates = {}
    provenance = {game: block_provenance(history, args.periods) for game, history in histories.items()}
    for game in ("DLT", "SSQ"):
        print(
            f"V2.3 FRESH HOLDOUT {game}: periods={args.periods}, excluded={FRESH_EXCLUDED_RECENT_POINTS}",
            flush=True,
        )
        row = run_game(
            game=game,
            full_history=histories[game],
            periods=args.periods,
            baseline_seeds=args.baseline_seeds,
            budget=args.budget,
            strategy=args.strategy,
        )
        row["gate"] = gate(game, row["metrics"])
        rows.append(row)
        gates[game] = row["gate"]
        print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)

    report = {
        "schema_version": "ceway.v2.3.pruned-scorer-holdout.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "fresh_retrospective_holdout_exclude_200",
        "scorer_version": SCORER_V23_VERSION,
        "formula_provenance": {
            "DLT_front": "balance only",
            "DLT_back": "equal heat + balance, averaged across fixed 50/100/200 windows",
            "SSQ_front": "neutral shrink; no ranking claim",
            "SSQ_back": "neutral shrink; no ranking claim",
            "outcome_tuned_coefficients": False,
            "selection_basis": "feature audit on already-consumed exclude=0/50/100 blocks only",
        },
        "settings": {
            "periods": args.periods,
            "excluded_recent_points": FRESH_EXCLUDED_RECENT_POINTS,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
            "windows": list(WINDOWS),
        },
        "block_provenance": provenance,
        "rows": rows,
        "gates": gates,
        "all_games_advance": all(gate_row["decision"].startswith("ADVANCE") for gate_row in gates.values()),
        "interpretation": (
            "Passing authorizes only unchanged forward shadow validation. It does not justify production merge, "
            "guaranteed-return language, or a claim that lottery history predicts future draws."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gates, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
