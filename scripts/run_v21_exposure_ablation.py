from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from engine import calculate_ssq_trends, calculate_trends, load_dlt_history, load_ssq_history  # noqa: E402
from generator_v2 import (  # noqa: E402
    GENERATOR_EXPOSURE_VERSION,
    GENERATOR_V2_VERSION,
    generate_dlt_coverage_single,
    generate_dlt_exposure_single,
    generate_ssq_coverage_single,
    generate_ssq_exposure_single,
)
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


def run_game(
    *,
    game: str,
    history: list[dict],
    window: int,
    periods: int,
    baseline_seeds: int,
    budget: int,
    strategy: str,
) -> dict:
    if game == "DLT":
        spec = DLT
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        v1_builder = generate_dlt_coverage_single
        v21_builder = generate_dlt_exposure_single
        reviewer = review_plan
        main_zones = DLT_MAIN_ZONES
        bonus_zones = DLT_BACK_ZONES
        bonus_sum_tolerance = 2
    else:
        spec = SSQ
        trend_builder = calculate_ssq_trends
        front_scorer = score_ssq_front_numbers
        back_scorer = score_ssq_back_numbers
        v1_builder = generate_ssq_coverage_single
        v21_builder = generate_ssq_exposure_single
        reviewer = review_ssq_plan
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_sum_tolerance = None

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)

    candidate_vs_v1_best = []
    candidate_vs_random_best = []
    candidate_vs_v1_ticket = []
    candidate_vs_random_ticket = []
    candidate_vs_v1_record = []
    candidate_vs_random_record = []
    v1_jaccards = []
    candidate_jaccards = []
    random_jaccards = []
    v1_best = []
    candidate_best = []
    random_best = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]
        trends = trend_builder(training, window=min(window, len(training)))
        score_table = front_scorer(trends)
        back_scores = back_scorer(trends)

        v1_plan = v1_builder(budget, score_table, back_scores, strategy)
        candidate_plan = v21_builder(budget, score_table, back_scores, strategy)
        v1_review = reviewer(v1_plan, actual)
        candidate_review = reviewer(candidate_plan, actual)

        random_reviews = []
        random_plans = []
        for seed_index in range(max(1, baseline_seeds)):
            random_plan = robust_structure_matched_random_plan(
                candidate_plan,
                spec,
                seed=f"v21-exposure-{game}-{source_issue}-{window}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_sum_tolerance,
            )
            random_plans.append(random_plan)
            random_reviews.append(reviewer(random_plan, actual))

        v1_best_value = best_hit_units(v1_review)
        candidate_best_value = best_hit_units(candidate_review)
        random_best_value = mean(best_hit_units(item) for item in random_reviews)
        v1_ticket_value = mean_ticket_hit_units(v1_review)
        candidate_ticket_value = mean_ticket_hit_units(candidate_review)
        random_ticket_value = mean(mean_ticket_hit_units(item) for item in random_reviews)
        v1_record_value = record_hit(v1_review)
        candidate_record_value = record_hit(candidate_review)
        random_record_value = mean(record_hit(item) for item in random_reviews)

        candidate_vs_v1_best.append(candidate_best_value - v1_best_value)
        candidate_vs_random_best.append(candidate_best_value - random_best_value)
        candidate_vs_v1_ticket.append(candidate_ticket_value - v1_ticket_value)
        candidate_vs_random_ticket.append(candidate_ticket_value - random_ticket_value)
        candidate_vs_v1_record.append(candidate_record_value - v1_record_value)
        candidate_vs_random_record.append(candidate_record_value - random_record_value)

        v1_jaccards.append(front_jaccard(v1_plan, spec))
        candidate_jaccards.append(front_jaccard(candidate_plan, spec))
        random_jaccards.append(mean(front_jaccard(plan, spec) for plan in random_plans))
        v1_best.append(v1_best_value)
        candidate_best.append(candidate_best_value)
        random_best.append(random_best_value)

    v1_best_ci = ci(candidate_vs_v1_best, f"{game}-{window}-v21-vs-v1-best")
    random_best_ci = ci(candidate_vs_random_best, f"{game}-{window}-v21-vs-random-best")
    metrics = {
        "candidate_vs_v1_best_hit": v1_best_ci,
        "candidate_vs_random_best_hit": random_best_ci,
        "candidate_vs_v1_mean_ticket_hit": ci(candidate_vs_v1_ticket, f"{game}-{window}-v21-vs-v1-ticket"),
        "candidate_vs_random_mean_ticket_hit": ci(candidate_vs_random_ticket, f"{game}-{window}-v21-vs-random-ticket"),
        "candidate_vs_v1_record_hit": ci(candidate_vs_v1_record, f"{game}-{window}-v21-vs-v1-record"),
        "candidate_vs_random_record_hit": ci(candidate_vs_random_record, f"{game}-{window}-v21-vs-random-record"),
        "v1_mean_best_hits": round(mean(v1_best), 4),
        "candidate_mean_best_hits": round(mean(candidate_best), 4),
        "random_mean_best_hits": round(mean(random_best), 4),
        "v1_front_mean_jaccard": round(mean(v1_jaccards), 4),
        "candidate_front_mean_jaccard": round(mean(candidate_jaccards), 4),
        "random_front_mean_jaccard": round(mean(random_jaccards), 4),
    }

    if v1_best_ci["ci95_low"] > 0 and random_best_ci["ci95_low"] > 0:
        decision = "PROMOTE_CANDIDATE"
        reason = "V2.1 significantly beats frozen V1 and structure-matched random on best-hit metric"
    elif v1_best_ci["ci95_low"] > 0 and random_best_ci["ci95_high"] >= 0:
        decision = "HOLD_FOR_HOLDOUT"
        reason = "V2.1 significantly beats frozen V1; matched-random comparison is non-negative/inconclusive"
    elif v1_best_ci["ci95_high"] < 0:
        decision = "REJECT"
        reason = "V2.1 is significantly worse than frozen V1"
    else:
        decision = "HOLD"
        reason = "development-sample evidence is inconclusive"

    return {
        "game": game,
        "window": window,
        "periods": len(candidate_vs_v1_best),
        "baseline_seeds": baseline_seeds,
        "frozen_v1_version": GENERATOR_V2_VERSION,
        "candidate_version": GENERATOR_EXPOSURE_VERSION,
        "decision": decision,
        "reason": reason,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B frozen V1 vs V2.1 score-exposure generator")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v21_exposure_ablation.json")
    args = parser.parse_args()

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows = []
    for game in ("DLT", "SSQ"):
        for window in windows:
            print(f"V2.1 A/B {game}: periods={args.periods}, window={window}", flush=True)
            row = run_game(
                game=game,
                history=histories[game],
                window=window,
                periods=args.periods,
                baseline_seeds=args.baseline_seeds,
                budget=args.budget,
                strategy=args.strategy,
            )
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)

    report = {
        "schema_version": "ceway.v2.1.exposure-ablation.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "development_evaluation_after_synthetic_parameter_selection",
        "parameter_provenance": (
            "V2.1 default structural parameters were selected using synthetic monotonic score tables and diversity targets, "
            "not lottery outcomes. This development run evaluates the frozen defaults against historical draws."
        ),
        "settings": {
            "periods": args.periods,
            "windows": windows,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "data": {
            "DLT": {"history_count": len(histories["DLT"]), "latest_issue": histories["DLT"][-1]["issue"]},
            "SSQ": {"history_count": len(histories["SSQ"]), "latest_issue": histories["SSQ"][-1]["issue"]},
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
