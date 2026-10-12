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
from fixed_window_v24 import (  # noqa: E402
    FIXED_WINDOW_V24,
    FIXED_WINDOW_V24_VERSION,
    generate_dlt_fixed100_single,
    generate_ssq_fixed100_single,
)
from generator import generate_plans, generate_ssq_plans  # noqa: E402
from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single  # noqa: E402
from random_control_v2 import robust_structure_matched_random_plan  # noqa: E402
from research_v2 import DLT, SSQ, bootstrap_mean_ci, diversity_summary, expand_plan_tickets, history_through_issue  # noqa: E402
from review import review_plan, review_ssq_plan  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402


EXCLUDED_RECENT_POINTS = 150
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


def holdout_history(history: list[dict], excluded_recent_points: int) -> list[dict]:
    if excluded_recent_points < EXCLUDED_RECENT_POINTS:
        raise ValueError("V2.4 fresh validation must exclude at least 150 recent outcomes")
    if len(history) <= excluded_recent_points + 32:
        raise ValueError("not enough history for V2.4 fresh validation")
    return history[:-excluded_recent_points]


def block_provenance(history: list[dict], periods: int, excluded_recent_points: int) -> dict:
    if excluded_recent_points < periods * 3:
        raise ValueError("must exclude development + V1 holdout + V2.1 holdout")
    n = len(history)

    def block(end_exclusive: int, count: int) -> dict:
        rows = history[end_exclusive - count:end_exclusive]
        return {"count": len(rows), "first_issue": rows[0]["issue"], "last_issue": rows[-1]["issue"]}

    return {
        "development_block": block(n, periods),
        "v1_consumed_holdout_block": block(n - periods, periods),
        "v21_consumed_holdout_block": block(n - periods * 2, periods),
        "v24_fresh_holdout_block": block(n - excluded_recent_points, periods),
        "v22_holdout_job": "skipped",
        "v23_holdout_job": "skipped",
        "blocks_overlap": False,
    }


def gate(game: str, metrics: dict) -> dict:
    target = 0.15 if game == "DLT" else 0.18
    structural_ok = metrics["candidate_front_mean_jaccard"] <= target
    legacy_significant = metrics["candidate_vs_legacy_w100_best_hit"]["ci95_low"] > 0
    random_ok = metrics["candidate_vs_random_best_hit"]["ci95_high"] >= 0
    alt50_ok = metrics["candidate_vs_v21_w50_best_hit"]["ci95_high"] >= 0
    alt200_ok = metrics["candidate_vs_v21_w200_best_hit"]["ci95_high"] >= 0

    if structural_ok and legacy_significant and random_ok and alt50_ok and alt200_ok:
        decision = "ADVANCE_TO_FORWARD"
        reason = "fixed-w100 passes every pre-registered fresh validation condition"
    elif not structural_ok or not random_ok or metrics["candidate_vs_legacy_w100_best_hit"]["ci95_high"] < 0:
        decision = "REJECT"
        reason = "fixed-w100 triggers a pre-registered rejection condition"
    else:
        decision = "HOLD"
        reason = "fixed-w100 fresh evidence is mixed; do not advance"

    return {
        "decision": decision,
        "reason": reason,
        "target_front_mean_jaccard": target,
        "structural_ok": structural_ok,
        "legacy_w100_ci_low_positive": legacy_significant,
        "random_not_significantly_worse": random_ok,
        "not_significantly_worse_than_v21_w50": alt50_ok,
        "not_significantly_worse_than_v21_w200": alt200_ok,
    }


def run_game(*, game: str, history: list[dict], periods: int, baseline_seeds: int, budget: int, strategy: str) -> dict:
    if game == "DLT":
        spec = DLT
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        legacy_builder = generate_plans
        candidate_builder = generate_dlt_fixed100_single
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
        candidate_builder = generate_ssq_fixed100_single
        v21_builder = generate_ssq_exposure_single
        reviewer = review_ssq_plan
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_sum_tolerance = None

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)

    vs_legacy = []
    vs_random = []
    vs_alt50 = []
    vs_alt200 = []
    ticket_vs_random = []
    record_vs_random = []
    candidate_best_values = []
    random_best_values = []
    jaccards = []
    random_jaccards = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]

        score_tables = {}
        back_tables = {}
        for window in (50, 100, 200):
            trends = trend_builder(training, window=min(window, len(training)))
            score_tables[window] = front_scorer(trends)
            back_tables[window] = back_scorer(trends)

        candidate = candidate_builder(budget, score_tables[100], back_tables[100], strategy)
        candidate_review = reviewer(candidate, actual)
        candidate_best = best_hit_units(candidate_review)

        legacy = legacy_builder(
            budget=budget,
            strategy=strategy,
            score_table=score_tables[100],
            back_scores=back_tables[100],
        )[0]
        alt50 = v21_builder(budget, score_tables[50], back_tables[50], strategy)
        alt200 = v21_builder(budget, score_tables[200], back_tables[200], strategy)

        legacy_best = best_hit_units(reviewer(legacy, actual))
        alt50_best = best_hit_units(reviewer(alt50, actual))
        alt200_best = best_hit_units(reviewer(alt200, actual))

        random_plans = []
        random_reviews = []
        for seed_index in range(max(1, baseline_seeds)):
            random_plan = robust_structure_matched_random_plan(
                candidate,
                spec,
                seed=f"v24-fixed100-{game}-{source_issue}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_sum_tolerance,
            )
            random_plans.append(random_plan)
            random_reviews.append(reviewer(random_plan, actual))

        random_best = mean(best_hit_units(item) for item in random_reviews)
        vs_legacy.append(candidate_best - legacy_best)
        vs_random.append(candidate_best - random_best)
        vs_alt50.append(candidate_best - alt50_best)
        vs_alt200.append(candidate_best - alt200_best)
        ticket_vs_random.append(mean_ticket_hit_units(candidate_review) - mean(mean_ticket_hit_units(item) for item in random_reviews))
        record_vs_random.append(record_hit(candidate_review) - mean(record_hit(item) for item in random_reviews))
        candidate_best_values.append(candidate_best)
        random_best_values.append(random_best)
        jaccards.append(front_jaccard(candidate, spec))
        random_jaccards.append(mean(front_jaccard(plan, spec) for plan in random_plans))

    metrics = {
        "candidate_vs_legacy_w100_best_hit": ci(vs_legacy, f"v24-{game}-legacy100"),
        "candidate_vs_random_best_hit": ci(vs_random, f"v24-{game}-random"),
        "candidate_vs_v21_w50_best_hit": ci(vs_alt50, f"v24-{game}-v21w50"),
        "candidate_vs_v21_w200_best_hit": ci(vs_alt200, f"v24-{game}-v21w200"),
        "candidate_vs_random_mean_ticket_hit": ci(ticket_vs_random, f"v24-{game}-random-ticket"),
        "candidate_vs_random_record_hit": ci(record_vs_random, f"v24-{game}-random-record"),
        "candidate_mean_best_hits": round(mean(candidate_best_values), 4),
        "random_mean_best_hits": round(mean(random_best_values), 4),
        "candidate_front_mean_jaccard": round(mean(jaccards), 4),
        "random_front_mean_jaccard": round(mean(random_jaccards), 4),
    }
    return {
        "game": game,
        "periods": len(vs_legacy),
        "fixed_window": FIXED_WINDOW_V24,
        "baseline_seeds": baseline_seeds,
        "candidate_generator_version": FIXED_WINDOW_V24_VERSION,
        "metrics": metrics,
        "gate": gate(game, metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh-only validation for CEWAY V2.4 fixed window 100")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--excluded-recent-points", type=int, default=EXCLUDED_RECENT_POINTS)
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v24_fixed100_holdout.json")
    args = parser.parse_args()

    full_histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    histories = {game: holdout_history(history, args.excluded_recent_points) for game, history in full_histories.items()}
    provenance = {game: block_provenance(history, args.periods, args.excluded_recent_points) for game, history in full_histories.items()}

    rows = []
    for game in ("DLT", "SSQ"):
        print(f"V2.4 FRESH {game}: fixed_window=100, periods={args.periods}, excluded={args.excluded_recent_points}", flush=True)
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
        "schema_version": "ceway.v2.4.fixed100-fresh-holdout.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "fresh_only_post_hoc_hypothesis_validation",
        "candidate_generator_version": FIXED_WINDOW_V24_VERSION,
        "hypothesis_provenance": (
            "The 100-period window was selected after inspecting consumed V2.1/V2.2/V2.3 research. Therefore this report's "
            "excluded=150 block is the first admissible promotion evidence for V2.4."
        ),
        "settings": {
            "periods": args.periods,
            "fixed_window": FIXED_WINDOW_V24,
            "excluded_recent_points": args.excluded_recent_points,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "block_provenance": provenance,
        "rows": rows,
        "all_games_advance": all(row["gate"]["decision"] == "ADVANCE_TO_FORWARD" for row in rows),
        "interpretation": (
            "Passing authorizes only unchanged prospective forward-shadow validation. It is not production authorization "
            "and does not establish predictive certainty."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
