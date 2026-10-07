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
from fixed_window_v24 import generate_dlt_fixed100_single, generate_ssq_fixed100_single  # noqa: E402
from multiregime_v25 import DLT, SSQ, MULTIREGIME_V25_VERSION, generate_multiregime_plan  # noqa: E402
from predictor_v9 import DLT as V9_DLT, SSQ as V9_SSQ, generate_prediction_v9  # noqa: E402
from random_control_v2 import robust_structure_matched_random_plan  # noqa: E402
from research_v2 import bootstrap_mean_ci, diversity_summary, expand_plan_tickets, history_through_issue  # noqa: E402
from review import review_plan, review_ssq_plan  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402


DLT_MAIN_ZONES = ((1, 12), (13, 24), (25, 35))
DLT_BACK_ZONES = ((1, 6), (7, 12))
SSQ_MAIN_ZONES = ((1, 11), (12, 22), (23, 33))
SSQ_BACK_ZONES = ((1, 8), (9, 16))


def best_hit(review: dict) -> float:
    best = review.get("best") or {}
    return float(best.get("front_hits", 0) + best.get("back_hits", 0))


def mean_ticket_hit(review: dict) -> float:
    details = review.get("details") or []
    if not details:
        return 0.0
    return mean(float(row.get("front_hits", 0) + row.get("back_hits", 0)) for row in details)


def record_hit(review: dict) -> float:
    return 1.0 if review.get("hit_tickets", 0) else 0.0


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


def _v9_plan(history: list[dict], game: str, budget: int) -> dict:
    spec = V9_DLT if game == "DLT" else V9_SSQ
    return generate_prediction_v9(history, spec, budget=budget, seed="v25-stress-v9", history_cutoff_issue=history[-1]["issue"])


def run_game(game: str, history: list[dict], *, periods: int, excluded_recent: int, baseline_seeds: int, budget: int) -> dict:
    if len(history) <= excluded_recent + periods + 35:
        raise ValueError("not enough history for V2.5 retrospective stress block")
    working = history[:-excluded_recent]
    start = len(working) - periods - 1
    end = len(working) - 2

    if game == "DLT":
        spec = DLT
        reviewer = review_plan
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        v24_builder = generate_dlt_fixed100_single
        main_zones = DLT_MAIN_ZONES
        bonus_zones = DLT_BACK_ZONES
        bonus_tol = 2
    else:
        spec = SSQ
        reviewer = review_ssq_plan
        trend_builder = calculate_ssq_trends
        front_scorer = score_ssq_front_numbers
        back_scorer = score_ssq_back_numbers
        v24_builder = generate_ssq_fixed100_single
        main_zones = SSQ_MAIN_ZONES
        bonus_zones = SSQ_BACK_ZONES
        bonus_tol = None

    diffs_random_best = []
    diffs_random_ticket = []
    diffs_random_record = []
    diffs_v24_best = []
    diffs_v9_best = []
    candidate_best = []
    v24_best_values = []
    v9_best_values = []
    random_best_values = []
    jaccards = []
    random_jaccards = []
    scarcity_top_quartile_hits = []
    scarcity_actual_percentiles = []
    evidence_actual_percentiles = []

    for index in range(start, end + 1):
        source_issue = working[index]["issue"]
        training = history_through_issue(working, source_issue)
        actual = working[index + 1]
        v25 = generate_multiregime_plan(training, spec, budget=budget, history_cutoff_issue=source_issue)
        v25_review = reviewer(v25, actual)

        trends = trend_builder(training, window=min(100, len(training)))
        v24 = v24_builder(budget, front_scorer(trends), back_scorer(trends), "balanced")
        v24_review = reviewer(v24, actual)
        v9 = _v9_plan(training, game, budget)
        v9_review = reviewer(v9, actual)

        random_reviews = []
        random_plans = []
        for seed_index in range(max(1, baseline_seeds)):
            random_plan = robust_structure_matched_random_plan(
                v25,
                spec,
                seed=f"v25-{game}-{source_issue}-{seed_index}",
                main_zones=main_zones,
                bonus_zones=bonus_zones,
                main_sum_tolerance=5,
                bonus_sum_tolerance=bonus_tol,
            )
            random_plans.append(random_plan)
            random_reviews.append(reviewer(random_plan, actual))

        v25_best = best_hit(v25_review)
        random_best = mean(best_hit(row) for row in random_reviews)
        diffs_random_best.append(v25_best - random_best)
        diffs_random_ticket.append(mean_ticket_hit(v25_review) - mean(mean_ticket_hit(row) for row in random_reviews))
        diffs_random_record.append(record_hit(v25_review) - mean(record_hit(row) for row in random_reviews))
        diffs_v24_best.append(v25_best - best_hit(v24_review))
        diffs_v9_best.append(v25_best - best_hit(v9_review))
        candidate_best.append(v25_best)
        v24_best_values.append(best_hit(v24_review))
        v9_best_values.append(best_hit(v9_review))
        random_best_values.append(random_best)
        jaccards.append(front_jaccard(v25, spec))
        random_jaccards.append(mean(front_jaccard(plan, spec) for plan in random_plans))

        table = {row["number"]: row for row in v25["front_regime_table"]}
        pool = spec.main_pool
        threshold = max(1, int(round(pool * 0.25)))
        actual_front = actual.get("front", [])
        scarcity_top_quartile_hits.append(sum(table[number]["scarcity_rank"] <= threshold for number in actual_front))
        scarcity_actual_percentiles.extend(1.0 - (table[number]["scarcity_rank"] - 1) / max(1, pool - 1) for number in actual_front)
        evidence_actual_percentiles.extend(1.0 - (table[number]["evidence_rank"] - 1) / max(1, pool - 1) for number in actual_front)

    metrics = {
        "v25_vs_random_best_hit": ci(diffs_random_best, f"v25-{game}-random-best"),
        "v25_vs_random_mean_ticket_hit": ci(diffs_random_ticket, f"v25-{game}-random-ticket"),
        "v25_vs_random_record_hit": ci(diffs_random_record, f"v25-{game}-random-record"),
        "v25_vs_v24_best_hit": ci(diffs_v24_best, f"v25-{game}-v24"),
        "v25_vs_v9_best_hit": ci(diffs_v9_best, f"v25-{game}-v9"),
        "v25_mean_best_hit": round(mean(candidate_best), 4),
        "v24_mean_best_hit": round(mean(v24_best_values), 4),
        "v9_mean_best_hit": round(mean(v9_best_values), 4),
        "random_mean_best_hit": round(mean(random_best_values), 4),
        "v25_front_mean_jaccard": round(mean(jaccards), 4),
        "random_front_mean_jaccard": round(mean(random_jaccards), 4),
        "actual_front_mean_scarcity_percentile": round(mean(scarcity_actual_percentiles), 4),
        "actual_front_mean_evidence_percentile": round(mean(evidence_actual_percentiles), 4),
        "actual_front_mean_top_quartile_scarcity_hits_per_draw": round(mean(scarcity_top_quartile_hits), 4),
    }

    random_ci = metrics["v25_vs_random_best_hit"]
    v24_ci = metrics["v25_vs_v24_best_hit"]
    if random_ci["ci95_low"] > 0 and v24_ci["ci95_low"] > 0:
        decision = "PROMISING_RETROSPECTIVE"
    elif random_ci["ci95_high"] < 0 or v24_ci["ci95_high"] < 0:
        decision = "REJECT_RETROSPECTIVE"
    else:
        decision = "HOLD_RETROSPECTIVE"

    return {
        "game": game,
        "periods": periods,
        "excluded_recent": excluded_recent,
        "candidate_version": MULTIREGIME_V25_VERSION,
        "metrics": metrics,
        "decision": decision,
        "evidence_warning": "Retrospective stress evidence only. Recent scarcity observations motivated the hypothesis, so this run cannot authorize production or claim fresh predictive uplift.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CEWAY V2.5 multi-regime retrospective stress test")
    parser.add_argument("--periods", type=int, default=60)
    parser.add_argument("--excluded-recent", type=int, default=200)
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v25_multiregime_stress.json")
    args = parser.parse_args()

    rows = [
        run_game("DLT", load_dlt_history(), periods=args.periods, excluded_recent=args.excluded_recent, baseline_seeds=args.baseline_seeds, budget=args.budget),
        run_game("SSQ", load_ssq_history(), periods=args.periods, excluded_recent=args.excluded_recent, baseline_seeds=args.baseline_seeds, budget=args.budget),
    ]
    report = {
        "schema_version": "ceway.v2.5.multiregime-retrospective-stress.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_version": MULTIREGIME_V25_VERSION,
        "settings": vars(args) | {"output": str(args.output)},
        "rows": rows,
        "overall_decision": "PROMISING_RETROSPECTIVE" if all(row["decision"] == "PROMISING_RETROSPECTIVE" for row in rows) else ("REJECT_RETROSPECTIVE" if any(row["decision"] == "REJECT_RETROSPECTIVE" for row in rows) else "HOLD_RETROSPECTIVE"),
        "guardrail": "No production promotion from this report. V2.5 parameters are pre-registered and must be frozen unchanged before any future prospective shadow result is admissible.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
