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
from research_v2 import (  # noqa: E402
    DLT,
    SSQ,
    bootstrap_mean_ci,
    diversity_summary,
    expand_plan_tickets,
    history_through_issue,
    structure_matched_random_plan,
)
from review import review_plan, review_ssq_plan  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402


DLT_MAIN_ZONES = ((1, 12), (13, 24), (25, 35))
DLT_BACK_ZONES = ((1, 6), (7, 12))
SSQ_MAIN_ZONES = ((1, 11), (12, 22), (23, 33))
SSQ_BACK_ZONES = ((1, 8), (9, 16))


def ticket_mean_hit_units(review: dict) -> float:
    rows = review.get("details") or []
    if not rows:
        return 0.0
    return mean(float(row.get("front_hits", 0) + row.get("back_hits", 0)) for row in rows)


def best_hit_units(review: dict) -> float:
    best = review.get("best") or {}
    return float(best.get("front_hits", 0) + best.get("back_hits", 0))


def front_jaccard(plan: dict, spec) -> float:
    tickets = expand_plan_tickets(plan, spec)
    return float(diversity_summary(ticket["front"] for ticket in tickets)["mean_jaccard"])


def diagnose(metrics: dict) -> str:
    ticket_ci = metrics["mean_ticket_hit_uplift"]
    best_ci = metrics["best_hit_uplift"]
    jaccard_delta = metrics["front_mean_jaccard_delta"]
    ticket_negative = ticket_ci["ci95_high"] < 0
    best_negative = best_ci["ci95_high"] < 0
    ticket_inconclusive = ticket_ci["ci95_low"] <= 0 <= ticket_ci["ci95_high"]
    more_clustered = jaccard_delta > 0.02

    if ticket_negative and best_negative and more_clustered:
        return "ranking_and_coverage"
    if ticket_negative:
        return "ranking_quality"
    if ticket_inconclusive and best_negative and more_clustered:
        return "coverage_concentration"
    if best_negative:
        return "portfolio_effect_or_other"
    return "no_clear_negative_driver"


def run_game(
    *,
    game: str,
    history: list[dict],
    spec,
    window: int,
    periods: int,
    baseline_seeds: int,
    budget: int,
    strategy: str,
) -> dict:
    if game == "DLT":
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        plan_builder = generate_plans
        reviewer = review_plan
        main_zones = DLT_MAIN_ZONES
        bonus_zones = DLT_BACK_ZONES
        bonus_sum_tolerance = 2
    else:
        trend_builder = calculate_ssq_trends
        front_scorer = score_ssq_front_numbers
        back_scorer = score_ssq_back_numbers
        plan_builder = generate_ssq_plans
        reviewer = review_ssq_plan
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_sum_tolerance = None

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)
    ticket_uplifts = []
    best_uplifts = []
    jaccard_deltas = []
    ceway_ticket_means = []
    baseline_ticket_means = []
    ceway_best_values = []
    baseline_best_values = []
    ceway_jaccards = []
    baseline_jaccards = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]
        trends = trend_builder(training, window=min(window, len(training)))
        score_table = front_scorer(trends)
        back_scores = back_scorer(trends)
        plan = plan_builder(
            budget=budget,
            strategy=strategy,
            score_table=score_table,
            back_scores=back_scores,
        )[0]
        ceway_review = reviewer(plan, actual)
        ceway_ticket_mean = ticket_mean_hit_units(ceway_review)
        ceway_best = best_hit_units(ceway_review)
        ceway_jaccard = front_jaccard(plan, spec)

        seed_ticket_means = []
        seed_best = []
        seed_jaccards = []
        for seed_index in range(baseline_seeds):
            baseline_plan = structure_matched_random_plan(
                plan,
                spec,
                seed=f"diag-{game}-{source_issue}-{budget}-{window}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_sum_tolerance,
            )
            baseline_review = reviewer(baseline_plan, actual)
            seed_ticket_means.append(ticket_mean_hit_units(baseline_review))
            seed_best.append(best_hit_units(baseline_review))
            seed_jaccards.append(front_jaccard(baseline_plan, spec))

        baseline_ticket_mean = mean(seed_ticket_means)
        baseline_best = mean(seed_best)
        baseline_jaccard = mean(seed_jaccards)
        ticket_uplifts.append(ceway_ticket_mean - baseline_ticket_mean)
        best_uplifts.append(ceway_best - baseline_best)
        jaccard_deltas.append(ceway_jaccard - baseline_jaccard)
        ceway_ticket_means.append(ceway_ticket_mean)
        baseline_ticket_means.append(baseline_ticket_mean)
        ceway_best_values.append(ceway_best)
        baseline_best_values.append(baseline_best)
        ceway_jaccards.append(ceway_jaccard)
        baseline_jaccards.append(baseline_jaccard)

    ticket_ci = bootstrap_mean_ci(ticket_uplifts, seed=f"diag-{game}-{window}-ticket")
    best_ci = bootstrap_mean_ci(best_uplifts, seed=f"diag-{game}-{window}-best")
    metrics = {
        "mean_ticket_hit_uplift": {
            "mean": round(float(ticket_ci["mean"]), 4),
            "ci95_low": round(float(ticket_ci["low"]), 4),
            "ci95_high": round(float(ticket_ci["high"]), 4),
        },
        "best_hit_uplift": {
            "mean": round(float(best_ci["mean"]), 4),
            "ci95_low": round(float(best_ci["low"]), 4),
            "ci95_high": round(float(best_ci["high"]), 4),
        },
        "ceway_mean_ticket_hits": round(mean(ceway_ticket_means), 4),
        "baseline_mean_ticket_hits": round(mean(baseline_ticket_means), 4),
        "ceway_mean_best_hits": round(mean(ceway_best_values), 4),
        "baseline_mean_best_hits": round(mean(baseline_best_values), 4),
        "ceway_front_mean_jaccard": round(mean(ceway_jaccards), 4),
        "baseline_front_mean_jaccard": round(mean(baseline_jaccards), 4),
        "front_mean_jaccard_delta": round(mean(jaccard_deltas), 4),
    }
    return {
        "game": game,
        "window": window,
        "periods": len(ticket_uplifts),
        "baseline_seeds": baseline_seeds,
        "metrics": metrics,
        "driver": diagnose(metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose CEWAY V2 ranking vs portfolio coverage")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v2_diagnostics.json")
    args = parser.parse_args()

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows = []
    for game, spec in (("DLT", DLT), ("SSQ", SSQ)):
        for window in windows:
            print(f"Diagnosing {game}: periods={args.periods}, window={window}", flush=True)
            rows.append(
                run_game(
                    game=game,
                    history=histories[game],
                    spec=spec,
                    window=window,
                    periods=args.periods,
                    baseline_seeds=args.baseline_seeds,
                    budget=args.budget,
                    strategy=args.strategy,
                )
            )

    report = {
        "schema_version": "ceway.v2.diagnostics.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "periods": args.periods,
            "windows": windows,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "rows": rows,
        "legend": {
            "ranking_quality": "paired CEWAY tickets have significantly lower average hits than matched random tickets",
            "coverage_concentration": "single-ticket quality is inconclusive but CEWAY portfolio is more clustered and loses on best-of-budget outcome",
            "ranking_and_coverage": "both paired ticket quality and portfolio diversity are materially worse",
            "portfolio_effect_or_other": "best-of-budget result is negative but current decomposition does not isolate ranking or clustering",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
