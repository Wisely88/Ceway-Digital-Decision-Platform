from __future__ import annotations

from itertools import combinations
from math import comb


TICKET_PRICE = 2


def format_numbers(numbers: list[int]) -> list[str]:
    return [f"{number:02d}" for number in numbers]


def plan_score(front: list[int], score_table: list[dict]) -> float:
    score_by_number = {item["number"]: item["total_score"] for item in score_table}
    return round(sum(score_by_number.get(number, 0) for number in front), 2)


def generate_single(budget: int, score_table: list[dict], back_scores: list[dict]) -> dict:
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
            }
        )

    return {
        "mode": "single",
        "cost": ticket_count * TICKET_PRICE,
        "tickets": ticket_count,
        "items": tickets,
    }


def dantuo_cost(front_dan_count: int, front_tuo_count: int, back_count: int) -> tuple[int, int]:
    if front_dan_count >= 5 or front_tuo_count < 5 - front_dan_count or back_count < 2:
        return 0, 0
    ticket_count = comb(front_tuo_count, 5 - front_dan_count) * comb(back_count, 2)
    return ticket_count, ticket_count * TICKET_PRICE


def generate_dantuo(budget: int, score_table: list[dict], back_scores: list[dict]) -> dict:
    ranked_front = [item["number"] for item in score_table]
    ranked_back = [item["number"] for item in back_scores]
    candidates = []

    for dan_count in [1, 2, 3]:
        for tuo_count in range(5 - dan_count, min(10, len(ranked_front) - dan_count) + 1):
            back_count = 2
            ticket_count, cost = dantuo_cost(dan_count, tuo_count, back_count)
            if cost == 0 or cost > budget:
                continue
            front_dan = sorted(ranked_front[:dan_count])
            front_tuo = sorted(ranked_front[dan_count : dan_count + tuo_count])
            back = sorted(ranked_back[:back_count])
            candidates.append(
                {
                    "mode": "dantuo",
                    "cost": cost,
                    "tickets": ticket_count,
                    "front_dan": front_dan,
                    "front_tuo": front_tuo,
                    "back": back,
                    "front_dan_display": format_numbers(front_dan),
                    "front_tuo_display": format_numbers(front_tuo),
                    "back_display": format_numbers(back),
                    "score": plan_score(front_dan + front_tuo, score_table),
                }
            )

    if not candidates:
        return generate_single(budget, score_table, back_scores)

    candidates.sort(key=lambda item: (-item["score"], -item["cost"], item["tickets"]))
    return candidates[0]


def generate_plans(budget: int, mode: str, score_table: list[dict], back_scores: list[dict]) -> list[dict]:
    plans = [generate_single(budget, score_table, back_scores)]
    dantuo = generate_dantuo(budget, score_table, back_scores)
    if dantuo["mode"] == "dantuo":
        plans.append(dantuo)

    if mode == "single":
        return [plans[0]]
    if mode == "dantuo":
        return [dantuo]
    return sorted(plans, key=lambda item: (-item["cost"], item["mode"]))

