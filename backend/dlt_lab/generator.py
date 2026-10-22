from __future__ import annotations

from itertools import combinations
import hashlib
import json
import random
import secrets
from typing import Mapping, Sequence

from .betting import calculate_bet, expand_bet_expression
from .collision import aggregate_collision_profiles, collision_profile, select_history
from .statistics import number_trends, structure_features, structure_score, ticket_similarity
from .types import BACK_MAX, FRONT_MAX, DltValidationError, Draw, Ticket


MODEL_VERSION = "ceway-dlt-collision-v1"


def _ticket_payload(ticket: Ticket, profile=None, **extra) -> dict:
    payload = ticket.to_dict()
    if profile is not None:
        payload["collision"] = profile.to_dict()
    payload.update(extra)
    return payload


def _secure_rng(seed: int | None = None):
    return random.Random(seed) if seed is not None else secrets.SystemRandom()


def generate_random_singles(count: int, seed: int | None = None) -> list[Ticket]:
    if count < 1 or count > 1000:
        raise DltValidationError("随机单式注数必须在 1 至 1000 之间")
    rng = _secure_rng(seed)
    tickets: list[Ticket] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    while len(tickets) < count:
        ticket = Ticket.create(rng.sample(range(1, FRONT_MAX + 1), 5), rng.sample(range(1, BACK_MAX + 1), 2))
        key = (ticket.front, ticket.back)
        if key not in seen:
            seen.add(key)
            tickets.append(ticket)
    return tickets


def generate_random_run(
    *,
    target_issue: str,
    history_cutoff_issue: str | None = None,
    count: int,
    addon: bool = False,
    multiplier: int = 1,
    seed: int | None = None,
    bet_expression: Mapping[str, object] | None = None,
) -> dict:
    expression_spec = dict(bet_expression or {"type": "single"})
    expression_type = str(expression_spec.get("type") or "single")
    rng = _secure_rng(seed)
    structures = []
    expanded: list[Ticket] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    total_cost = 0
    attempts = 0
    while len(structures) < count:
        attempts += 1
        if attempts > count * 100:
            raise DltValidationError("无法在当前约束下生成足够的不重复随机结构")
        expression = _random_expression(expression_type, expression_spec, rng)
        calculation = calculate_bet(expression, addon=addon, multiplier=multiplier)
        structure_tickets = expand_bet_expression(expression)
        keys = {(ticket.front, ticket.back) for ticket in structure_tickets}
        if seen & keys:
            continue
        seen.update(keys)
        expanded.extend(structure_tickets)
        structures.append({**expression, **calculation.to_dict()})
        total_cost += calculation.cost_yuan
    per_ticket_cost = (2 + int(addon)) * multiplier
    return {
        "target_issue": target_issue,
        "history_cutoff_issue": history_cutoff_issue,
        "mode": "random",
        "model_version": "secure-random-v1" if seed is None else "seeded-random-v1",
        "random_seed": seed,
        "config": {
            "count": count,
            "bet_expression": expression_spec,
            "addon": addon,
            "multiplier": multiplier,
            "history_cutoff_issue": history_cutoff_issue,
        },
        "structures": structures,
        "tickets": [
            _ticket_payload(ticket, expression_type=expression_type, addon=addon, multiplier=multiplier, expanded_bets=1, cost_yuan=per_ticket_cost)
            for ticket in expanded
        ],
        "total_bets": len(expanded),
        "total_cost_yuan": total_cost,
    }


def _random_expression(expression_type: str, spec: Mapping[str, object], rng) -> dict:
    if expression_type == "single":
        return {
            "type": "single",
            "front": sorted(rng.sample(range(1, FRONT_MAX + 1), 5)),
            "back": sorted(rng.sample(range(1, BACK_MAX + 1), 2)),
        }
    if expression_type in {"front_compound", "back_compound", "double_compound", "compound"}:
        default_front = 6 if expression_type in {"front_compound", "double_compound", "compound"} else 5
        default_back = 3 if expression_type in {"back_compound", "double_compound", "compound"} else 2
        front_count = int(spec.get("front_count") or default_front)
        back_count = int(spec.get("back_count") or default_back)
        return {
            "type": expression_type,
            "front": sorted(rng.sample(range(1, FRONT_MAX + 1), front_count)),
            "back": sorted(rng.sample(range(1, BACK_MAX + 1), back_count)),
        }
    if expression_type in {"front_dantuo", "back_dantuo", "double_dantuo", "dantuo"}:
        result: dict[str, object] = {"type": expression_type}
        if expression_type in {"front_dantuo", "double_dantuo", "dantuo"}:
            dan_count = int(spec.get("front_dan_count") or 2)
            tuo_count = int(spec.get("front_tuo_count") or 5)
            selected = rng.sample(range(1, FRONT_MAX + 1), dan_count + tuo_count)
            result.update({"front_dan": sorted(selected[:dan_count]), "front_tuo": sorted(selected[dan_count:])})
        else:
            result["front"] = sorted(rng.sample(range(1, FRONT_MAX + 1), 5))
        if expression_type in {"back_dantuo", "double_dantuo"}:
            dan_count = int(spec.get("back_dan_count") or 1)
            tuo_count = int(spec.get("back_tuo_count") or 2)
            selected = rng.sample(range(1, BACK_MAX + 1), dan_count + tuo_count)
            result.update({"back_dan": sorted(selected[:dan_count]), "back_tuo": sorted(selected[dan_count:])})
        else:
            result["back"] = sorted(rng.sample(range(1, BACK_MAX + 1), 2))
        return result
    raise DltValidationError("随机来源不支持该投注表达方式")


def _number_score(ticket: Ticket, front_trends: Mapping[int, Mapping[str, float]], back_trends: Mapping[int, Mapping[str, float]]) -> float:
    values = [float(front_trends[number]["trend_score"]) for number in ticket.front]
    values += [float(back_trends[number]["trend_score"]) for number in ticket.back]
    return sum(values) / len(values)


def generate_model_run(
    draws: Sequence[Draw],
    *,
    target_issue: str,
    history_cutoff_issue: str,
    history_window: Mapping[str, object] | None = None,
    front_pool_size: int = 12,
    back_pool_size: int = 5,
    output_count: int = 10,
    ranking_mode: str = "model",
) -> dict:
    if not target_issue:
        raise DltValidationError("target_issue 不能为空")
    if not 5 <= front_pool_size <= 18 or not 2 <= back_pool_size <= 8:
        raise DltValidationError("候选池范围为前区 5 至 18、后区 2 至 8")
    if not 1 <= output_count <= 100:
        raise DltValidationError("输出注数必须在 1 至 100 之间")
    if ranking_mode not in {"model", "scarcity"}:
        raise DltValidationError("模型模式仅支持 model 或 scarcity")
    history = select_history(draws, history_cutoff_issue, history_window)
    front_trends = number_trends(history, "front")
    back_trends = number_trends(history, "back")
    front_pool = sorted(front_trends, key=lambda number: (-float(front_trends[number]["trend_score"]), number))[:front_pool_size]
    back_pool = sorted(back_trends, key=lambda number: (-float(back_trends[number]["trend_score"]), number))[:back_pool_size]

    ranked = []
    for front in combinations(front_pool, 5):
        for back in combinations(back_pool, 2):
            ticket = Ticket.create(front, back)
            profile = collision_profile(ticket, history)
            number_score = _number_score(ticket, front_trends, back_trends)
            structural = structure_score(ticket, history)
            secondary = 0.45 * number_score + 0.45 * structural if ranking_mode == "model" else 0.0
            ranked.append((profile.scarcity_key, -secondary, ticket, profile, number_score, structural))
    ranked.sort(key=lambda row: (row[0], row[1], row[2].front, row[2].back))

    selected = []
    remaining = ranked[: max(output_count * 40, output_count)]
    while remaining and len(selected) < output_count:
        best = min(
            remaining,
            key=lambda row: (
                row[0],
                row[1] + (max((ticket_similarity(row[2], chosen[2]) for chosen in selected), default=0.0) * 0.10),
                row[2].front,
                row[2].back,
            ),
        )
        selected.append(best)
        remaining.remove(best)

    all_profiles = [row[3] for row in ranked]
    candidate_profiles = [
        {
            "rank": index,
            "front": list(row[2].front),
            "back": list(row[2].back),
            "collision": row[3].to_dict(),
            "number_score": round(row[4], 6),
            "structure_score": round(row[5], 6),
        }
        for index, row in enumerate(ranked, start=1)
    ]
    collision_fingerprint = hashlib.sha256(
        json.dumps(candidate_profiles, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    tickets = []
    for scarcity, _, ticket, profile, number_score, structural in selected:
        diversity = 1 - max((ticket_similarity(ticket, other[2]) for other in selected if other[2] != ticket), default=0.0)
        tickets.append(
            _ticket_payload(
                ticket,
                profile,
                expression_type="single",
                addon=False,
                multiplier=1,
                expanded_bets=1,
                cost_yuan=2,
                score_breakdown={
                    "number": round(number_score, 6),
                    "structure": round(structural, 6),
                    "diversity": round(diversity, 6),
                    "secondary": round(0.45 * number_score + 0.45 * structural + 0.10 * diversity, 6),
                },
                structure_features=structure_features(ticket),
                scarcity_key=list(scarcity),
            )
        )
    return {
        "target_issue": target_issue,
        "history_cutoff_issue": history_cutoff_issue,
        "mode": ranking_mode,
        "model_version": MODEL_VERSION,
        "config": {
            "history_window": dict(history_window or {"mode": "all_history"}),
            "front_pool_size": front_pool_size,
            "back_pool_size": back_pool_size,
            "output_count": output_count,
            "ranking": "collision_lexicographic_high_hits_first",
            "ranking_mode": ranking_mode,
        },
        "history": {"start_issue": history[0].issue, "end_issue": history[-1].issue, "draw_count": len(history)},
        "candidate_count": len(ranked),
        "candidate_profiles": candidate_profiles,
        "collision_fingerprint": collision_fingerprint,
        "tickets": tickets,
        "aggregate": aggregate_collision_profiles(all_profiles),
        "total_bets": len(tickets),
        "total_cost_yuan": len(tickets) * 2,
        "disclaimer": "历史碰撞稀缺只描述过去，不代表未来开奖概率更高。",
    }


def generate_package_run(
    *,
    target_issue: str,
    budget_yuan: int,
    template: str = "mixed",
    source: str = "random",
    addon: bool = False,
    multiplier: int = 1,
    seed: int | None = None,
    history_cutoff_issue: str | None = None,
    source_tickets: Sequence[Ticket] | None = None,
) -> dict:
    if budget_yuan < 2:
        raise DltValidationError("预算至少为 2 元")
    unit = (2 + int(addon)) * multiplier
    if budget_yuan < unit:
        raise DltValidationError("当前追加与倍数组合超过预算")
    if template not in {"dispersed_singles", "addon_singles", "small_compound", "dantuo", "mixed"}:
        raise DltValidationError("未知预算模板")
    rng = _secure_rng(seed)
    preferred = list(source_tickets or [])
    preferred_index = 0
    structures: list[dict] = []
    expanded_entries: list[tuple[Ticket, str, bool, int]] = []
    spent = 0

    def add_structure(expression: dict, use_addon: bool = addon) -> bool:
        nonlocal spent
        calculation = calculate_bet(expression, addon=use_addon, multiplier=multiplier)
        if spent + calculation.cost_yuan > budget_yuan:
            return False
        structures.append({**expression, **calculation.to_dict(), "source": source})
        per_ticket_cost = calculation.unit_yuan * calculation.multiplier
        expanded_entries.extend(
            (ticket, calculation.expression_type, use_addon, per_ticket_cost)
            for ticket in expand_bet_expression(expression)
        )
        spent += calculation.cost_yuan
        return True

    def source_expression(expression_type: str) -> dict:
        nonlocal preferred_index
        use_preferred = bool(preferred) and (source != "mixed" or preferred_index % 2 == 0)
        if expression_type == "single" and use_preferred:
            ticket = preferred[preferred_index % len(preferred)]
            preferred_index += 1
            return {"type": "single", **ticket.to_dict()}
        if expression_type in {"front_compound", "front_dantuo"} and use_preferred:
            front_order = []
            back_order = []
            for ticket in preferred:
                for number in ticket.front:
                    if number not in front_order:
                        front_order.append(number)
                for number in ticket.back:
                    if number not in back_order:
                        back_order.append(number)
            if len(front_order) >= 7 and len(back_order) >= 2:
                preferred_index += 1
                if expression_type == "front_compound":
                    return {"type": "front_compound", "front": sorted(front_order[:6]), "back": sorted(back_order[:2])}
                return {
                    "type": "front_dantuo", "front_dan": sorted(front_order[:2]),
                    "front_tuo": sorted(front_order[2:7]), "back": sorted(back_order[:2]),
                }
        preferred_index += 1
        return _random_expression(expression_type, {}, rng)

    if template in {"small_compound", "mixed"}:
        add_structure(source_expression("front_compound"))
    if template in {"dantuo", "mixed"}:
        add_structure(source_expression("front_dantuo"))
    single_addon = True if template == "addon_singles" else addon
    single_unit = (2 + int(single_addon)) * multiplier
    while spent + single_unit <= budget_yuan:
        expression = source_expression("single")
        add_structure(expression, single_addon)
    return {
        "target_issue": target_issue,
        "history_cutoff_issue": history_cutoff_issue,
        "mode": "package",
        "model_version": "ceway-budget-template-v1",
        "random_seed": seed,
        "config": {
            "budget_yuan": budget_yuan, "template": template, "source": source,
            "addon": addon, "multiplier": multiplier, "history_cutoff_issue": history_cutoff_issue,
        },
        "structures": structures,
        "tickets": [
            _ticket_payload(ticket, expression_type=expression_type, addon=ticket_addon, multiplier=multiplier, expanded_bets=1, cost_yuan=ticket_cost)
            for ticket, expression_type, ticket_addon, ticket_cost in expanded_entries
        ],
        "components": [
            {
                "expression_type": structure["expression_type"],
                "source": source,
                "expanded_bets": structure["expanded_bets"],
                "cost_yuan": structure["cost_yuan"],
            }
            for structure in structures
        ],
        "total_bets": len(expanded_entries),
        "total_cost_yuan": spent,
        "spent": spent,
        "unspent": budget_yuan - spent,
        "disclaimer": "预算套餐是程序内的预算组合模板，不是官方新增玩法。",
    }
