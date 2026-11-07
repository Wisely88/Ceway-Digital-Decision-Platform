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
from generator_v2 import (  # noqa: E402
    GENERATOR_EXPOSURE_VERSION,
    GENERATOR_V2_VERSION,
    generate_dlt_coverage_single,
    generate_dlt_exposure_single,
    generate_ssq_coverage_single,
    generate_ssq_exposure_single,
)
from random_control_v2 import robust_structure_matched_random_plan  # noqa: E402
from research_v2 import (  # noqa: E402
    DLT,
    SSQ,
    bootstrap_mean_ci,
    diversity_summary,
    expand_plan_tickets,
    history_through_issue,
)
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


def development_gate(game: str, rows: list[dict]) -> dict:
    target_jaccard = 0.15 if game == "DLT" else 0.18
    structural_ok = all(row["metrics"]["v21_front_mean_jaccard"] <= target_jaccard for row in rows)
    legacy_means_positive = all(row["metrics"]["v21_vs_legacy_best_hit"]["mean"] > 0 for row in rows)
    v1_not_worse = sum(
        row["metrics"]["v21_vs_v1_best_hit"]["mean"] >= 0
        for row in rows
    ) >= 2
    significant_random_losses = sum(
        row["metrics"]["v21_vs_random_best_hit"]["ci95_high"] < 0
        for row in rows
    )

    if structural_ok and legacy_means_positive and v1_not_worse and significant_random_losses <= 1:
        decision = "ADVANCE_TO_FRESH_HOLDOUT"
        reason = "structural diversity target passed and development performance did not regress materially"
    elif not structural_ok:
        decision = "REJECT_STRUCTURE"
        reason = "portfolio diversity target was not reached in all scoring windows"
    elif not legacy_means_positive:
        decision = "REJECT_PERFORMANCE"
        reason = "V2.1 failed to improve legacy best-hit mean in every development window"
    else:
        decision = "HOLD"
        reason = "development evidence is mixed; do not consume a fresh holdout yet"

    return {
        "decision": decision,
        "reason": reason,
        "target_front_mean_jaccard": target_jaccard,
        "structural_ok": structural_ok,
        "legacy_means_positive": legacy_means_positive,
        "v21_nonnegative_vs_v1_in_at_least_two_windows": v1_not_worse,
        "significant_random_loss_windows": significant_random_losses,
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
        legacy_builder = generate_plans
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
        legacy_builder = generate_ssq_plans
        v1_builder = generate_ssq_coverage_single
        v21_builder = generate_ssq_exposure_single
        reviewer = review_ssq_plan
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_sum_tolerance = None

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)

    v21_vs_legacy_best = []
    v21_vs_v1_best = []
    v21_vs_random_best = []
    v21_vs_random_ticket = []
    v21_vs_random_record = []
    legacy_jaccards = []
    v1_jaccards = []
    v21_jaccards = []
    random_jaccards = []
    legacy_best_values = []
    v1_best_values = []
    v21_best_values = []
    random_best_values = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]
        trends = trend_builder(training, window=min(window, len(training)))
        score_table = front_scorer(trends)
        back_scores = back_scorer(trends)

        legacy_plan = legacy_builder(
            budget=budget,
            strategy=strategy,
            score_table=score_table,
            back_scores=back_scores,
        )[0]
        v1_plan = v1_builder(budget, score_table, back_scores, strategy)
        v21_plan = v21_builder(budget, score_table, back_scores, strategy)

        legacy_review = reviewer(legacy_plan, actual)
        v1_review = reviewer(v1_plan, actual)
        v21_review = reviewer(v21_plan, actual)

        random_plans = []
        random_reviews = []
        for seed_index in range(max(1, baseline_seeds)):
            random_plan = robust_structure_matched_random_plan(
                v21_plan,
                spec,
                seed=f"exposure-ablation-{game}-{source_issue}-{window}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_sum_tolerance,
            )
            random_plans.append(random_plan)
            random_reviews.append(reviewer(random_plan, actual))

        legacy_best = best_hit_units(legacy_review)
        v1_best = best_hit_units(v1_review)
        v21_best = best_hit_units(v21_review)
        random_best = mean(best_hit_units(item) for item in random_reviews)
        random_ticket = mean(mean_ticket_hit_units(item) for item in random_reviews)
        random_record = mean(record_hit(item) for item in random_reviews)

        v21_vs_legacy_best.append(v21_best - legacy_best)
        v21_vs_v1_best.append(v21_best - v1_best)
        v21_vs_random_best.append(v21_best - random_best)
        v21_vs_random_ticket.append(mean_ticket_hit_units(v21_review) - random_ticket)
        v21_vs_random_record.append(record_hit(v21_review) - random_record)

        legacy_jaccards.append(front_jaccard(legacy_plan, spec))
        v1_jaccards.append(front_jaccard(v1_plan, spec))
        v21_jaccards.append(front_jaccard(v21_plan, spec))
        random_jaccards.append(mean(front_jaccard(plan, spec) for plan in random_plans))
        legacy_best_values.append(legacy_best)
        v1_best_values.append(v1_best)
        v21_best_values.append(v21_best)
        random_best_values.append(random_best)

    metrics = {
        "v21_vs_legacy_best_hit": ci(v21_vs_legacy_best, f"{game}-{window}-v21-legacy"),
        "v21_vs_v1_best_hit": ci(v21_vs_v1_best, f"{game}-{window}-v21-v1"),
        "v21_vs_random_best_hit": ci(v21_vs_random_best, f"{game}-{window}-v21-random"),
        "v21_vs_random_mean_ticket_hit": ci(v21_vs_random_ticket, f"{game}-{window}-v21-random-ticket"),
        "v21_vs_random_record_hit": ci(v21_vs_random_record, f"{game}-{window}-v21-random-record"),
        "legacy_mean_best_hits": round(mean(legacy_best_values), 4),
        "v1_mean_best_hits": round(mean(v1_best_values), 4),
        "v21_mean_best_hits": round(mean(v21_best_values), 4),
        "random_mean_best_hits": round(mean(random_best_values), 4),
        "legacy_front_mean_jaccard": round(mean(legacy_jaccards), 4),
        "v1_front_mean_jaccard": round(mean(v1_jaccards), 4),
        "v21_front_mean_jaccard": round(mean(v21_jaccards), 4),
        "random_front_mean_jaccard": round(mean(random_jaccards), 4),
    }
    return {
        "game": game,
        "window": window,
        "periods": len(v21_vs_legacy_best),
        "baseline_seeds": baseline_seeds,
        "v1_generator_version": GENERATOR_V2_VERSION,
        "candidate_generator_version": GENERATOR_EXPOSURE_VERSION,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Development A/B for CEWAY V2.1 score-exposure generator")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v21_generator_ablation.json")
    args = parser.parse_args()

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows = []
    gates = {}
    for game in ("DLT", "SSQ"):
        game_rows = []
        for window in windows:
            print(f"V2.1 dev A/B {game}: periods={args.periods}, window={window}", flush=True)
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
            game_rows.append(row)
            print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)
        gates[game] = development_gate(game, game_rows)

    report = {
        "schema_version": "ceway.v2.generator-exposure-ablation.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "development_only",
        "candidate_generator_version": GENERATOR_EXPOSURE_VERSION,
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
        "gates": gates,
        "interpretation": (
            "This is a development-sample test. Passing only authorizes evaluation on a fresh historical block "
            "that excludes both the recent development block and the V1 holdout block."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gates, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
