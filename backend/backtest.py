from __future__ import annotations

import random
from statistics import mean

from engine import calculate_trends, calculate_ssq_trends
from generator import generate_plans, generate_ssq_plans
from research_v2 import (
    DLT,
    SSQ,
    bootstrap_mean_ci,
    build_freeze_manifest,
    combination_collision_audit,
    diversity_summary,
    expand_plan_tickets,
    history_through_issue,
    structure_matched_random_plan,
)
from review import review_plan, review_ssq_plan
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers


CEWAY_V2_ALGORITHM_VERSION = "CEWAY-FWD-V2.0-dev2"
DLT_MAIN_ZONES = ((1, 12), (13, 24), (25, 35))
DLT_BACK_ZONES = ((1, 6), (7, 12))
SSQ_MAIN_ZONES = ((1, 11), (12, 22), (23, 33))
SSQ_BACK_ZONES = ((1, 8), (9, 16))


def random_single_plan(issue: str, budget: int) -> dict:
    """Legacy unconstrained DLT random baseline kept for API compatibility."""
    rng = random.Random(f"ceway-dlt-random-{issue}-{budget}")
    ticket_count = max(1, budget // 2)
    items = []
    for _ in range(ticket_count):
        front = sorted(rng.sample(range(1, 36), 5))
        back = sorted(rng.sample(range(1, 13), 2))
        items.append(
            {
                "front": front,
                "back": back,
                "front_display": [f"{number:02d}" for number in front],
                "back_display": [f"{number:02d}" for number in back],
                "score": 0,
                "explanation": ["随机基线，仅用于对照，不参与推荐。"],
            }
        )
    return {
        "mode": "single",
        "strategy": "random",
        "cost": ticket_count * 2,
        "tickets": ticket_count,
        "items": items,
        "score": 0,
        "reason": "随机选号对照组。",
    }


def random_ssq_single_plan(issue: str, budget: int) -> dict:
    """Legacy unconstrained SSQ random baseline kept for API compatibility."""
    rng = random.Random(f"ceway-ssq-random-{issue}-{budget}")
    ticket_count = max(1, budget // 2)
    items = []
    for _ in range(ticket_count):
        front = sorted(rng.sample(range(1, 34), 6))
        back = sorted(rng.sample(range(1, 17), 1))
        items.append(
            {
                "front": front,
                "back": back,
                "front_display": [f"{number:02d}" for number in front],
                "back_display": [f"{number:02d}" for number in back],
                "score": 0,
                "explanation": ["随机基线，仅用于对照，不参与推荐。"],
            }
        )
    return {
        "mode": "single",
        "strategy": "random",
        "cost": ticket_count * 2,
        "tickets": ticket_count,
        "items": items,
        "score": 0,
        "reason": "随机选号对照组。",
    }


def best_key(item: dict) -> tuple[int, int, int]:
    best = item.get("best") or {}
    front_hits = best.get("front_hits", 0)
    back_hits = best.get("back_hits", 0)
    return front_hits + back_hits, front_hits, back_hits


def best_hit_units(item: dict) -> float:
    best = item.get("best") or {}
    return float(best.get("front_hits", 0) + best.get("back_hits", 0))


def summarize(items: list[dict]) -> dict:
    reviewed = len(items)
    hit_items = [item for item in items if item.get("hit_tickets", 0) > 0]
    best_item = max(items, key=best_key, default={})
    total_cost = sum(item.get("cost", 0) for item in items)
    avg_front = round(
        sum((item.get("best") or {}).get("front_hits", 0) for item in items) / max(1, reviewed),
        2,
    )
    avg_back = round(
        sum((item.get("best") or {}).get("back_hits", 0) for item in items) / max(1, reviewed),
        2,
    )
    return {
        "periods": reviewed,
        "total_cost": total_cost,
        "hit_records": len(hit_items),
        "record_hit_rate": round((len(hit_items) / max(1, reviewed)) * 100, 2),
        "best_hit": (best_item.get("best") or {}).get("hit_label", "-"),
        "best_prize_label": (best_item.get("best") or {}).get("prize_label", "-"),
        "avg_front_hits": avg_front,
        "avg_back_hits": avg_back,
    }


def ssq_summarize(items: list[dict]) -> dict:
    return summarize(items)


def _ensemble_validation(
    ceway_items: list[dict],
    baseline_ensembles: list[list[dict]],
    *,
    bootstrap_seed: str,
) -> dict:
    best_hit_uplifts = []
    record_hit_uplifts = []
    period_rows = []

    for ceway_item, baseline_reviews in zip(ceway_items, baseline_ensembles):
        ceway_best = best_hit_units(ceway_item)
        baseline_best_values = [best_hit_units(item) for item in baseline_reviews]
        baseline_best_mean = mean(baseline_best_values)
        best_uplift = ceway_best - baseline_best_mean

        ceway_record_hit = 1.0 if ceway_item.get("hit_tickets", 0) > 0 else 0.0
        baseline_record_values = [1.0 if item.get("hit_tickets", 0) > 0 else 0.0 for item in baseline_reviews]
        baseline_record_mean = mean(baseline_record_values)
        record_uplift = ceway_record_hit - baseline_record_mean

        best_hit_uplifts.append(best_uplift)
        record_hit_uplifts.append(record_uplift)
        period_rows.append(
            {
                "source_issue": ceway_item.get("source_issue"),
                "actual_issue": ceway_item.get("actual_issue"),
                "ceway_best_hit_units": ceway_best,
                "baseline_best_hit_units_mean": round(baseline_best_mean, 4),
                "best_hit_uplift": round(best_uplift, 4),
                "ceway_record_hit": ceway_record_hit,
                "baseline_record_hit_mean": round(baseline_record_mean, 4),
                "record_hit_uplift": round(record_uplift, 4),
            }
        )

    if not best_hit_uplifts:
        return {
            "baseline_type": "conditional_random_v2",
            "periods": 0,
            "best_hit_uplift": None,
            "record_hit_uplift": None,
            "status": "insufficient_data",
            "period_rows": [],
        }

    best_ci = bootstrap_mean_ci(best_hit_uplifts, seed=f"{bootstrap_seed}-best")
    record_ci = bootstrap_mean_ci(record_hit_uplifts, seed=f"{bootstrap_seed}-record")
    wins = sum(value > 0 for value in best_hit_uplifts)
    losses = sum(value < 0 for value in best_hit_uplifts)
    ties = len(best_hit_uplifts) - wins - losses

    if best_ci["high"] < 0:
        status = "negative"
    elif best_ci["low"] > 0:
        status = "positive_candidate"
    else:
        status = "inconclusive"

    return {
        "baseline_type": "conditional_random_v2",
        "periods": len(best_hit_uplifts),
        "best_hit_uplift": {
            "mean": round(float(best_ci["mean"]), 4),
            "ci95_low": round(float(best_ci["low"]), 4),
            "ci95_high": round(float(best_ci["high"]), 4),
        },
        "record_hit_uplift": {
            "mean": round(float(record_ci["mean"]), 4),
            "ci95_low": round(float(record_ci["low"]), 4),
            "ci95_high": round(float(record_ci["high"]), 4),
        },
        "win_rate": round((wins / len(best_hit_uplifts)) * 100, 2),
        "loss_rate": round((losses / len(best_hit_uplifts)) * 100, 2),
        "tie_rate": round((ties / len(best_hit_uplifts)) * 100, 2),
        "status": status,
        "period_rows": period_rows[-20:][::-1],
        "note": "positive_candidate 仅表示该回测区间的 95% Bootstrap CI 高于 0，不等于正式晋升，更不证明未来开奖可预测。",
    }


def _research_snapshot(
    *,
    game: str,
    spec,
    plan: dict,
    training: list[dict],
    actual: dict,
    budget: int,
    strategy: str,
    window: int,
) -> dict:
    tickets = expand_plan_tickets(plan, spec)
    manifest = build_freeze_manifest(
        game=game,
        target_issue=actual["issue"],
        history_cutoff_issue=training[-1]["issue"],
        algorithm_version=CEWAY_V2_ALGORITHM_VERSION,
        parameters={
            "budget": budget,
            "strategy": strategy,
            "window": window,
            "mode": plan.get("mode"),
        },
        tickets=tickets,
        budget=plan.get("cost", budget),
        seed=None,
    )
    return {
        "algorithm_version": CEWAY_V2_ALGORITHM_VERSION,
        "history_cutoff_issue": training[-1]["issue"],
        "target_issue": actual["issue"],
        "freeze_sha256": manifest["sha256"],
        "collision_audit": combination_collision_audit(tickets, training, spec),
        "diversity": {
            "front": diversity_summary(ticket["front"] for ticket in tickets),
            "back": diversity_summary(ticket["back"] for ticket in tickets),
        },
    }


def _dlt_conditional_baselines(plan: dict, source_issue: str, budget: int, seeds: int) -> list[dict]:
    return [
        structure_matched_random_plan(
            plan,
            DLT,
            seed=f"ceway-v2-dlt-{source_issue}-{budget}-{seed_index}",
            main_zones=DLT_MAIN_ZONES,
            bonus_zones=DLT_BACK_ZONES,
            main_sum_tolerance=5,
            bonus_sum_tolerance=2,
        )
        for seed_index in range(seeds)
    ]


def _ssq_conditional_baselines(plan: dict, source_issue: str, budget: int, seeds: int) -> list[dict]:
    return [
        structure_matched_random_plan(
            plan,
            SSQ,
            seed=f"ceway-v2-ssq-{source_issue}-{budget}-{seed_index}",
            main_zones=SSQ_MAIN_ZONES,
            bonus_zones=SSQ_BACK_ZONES,
            main_sum_tolerance=5,
            bonus_sum_tolerance=None,
        )
        for seed_index in range(seeds)
    ]


def build_dlt_backtest(
    history: list[dict],
    budget: int = 20,
    strategy: str = "balanced",
    periods: int = 100,
    window: int = 100,
    baseline_seeds: int = 5,
) -> dict:
    if len(history) < 31:
        return {
            "summary": summarize([]),
            "baseline": summarize([]),
            "items": [],
            "v2_validation": _ensemble_validation([], [], bootstrap_seed="dlt-empty"),
            "disclaimer": "历史数据少于 31 期，暂不能进行滚动回测。",
        }

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)
    ceway_items = []
    representative_baseline_items = []
    baseline_ensembles: list[list[dict]] = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]
        trends = calculate_trends(training, window=min(window, len(training)))
        score_table = score_front_numbers(trends)
        back_scores = score_back_numbers(trends)
        plan = generate_plans(
            budget=budget,
            strategy=strategy,
            score_table=score_table,
            back_scores=back_scores,
        )[0]
        result = review_plan(plan, actual)
        ceway_item = {
            "source_issue": source_issue,
            "history_cutoff_issue": source_issue,
            "actual_issue": actual["issue"],
            "actual_date": actual["date"],
            "strategy": strategy,
            "budget": budget,
            "algorithm_version": CEWAY_V2_ALGORITHM_VERSION,
            "research": _research_snapshot(
                game="dlt",
                spec=DLT,
                plan=plan,
                training=training,
                actual=actual,
                budget=budget,
                strategy=strategy,
                window=window,
            ),
            **result,
        }
        ceway_items.append(ceway_item)

        baseline_plans = _dlt_conditional_baselines(plan, source_issue, budget, max(1, baseline_seeds))
        baseline_reviews = []
        for seed_index, baseline_plan in enumerate(baseline_plans):
            baseline_reviews.append(
                {
                    "source_issue": source_issue,
                    "history_cutoff_issue": source_issue,
                    "actual_issue": actual["issue"],
                    "actual_date": actual["date"],
                    "strategy": "random",
                    "baseline_type": "conditional_random_v2",
                    "baseline_seed_index": seed_index,
                    "budget": budget,
                    **review_plan(baseline_plan, actual),
                }
            )
        baseline_ensembles.append(baseline_reviews)
        representative_baseline_items.append(baseline_reviews[0])

    summary = summarize(ceway_items)
    baseline = summarize(representative_baseline_items)
    summary["edge_vs_random"] = round(summary["record_hit_rate"] - baseline["record_hit_rate"], 2)
    validation = _ensemble_validation(
        ceway_items,
        baseline_ensembles,
        bootstrap_seed=f"dlt-{budget}-{strategy}-{periods}-{window}-{baseline_seeds}",
    )
    if validation.get("record_hit_uplift"):
        summary["edge_vs_conditional_random"] = round(
            validation["record_hit_uplift"]["mean"] * 100,
            2,
        )

    return {
        "config": {
            "algorithm_version": CEWAY_V2_ALGORITHM_VERSION,
            "budget": budget,
            "strategy": strategy,
            "periods": len(ceway_items),
            "window": window,
            "baseline_type": "conditional_random_v2",
            "baseline_seeds": max(1, baseline_seeds),
            "start_issue": ceway_items[0]["source_issue"] if ceway_items else None,
            "end_issue": ceway_items[-1]["actual_issue"] if ceway_items else None,
        },
        "summary": summary,
        "baseline": baseline,
        "v2_validation": validation,
        "items": ceway_items[-20:][::-1],
        "baseline_items": representative_baseline_items[-20:][::-1],
        "disclaimer": "V2 回测严格按 history_cutoff_issue 滚动，只用当时可知历史；条件随机基线逐票匹配结构。历史 uplift 与 Bootstrap 区间仅用于研究验证，不代表未来开奖概率。",
    }


def build_ssq_backtest(
    history: list[dict],
    budget: int = 20,
    strategy: str = "balanced",
    periods: int = 100,
    window: int = 100,
    baseline_seeds: int = 5,
) -> dict:
    if len(history) < 31:
        return {
            "summary": ssq_summarize([]),
            "baseline": ssq_summarize([]),
            "items": [],
            "v2_validation": _ensemble_validation([], [], bootstrap_seed="ssq-empty"),
            "disclaimer": "历史数据少于 31 期，暂不能进行滚动回测。",
        }

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)
    ceway_items = []
    representative_baseline_items = []
    baseline_ensembles: list[list[dict]] = []

    for index in range(start_index, end_index + 1):
        source_issue = history[index]["issue"]
        training = history_through_issue(history, source_issue)
        actual = history[index + 1]
        trends = calculate_ssq_trends(training, window=min(window, len(training)))
        score_table = score_ssq_front_numbers(trends)
        back_scores = score_ssq_back_numbers(trends)
        plan = generate_ssq_plans(
            budget=budget,
            strategy=strategy,
            score_table=score_table,
            back_scores=back_scores,
        )[0]
        result = review_ssq_plan(plan, actual)
        ceway_item = {
            "source_issue": source_issue,
            "history_cutoff_issue": source_issue,
            "actual_issue": actual["issue"],
            "actual_date": actual["date"],
            "strategy": strategy,
            "budget": budget,
            "algorithm_version": CEWAY_V2_ALGORITHM_VERSION,
            "research": _research_snapshot(
                game="ssq",
                spec=SSQ,
                plan=plan,
                training=training,
                actual=actual,
                budget=budget,
                strategy=strategy,
                window=window,
            ),
            **result,
        }
        ceway_items.append(ceway_item)

        baseline_plans = _ssq_conditional_baselines(plan, source_issue, budget, max(1, baseline_seeds))
        baseline_reviews = []
        for seed_index, baseline_plan in enumerate(baseline_plans):
            baseline_reviews.append(
                {
                    "source_issue": source_issue,
                    "history_cutoff_issue": source_issue,
                    "actual_issue": actual["issue"],
                    "actual_date": actual["date"],
                    "strategy": "random",
                    "baseline_type": "conditional_random_v2",
                    "baseline_seed_index": seed_index,
                    "budget": budget,
                    **review_ssq_plan(baseline_plan, actual),
                }
            )
        baseline_ensembles.append(baseline_reviews)
        representative_baseline_items.append(baseline_reviews[0])

    summary = ssq_summarize(ceway_items)
    baseline = ssq_summarize(representative_baseline_items)
    summary["edge_vs_random"] = round(summary["record_hit_rate"] - baseline["record_hit_rate"], 2)
    validation = _ensemble_validation(
        ceway_items,
        baseline_ensembles,
        bootstrap_seed=f"ssq-{budget}-{strategy}-{periods}-{window}-{baseline_seeds}",
    )
    if validation.get("record_hit_uplift"):
        summary["edge_vs_conditional_random"] = round(
            validation["record_hit_uplift"]["mean"] * 100,
            2,
        )

    return {
        "config": {
            "algorithm_version": CEWAY_V2_ALGORITHM_VERSION,
            "budget": budget,
            "strategy": strategy,
            "periods": len(ceway_items),
            "window": window,
            "baseline_type": "conditional_random_v2",
            "baseline_seeds": max(1, baseline_seeds),
            "start_issue": ceway_items[0]["source_issue"] if ceway_items else None,
            "end_issue": ceway_items[-1]["actual_issue"] if ceway_items else None,
        },
        "summary": summary,
        "baseline": baseline,
        "v2_validation": validation,
        "items": ceway_items[-20:][::-1],
        "baseline_items": representative_baseline_items[-20:][::-1],
        "disclaimer": "V2 回测严格按 history_cutoff_issue 滚动，只用当时可知历史；条件随机基线逐票匹配结构。历史 uplift 与 Bootstrap 区间仅用于研究验证，不代表未来开奖概率。",
    }
