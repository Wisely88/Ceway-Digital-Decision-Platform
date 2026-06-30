from __future__ import annotations

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


def mode_label(mode: str) -> str:
    return "胆拖" if mode == "dantuo" else "单式"


def top_explanations(numbers: list[int], score_table: list[dict], limit: int = 5) -> list[str]:
    explanation_by_number = {item["number"]: item.get("explanation", "") for item in score_table}
    return [f"{number:02d}：{explanation_by_number.get(number, '')}" for number in numbers[:limit]]


def generate_single(budget: int, score_table: list[dict], back_scores: list[dict], strategy: str = "balanced") -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    ranked_front = [item["number"] for item in score_table]
    ranked_back = [item["number"] for item in back_scores]
    tickets = []

    for index in range(ticket_count):
        front_pool = ranked_front[index:] + ranked_front[:index]
        back_pool = ranked_back[index:] + ranked_back[:index]
        front = sorted(front_pool[:5])
        back = sorted(back_pool[:2])
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
    return {
        "mode": "single",
        "strategy": strategy,
        "cost": cost,
        "tickets": ticket_count,
        "items": tickets,
        "score": score,
        "reason": plan_reason(strategy, "single", score, cost, budget),
    }


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
) -> dict:
    ranked_front = [item["number"] for item in score_table]
    ranked_back = [item["number"] for item in back_scores]
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
                back = sorted(ranked_back[:back_count])
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
        return generate_single(budget, score_table, back_scores, strategy)

    if strategy == "aggressive":
        candidates.sort(key=lambda item: (-item["cost"], -item["tickets"], -item["score"]))
    else:
        candidates.sort(key=lambda item: (-item["score"], -item["cost"], item["tickets"]))
    selected = candidates[0]
    selected["reason"] = plan_reason(strategy, "dantuo", selected["score"], selected["cost"], budget)
    return selected


def generate_strategy_plans(strategy: str, budget: int, score_table: list[dict], back_scores: list[dict]) -> list[dict]:
    if strategy == "conservative":
        return [generate_single(budget, score_table, back_scores, strategy)]

    single = generate_single(budget, score_table, back_scores, strategy)
    dantuo = generate_dantuo(budget, score_table, back_scores, strategy)
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
) -> list[dict]:
    score_table = score_table or []
    back_scores = back_scores or []
    normalized = normalize_strategy(strategy, mode)
    plans = generate_strategy_plans(normalized, budget, score_table, back_scores)

    legacy_request = strategy in LEGACY_STRATEGY_MAP or mode in LEGACY_STRATEGY_MAP
    requested_mode = strategy if strategy in {"single", "dantuo"} else mode
    if legacy_request and requested_mode == "single":
        return [generate_single(budget, score_table, back_scores, normalized)]
    if legacy_request and requested_mode == "dantuo":
        return [generate_dantuo(budget, score_table, back_scores, normalized)]
    return sorted(plans, key=lambda item: (-item["cost"], item["mode"]))
