from __future__ import annotations

from itertools import combinations
from math import comb


TICKET_PRICE = 2
VALID_STRATEGIES = {"conservative", "balanced", "aggressive"}
LEGACY_STRATEGY_MAP = {
    "single": "conservative",
    "dantuo": "balanced",
    "auto": "balanced",
}


def format_numbers(numbers: list[int]) -> list[str]:
    return [f"{number:02d}" for number in numbers]


def plan_score(front: list[int], score_table: list[dict]) -> float:
    score_by_number = {item["number"]: item["total_score"] for item in score_table}
    return round(sum(score_by_number.get(number, 0) for number in front), 2)


def normalize_strategy(strategy: str | None = None, mode: str | None = None) -> str:
    requested = strategy or mode or "balanced"
    return LEGACY_STRATEGY_MAP.get(requested, requested if requested in VALID_STRATEGIES else "balanced")


def plan_reason(strategy: str, mode: str, score: float, cost: int, budget: int) -> str:
    ratio = round((cost / budget) * 100, 1) if budget > 0 else 0
    if strategy == "conservative":
        return f"保守策略优先控制复杂度，采用单式分散组合；综合评分 {score}，预算占用 {ratio}%。"
    if strategy == "aggressive":
        return f"激进策略提高覆盖面并尽量贴近预算上限，当前{mode_label(mode)}方案综合评分 {score}，预算占用 {ratio}%。"
    return f"均衡策略在评分质量和预算使用之间折中，当前{mode_label(mode)}方案综合评分 {score}，预算占用 {ratio}%。"


def budget_analysis(cost: int, budget: int, mode: str) -> dict:
    unused = max(0, budget - cost)
    utilization = round((cost / budget) * 100, 1) if budget > 0 else 0
    if unused == 0:
        explanation = "本方案费用刚好等于本期预算。"
    elif mode == "dantuo":
        explanation = f"胆拖费用由组合公式决定，当前预算内最接近的合法方案为 {cost} 元，剩余 {unused} 元不强行加注。"
    else:
        explanation = f"单式按 2 元/注生成，当前使用 {cost} 元，剩余 {unused} 元。"
    return {
        "budget": budget,
        "cost": cost,
        "unused": unused,
        "utilization": utilization,
        "explanation": explanation,
    }


def attach_budget_analysis(plan: dict, budget: int) -> dict:
    plan["budget_analysis"] = budget_analysis(plan.get("cost", 0), budget, plan.get("mode", "single"))
    return plan


def mode_label(mode: str) -> str:
    return "胆拖" if mode == "dantuo" else "单式"


def top_explanations(numbers: list[int], score_table: list[dict], limit: int = 5) -> list[str]:
    explanation_by_number = {item["number"]: item.get("explanation", "") for item in score_table}
    return [f"{number:02d}：{explanation_by_number.get(number, '')}" for number in numbers[:limit]]


def rotate(items: list, variant: int = 0) -> list:
    if not items:
        return items
    offset = variant % len(items)
    return items[offset:] + items[:offset]


def budget_fit_sort_key(item: dict) -> tuple:
    return (-item["cost"], -item.get("tickets", 0), -item.get("score", 0))


def has_consecutive_numbers(numbers: tuple[int, ...] | list[int]) -> bool:
    ordered = sorted(numbers)
    return any(current - previous == 1 for previous, current in zip(ordered, ordered[1:]))


def select_dlt_back_numbers(ranked_back: list[int], count: int, excluded: list[int]) -> list[int]:
    pool = [number for number in ranked_back if number not in set(excluded)]
    if len(pool) < count:
        pool = ranked_back
    candidate_band = pool[: min(len(pool), count + 6)]
    candidates = list(combinations(candidate_band, count))
    separated = [candidate for candidate in candidates if not has_consecutive_numbers(candidate)]
    selected = separated[0] if separated else (candidates[0] if candidates else tuple(pool[:count]))
    return sorted(selected)


def generate_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
    variant: int = 0,
) -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    ranked_front = rotate([item["number"] for item in score_table], variant)
    ranked_back = rotate([item["number"] for item in back_scores], variant)
    tickets = []

    for index in range(ticket_count):
        front_pool = ranked_front[index:] + ranked_front[:index]
        back_pool = ranked_back[index:] + ranked_back[:index]
        front = sorted(front_pool[:5])
        back = select_dlt_back_numbers(back_pool, 2, front)
        tickets.append(
            {
                "front": front,
                "back": back,
                "front_display": format_numbers(front),
                "back_display": format_numbers(back),
                "score": plan_score(front, score_table),
                "explanation": top_explanations(front, score_table),
            }
        )

    score = round(sum(item["score"] for item in tickets), 2)
    cost = ticket_count * TICKET_PRICE
    return attach_budget_analysis({
        "mode": "single",
        "strategy": strategy,
        "cost": cost,
        "tickets": ticket_count,
        "items": tickets,
        "score": score,
        "reason": plan_reason(strategy, "single", score, cost, budget),
    }, budget)


def dantuo_cost(front_dan_count: int, front_tuo_count: int, back_count: int) -> tuple[int, int]:
    if front_dan_count >= 5 or front_tuo_count < 5 - front_dan_count or back_count < 2:
        return 0, 0
    ticket_count = comb(front_tuo_count, 5 - front_dan_count) * comb(back_count, 2)
    return ticket_count, ticket_count * TICKET_PRICE


def generate_dantuo(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
    variant: int = 0,
) -> dict:
    ranked_front = rotate([item["number"] for item in score_table], variant)
    ranked_back = rotate([item["number"] for item in back_scores], variant)
    candidates = []
    dan_counts = [2, 3] if strategy == "balanced" else [1, 2, 3]
    max_tuo = 10 if strategy != "aggressive" else 12
    max_back = 2 if strategy != "aggressive" else min(4, len(ranked_back))

    for dan_count in dan_counts:
        for tuo_count in range(5 - dan_count, min(max_tuo, len(ranked_front) - dan_count) + 1):
            for back_count in range(2, max_back + 1):
                ticket_count, cost = dantuo_cost(dan_count, tuo_count, back_count)
                if cost == 0 or cost > budget:
                    continue
                front_dan = sorted(ranked_front[:dan_count])
                front_tuo = sorted(ranked_front[dan_count : dan_count + tuo_count])
                back = select_dlt_back_numbers(ranked_back, back_count, front_dan)
                front_score = plan_score(front_dan + front_tuo, score_table)
                candidates.append(
                    {
                        "mode": "dantuo",
                        "strategy": strategy,
                        "cost": cost,
                        "tickets": ticket_count,
                        "front_dan": front_dan,
                        "front_tuo": front_tuo,
                        "back": back,
                        "front_dan_display": format_numbers(front_dan),
                        "front_tuo_display": format_numbers(front_tuo),
                        "back_display": format_numbers(back),
                        "score": front_score,
                        "explanation": top_explanations(front_dan + front_tuo, score_table),
                    }
                )

    if not candidates:
        return generate_single(budget, score_table, back_scores, strategy, variant)

    if strategy == "aggressive":
        candidates.sort(key=lambda item: (-item["cost"], -item["tickets"], -item["score"]))
    else:
        candidates.sort(key=budget_fit_sort_key)
    selected = candidates[0]
    selected["reason"] = plan_reason(strategy, "dantuo", selected["score"], selected["cost"], budget)
    return attach_budget_analysis(selected, budget)


def generate_strategy_plans(
    strategy: str,
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    variant: int = 0,
) -> list[dict]:
    if strategy == "conservative":
        return [generate_single(budget, score_table, back_scores, strategy, variant)]

    single = generate_single(budget, score_table, back_scores, strategy, variant)
    dantuo = generate_dantuo(budget, score_table, back_scores, strategy, variant)
    plans = [single]
    if dantuo["mode"] == "dantuo":
        plans.insert(0, dantuo)
    return plans


def generate_plans(
    budget: int,
    strategy: str = "balanced",
    score_table: list[dict] | None = None,
    back_scores: list[dict] | None = None,
    mode: str | None = None,
    variant: int = 0,
) -> list[dict]:
    score_table = score_table or []
    back_scores = back_scores or []
    normalized = normalize_strategy(strategy, mode)
    plans = generate_strategy_plans(normalized, budget, score_table, back_scores, variant)

    legacy_request = strategy in LEGACY_STRATEGY_MAP or mode in LEGACY_STRATEGY_MAP
    requested_mode = strategy if strategy in {"single", "dantuo"} else mode
    if legacy_request and requested_mode == "single":
        return [generate_single(budget, score_table, back_scores, normalized, variant)]
    if legacy_request and requested_mode == "dantuo":
        return [generate_dantuo(budget, score_table, back_scores, normalized, variant)]
    return plans


# --- SSQ 双色球生成函数 ---

def ssq_format_numbers(numbers: list[int]) -> list[str]:
    return [f"{number:02d}" for number in numbers]


def ssq_plan_score(front: list[int], score_table: list[dict]) -> float:
    score_by_number = {item["number"]: item["total_score"] for item in score_table}
    return round(sum(score_by_number.get(number, 0) for number in front), 2)


def ssq_plan_reason(strategy: str, mode: str, score: float, cost: int, budget: int) -> str:
    ratio = round((cost / budget) * 100, 1) if budget > 0 else 0
    if strategy == "conservative":
        return f"保守策略优先控制复杂度，采用单式分散组合；综合评分 {score}，预算占用 {ratio}%。"
    if strategy == "aggressive":
        return f"激进策略提高覆盖面并尽量贴近预算上限，当前{mode_label(mode)}方案综合评分 {score}，预算占用 {ratio}%。"
    return f"均衡策略在评分质量和预算使用之间折中，当前{mode_label(mode)}方案综合评分 {score}，预算占用 {ratio}%。"


def ssq_top_explanations(numbers: list[int], score_table: list[dict], limit: int = 5) -> list[str]:
    explanation_by_number = {item["number"]: item.get("explanation", "") for item in score_table}
    return [f"{number:02d}：{explanation_by_number.get(number, '')}" for number in numbers[:limit]]


def generate_ssq_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
    variant: int = 0,
) -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    ranked_front = rotate([item["number"] for item in score_table], variant)
    ranked_back = rotate([item["number"] for item in back_scores], variant)
    tickets = []

    for index in range(ticket_count):
        front_pool = ranked_front[index:] + ranked_front[:index]
        back_pool = ranked_back[index:] + ranked_back[:index]
        front = sorted(front_pool[:6])
        back = sorted(back_pool[:1])
        tickets.append(
            {
                "front": front,
                "back": back,
                "front_display": ssq_format_numbers(front),
                "back_display": ssq_format_numbers(back),
                "score": ssq_plan_score(front, score_table),
                "explanation": ssq_top_explanations(front, score_table),
            }
        )

    score = round(sum(item["score"] for item in tickets), 2)
    cost = ticket_count * TICKET_PRICE
    return attach_budget_analysis({
        "mode": "single",
        "strategy": strategy,
        "cost": cost,
        "tickets": ticket_count,
        "items": tickets,
        "score": score,
        "reason": ssq_plan_reason(strategy, "single", score, cost, budget),
    }, budget)


def ssq_dantuo_cost(front_dan_count: int, front_tuo_count: int, back_count: int) -> tuple[int, int]:
    if front_dan_count >= 6 or front_tuo_count < 6 - front_dan_count or back_count < 1:
        return 0, 0
    ticket_count = comb(front_tuo_count, 6 - front_dan_count) * back_count
    return ticket_count, ticket_count * TICKET_PRICE


def generate_ssq_dantuo(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
    variant: int = 0,
) -> dict:
    ranked_front = rotate([item["number"] for item in score_table], variant)
    ranked_back = rotate([item["number"] for item in back_scores], variant)
    candidates = []
    dan_counts = [2, 3] if strategy == "balanced" else [1, 2, 3]
    max_tuo = 12 if strategy != "aggressive" else 15
    max_back = 1 if strategy != "aggressive" else min(3, len(ranked_back))

    for dan_count in dan_counts:
        for tuo_count in range(6 - dan_count, min(max_tuo, len(ranked_front) - dan_count) + 1):
            for back_count in range(1, max_back + 1):
                ticket_count, cost = ssq_dantuo_cost(dan_count, tuo_count, back_count)
                if cost == 0 or cost > budget:
                    continue
                front_dan = sorted(ranked_front[:dan_count])
                front_tuo = sorted(ranked_front[dan_count : dan_count + tuo_count])
                back = sorted(ranked_back[:back_count])
                front_score = ssq_plan_score(front_dan + front_tuo, score_table)
                candidates.append(
                    {
                        "mode": "dantuo",
                        "strategy": strategy,
                        "cost": cost,
                        "tickets": ticket_count,
                        "front_dan": front_dan,
                        "front_tuo": front_tuo,
                        "back": back,
                        "front_dan_display": ssq_format_numbers(front_dan),
                        "front_tuo_display": ssq_format_numbers(front_tuo),
                        "back_display": ssq_format_numbers(back),
                        "score": front_score,
                        "explanation": ssq_top_explanations(front_dan + front_tuo, score_table),
                    }
                )

    if not candidates:
        return generate_ssq_single(budget, score_table, back_scores, strategy, variant)

    if strategy == "aggressive":
        candidates.sort(key=lambda item: (-item["cost"], -item["tickets"], -item["score"]))
    else:
        candidates.sort(key=budget_fit_sort_key)
    selected = candidates[0]
    selected["reason"] = ssq_plan_reason(strategy, "dantuo", selected["score"], selected["cost"], budget)
    return attach_budget_analysis(selected, budget)


def generate_ssq_strategy_plans(
    strategy: str,
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    variant: int = 0,
) -> list[dict]:
    if strategy == "conservative":
        return [generate_ssq_single(budget, score_table, back_scores, strategy, variant)]

    single = generate_ssq_single(budget, score_table, back_scores, strategy, variant)
    dantuo = generate_ssq_dantuo(budget, score_table, back_scores, strategy, variant)
    plans = [single]
    if dantuo["mode"] == "dantuo":
        plans.insert(0, dantuo)
    return plans


def generate_ssq_plans(
    budget: int,
    strategy: str = "balanced",
    score_table: list[dict] | None = None,
    back_scores: list[dict] | None = None,
    mode: str | None = None,
    variant: int = 0,
) -> list[dict]:
    score_table = score_table or []
    back_scores = back_scores or []
    normalized = normalize_strategy(strategy, mode)
    plans = generate_ssq_strategy_plans(normalized, budget, score_table, back_scores, variant)

    legacy_request = strategy in LEGACY_STRATEGY_MAP or mode in LEGACY_STRATEGY_MAP
    requested_mode = strategy if strategy in {"single", "dantuo"} else mode
    if legacy_request and requested_mode == "single":
        return [generate_ssq_single(budget, score_table, back_scores, normalized, variant)]
    if legacy_request and requested_mode == "dantuo":
        return [generate_ssq_dantuo(budget, score_table, back_scores, normalized, variant)]
    return plans
