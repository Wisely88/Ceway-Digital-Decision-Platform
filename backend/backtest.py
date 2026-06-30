from __future__ import annotations

import random

from engine import calculate_trends
from generator import generate_plans
from review import review_plan
from scorer import score_back_numbers, score_front_numbers


def random_single_plan(issue: str, budget: int) -> dict:
    rng = random.Random(f"ceway-dlt-random-{issue}-{budget}")
    ticket_count = max(1, budget // 2)
    items = []
    for index in range(ticket_count):
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


def best_key(item: dict) -> tuple[int, int, int]:
    best = item.get("best") or {}
    front_hits = best.get("front_hits", 0)
    back_hits = best.get("back_hits", 0)
    return front_hits + back_hits, front_hits, back_hits


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


def build_dlt_backtest(
    history: list[dict],
    budget: int = 20,
    strategy: str = "balanced",
    periods: int = 100,
    window: int = 100,
) -> dict:
    if len(history) < 31:
        return {
            "summary": summarize([]),
            "baseline": summarize([]),
            "items": [],
            "disclaimer": "历史数据少于 31 期，暂不能进行滚动回测。",
        }

    end_index = len(history) - 2
    start_index = max(30, end_index - periods + 1)
    cbgo_items = []
    random_items = []

    for index in range(start_index, end_index + 1):
        training = history[: index + 1]
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
        cbgo_items.append(
            {
                "source_issue": training[-1]["issue"],
                "actual_issue": actual["issue"],
                "actual_date": actual["date"],
                "strategy": strategy,
                "budget": budget,
                **result,
            }
        )

        baseline_plan = random_single_plan(training[-1]["issue"], budget)
        random_items.append(
            {
                "source_issue": training[-1]["issue"],
                "actual_issue": actual["issue"],
                "actual_date": actual["date"],
                "strategy": "random",
                "budget": budget,
                **review_plan(baseline_plan, actual),
            }
        )

    summary = summarize(cbgo_items)
    baseline = summarize(random_items)
    summary["edge_vs_random"] = round(summary["record_hit_rate"] - baseline["record_hit_rate"], 2)

    return {
        "config": {
            "budget": budget,
            "strategy": strategy,
            "periods": len(cbgo_items),
            "window": window,
            "start_issue": cbgo_items[0]["source_issue"] if cbgo_items else None,
            "end_issue": cbgo_items[-1]["actual_issue"] if cbgo_items else None,
        },
        "summary": summary,
        "baseline": baseline,
        "items": cbgo_items[-20:][::-1],
        "baseline_items": random_items[-20:][::-1],
        "disclaimer": "历史回测是把当前规则滚动应用到过去数据，仅用于验证流程稳定性和匹配统计，不代表未来开奖概率。",
    }
