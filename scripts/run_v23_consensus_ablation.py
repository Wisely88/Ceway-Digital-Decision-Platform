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

from consensus_v23 import (  # noqa: E402
    CONSENSUS_V23_VERSION,
    CONSENSUS_WINDOWS,
    generate_dlt_consensus_exposure_single,
    generate_ssq_consensus_exposure_single,
    median_rank_consensus,
)
from engine import calculate_ssq_trends, calculate_trends, load_dlt_history, load_ssq_history  # noqa: E402
from generator import generate_plans, generate_ssq_plans  # noqa: E402
from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single  # noqa: E402
from random_control_v2 import robust_structure_matched_random_plan  # noqa: E402
from research_v2 import DLT, SSQ, bootstrap_mean_ci, diversity_summary, expand_plan_tickets, history_through_issue  # noqa: E402
from review import review_plan, review_ssq_plan  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402


DLT_MAIN_ZONES = ((1, 12), (13, 24), (25, 35))
DLT_BACK_ZONES = ((1, 6), (7, 12))
SSQ_MAIN_ZONES = ((1, 11), (12, 22), (23, 33))
SSQ_BACK_ZONES = ((1, 8), (9, 16))


def best_hit_units(review: dict) -> float:
    best = review.get("best") or {}
    return float(best.get("front_hits", 0) + best.get("back_hits", 0))


def mean_ticket_hit_units(review: dict) -> float:
    details = review.get("details") or []
    if not details:
        return 0.0
    return mean(float(item.get("front_hits", 0) + item.get("back_hits", 0)) for item in details)


def record_hit(review: dict) -> float:
    return 1.0 if review.get("hit_tickets", 0) > 0 else 0.0


def front_jaccard(plan: dict, spec) -> float:
    tickets = expand_plan_tickets(plan, spec)
    return float(diversity_summary(ticket["front"] for ticket in tickets)["mean_jaccard"])


def ci(values: list[float], seed: str) -> dict:
    result = bootstrap_mean_ci(values, seed=seed)
    return {
        "mean": round(float(result["mean"]), 4),
        "ci95_low": round(float(result["low"]), 4),
        "ci95_high": round(float(result["high"]), 4),
    }


def development_gate(game: str, metrics: dict) -> dict:
    target_jaccard = 0.15 if game == "DLT" else 0.18
    structural_ok = metrics["candidate_front_mean_jaccard"] <= target_jaccard
    baseline_rows = metrics["baseline_comparisons"]
    legacy_positive_all = all(row["candidate_vs_legacy_best_hit"]["mean"] > 0 for row in baseline_rows)
    legacy_significant_two = sum(
        row["candidate_vs_legacy_best_hit"]["ci95_low"] > 0 for row in baseline_rows
    ) >= 2
    v21_nonnegative_two = sum(
        row["candidate_vs_v21_best_hit"]["mean"] >= 0 for row in baseline_rows
    ) >= 2
    random_not_significantly_worse = metrics["candidate_vs_random_best_hit"]["ci95_high"] >= 0

    if structural_ok and legacy_positive_all and legacy_significant_two and v21_nonnegative_two and random_not_significantly_worse:
        decision = "ADVANCE_TO_FRESH_HOLDOUT"
        reason = "median-rank consensus passes structural, legacy, V2.1, and matched-random development gates"
    elif not structural_ok:
        decision = "REJECT_STRUCTURE"
        reason = "median-rank portfolio misses the pre-registered diversity target"
    elif metrics["candidate_vs_random_best_hit"]["ci95_high"] < 0:
        decision = "REJECT_RANDOM"
        reason = "median-rank candidate is significantly worse than structure-matched random on development data"
    elif sum(row["candidate_vs_v21_best_hit"]["ci95_high"] < 0 for row in baseline_rows) >= 2:
        decision = "REJECT_V21"
        reason = "median-rank candidate is significantly worse than frozen V2.1 in at least two baseline windows"
    else:
        decision = "HOLD"
        reason = "development evidence is mixed; do not consume the fresh V2.3 holdout"

    return {
        "decision": decision,
        "reason": reason,
        "target_front_mean_jaccard": target_jaccard,
        "structural_ok": structural_ok,
        "legacy_positive_all_windows": legacy_positive_all,
        "legacy_significant_in_at_least_two_windows": legacy_significant_two,
        "v21_nonnegative_in_at_least_two_windows": v21_nonnegative_two,
        "random_not_significantly_worse": random_not_significantly_worse,
    }


def run_game(
    *,
    game: str,
    history: list[dict],
    periods: int,
    baseline_seeds: int,
    budget: int,
    strategy: str,
    windows: tuple[int, ...] = CONSENSUS_WINDOWS,
) -> dict:
    if game == "DLT":
        spec = DLT
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        legacy_builder = generate_plans
        v21_builder = generate_dlt_exposure_single
        candidate_builder = generate_dlt_consensus_exposure_single
        reviewer = review_plan
        main_zones = DLT_MAIN_ZONES
        bonus_zones = DLT_BACK_ZONES
        bonus_sum_tolerance = 2
    else:
        spec = SSQ
        trend_builder = calculate_ssq_trends
        front_scorer = score_ssq_front_numbers
        back_scorer = score_ssq_back_numbers
        legacy_builder = generate_ssq_plans
        v21_builder = generate_ssq_exposure_single
        candidate_builder = generate_ssq_consensus_exposure_single
        reviewer = review_ssq_plan
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_sum_tolerance = None

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)

    baseline_deltas = {
        window: {
            "candidate_vs_legacy": [],
            "candidate_vs_v21": [],
            "legacy_best": [],
            "v21_best": [],
        }
        for window in windows
    }
    candidate_vs_random = []
    candidate_vs_random_ticket = []
    candidate_vs_random_record = []
    candidate_best_values = []
    random_best_values = []
    candidate_jaccards = []
    random_jaccards = []
    front_rank_stddevs = []
    back_rank_stddevs = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]

        front_tables = []
        back_tables = []
        for window in windows:
            trends = trend_builder(training, window=min(window, len(training)))
            front_tables.append(front_scorer(trends))
            back_tables.append(back_scorer(trends))

        consensus_front = median_rank_consensus(front_tables, windows=windows)
        consensus_back = median_rank_consensus(back_tables, windows=windows)
        candidate_plan = candidate_builder(budget, consensus_front, consensus_back, strategy)
        candidate_review = reviewer(candidate_plan, actual)
        candidate_best = best_hit_units(candidate_review)

        random_plans = []
        random_reviews = []
        for seed_index in range(max(1, baseline_seeds)):
            random_plan = robust_structure_matched_random_plan(
                candidate_plan,
                spec,
                seed=f"v23-median-consensus-{game}-{source_issue}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_sum_tolerance,
            )
            random_plans.append(random_plan)
            random_reviews.append(reviewer(random_plan, actual))

        random_best = mean(best_hit_units(item) for item in random_reviews)
        candidate_vs_random.append(candidate_best - random_best)
        candidate_vs_random_ticket.append(
            mean_ticket_hit_units(candidate_review) - mean(mean_ticket_hit_units(item) for item in random_reviews)
        )
        candidate_vs_random_record.append(
            record_hit(candidate_review) - mean(record_hit(item) for item in random_reviews)
        )
        candidate_best_values.append(candidate_best)
        random_best_values.append(random_best)
        candidate_jaccards.append(front_jaccard(candidate_plan, spec))
        random_jaccards.append(mean(front_jaccard(plan, spec) for plan in random_plans))
        front_rank_stddevs.append(mean(float(row["rank_stddev"]) for row in consensus_front))
        back_rank_stddevs.append(mean(float(row["rank_stddev"]) for row in consensus_back))

        for table_index, window in enumerate(windows):
            score_table = front_tables[table_index]
            back_scores = back_tables[table_index]
            legacy_plan = legacy_builder(
                budget=budget,
                strategy=strategy,
                score_table=score_table,
                back_scores=back_scores,
            )[0]
            v21_plan = v21_builder(budget, score_table, back_scores, strategy)
            legacy_best = best_hit_units(reviewer(legacy_plan, actual))
            v21_best = best_hit_units(reviewer(v21_plan, actual))
            baseline_deltas[window]["candidate_vs_legacy"].append(candidate_best - legacy_best)
            baseline_deltas[window]["candidate_vs_v21"].append(candidate_best - v21_best)
            baseline_deltas[window]["legacy_best"].append(legacy_best)
            baseline_deltas[window]["v21_best"].append(v21_best)

    baseline_comparisons = []
    for window in windows:
        values = baseline_deltas[window]
        baseline_comparisons.append(
            {
                "baseline_window": window,
                "candidate_vs_legacy_best_hit": ci(values["candidate_vs_legacy"], f"v23-{game}-{window}-legacy"),
                "candidate_vs_v21_best_hit": ci(values["candidate_vs_v21"], f"v23-{game}-{window}-v21"),
                "legacy_mean_best_hits": round(mean(values["legacy_best"]), 4),
                "v21_mean_best_hits": round(mean(values["v21_best"]), 4),
            }
        )

    metrics = {
        "candidate_vs_random_best_hit": ci(candidate_vs_random, f"v23-{game}-random-best"),
        "candidate_vs_random_mean_ticket_hit": ci(candidate_vs_random_ticket, f"v23-{game}-random-ticket"),
        "candidate_vs_random_record_hit": ci(candidate_vs_random_record, f"v23-{game}-random-record"),
        "candidate_mean_best_hits": round(mean(candidate_best_values), 4),
        "random_mean_best_hits": round(mean(random_best_values), 4),
        "candidate_front_mean_jaccard": round(mean(candidate_jaccards), 4),
        "random_front_mean_jaccard": round(mean(random_jaccards), 4),
        "front_mean_rank_stddev": round(mean(front_rank_stddevs), 4),
        "back_mean_rank_stddev": round(mean(back_rank_stddevs), 4),
        "baseline_comparisons": baseline_comparisons,
    }
    return {
        "game": game,
        "periods": len(candidate_vs_random),
        "consensus_windows": list(windows),
        "baseline_seeds": baseline_seeds,
        "candidate_generator_version": CONSENSUS_V23_VERSION,
        "metrics": metrics,
        "gate": development_gate(game, metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Development A/B for CEWAY V2.3 median-rank consensus")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v23_consensus_ablation.json")
    args = parser.parse_args()

    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows = []
    for game in ("DLT", "SSQ"):
        print(f"V2.3 median consensus development {game}: periods={args.periods}, windows={CONSENSUS_WINDOWS}", flush=True)
        row = run_game(
            game=game,
            history=histories[game],
            periods=args.periods,
            baseline_seeds=args.baseline_seeds,
            budget=args.budget,
            strategy=args.strategy,
        )
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)

    report = {
        "schema_version": "ceway.v2.3.median-consensus-ablation.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "development_only_reusing_consumed_recent_block",
        "candidate_generator_version": CONSENSUS_V23_VERSION,
        "parameter_provenance": (
            "Windows are fixed at 50/100/200. Each window becomes a rank-percentile table and the candidate uses the median "
            "percentile (two-of-three consensus). No learned weights or lottery-outcome tuning are used. The V2.1 exposure "
            "combination engine is unchanged."
        ),
        "settings": {
            "periods": args.periods,
            "consensus_windows": list(CONSENSUS_WINDOWS),
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "data": {
            "DLT": {"history_count": len(histories["DLT"]), "latest_issue": histories["DLT"][-1]["issue"]},
            "SSQ": {"history_count": len(histories["SSQ"]), "latest_issue": histories["SSQ"][-1]["issue"]},
        },
        "rows": rows,
        "all_games_advance": all(row["gate"]["decision"] == "ADVANCE_TO_FRESH_HOLDOUT" for row in rows),
        "interpretation": (
            "This run reuses only consumed development outcomes. It may unlock the still-untouched excluded=150 holdout block, "
            "but is not itself promotion evidence."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ALL_GAMES_ADVANCE={str(report['all_games_advance']).lower()}", flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
