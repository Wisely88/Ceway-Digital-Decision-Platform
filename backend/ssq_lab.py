from __future__ import annotations

from itertools import combinations
import random
import secrets
from typing import Mapping, Sequence

from engine import calculate_ssq_trends
from scorer import score_ssq_back_numbers, score_ssq_front_numbers


RED_MAX, RED_PICK = 33, 6
BLUE_MAX, BLUE_PICK = 16, 1


class SsqLabValidationError(ValueError):
    pass


def _numbers(values: Sequence[int], maximum: int, expected: int, label: str) -> tuple[int, ...]:
    result = tuple(sorted(int(value) for value in values))
    if len(result) != expected:
        raise SsqLabValidationError(f"{label}需要选择 {expected} 个")
    if len(set(result)) != len(result):
        raise SsqLabValidationError(f"{label}不能重复")
    if any(value < 1 or value > maximum for value in result):
        raise SsqLabValidationError(f"{label}必须在 1 至 {maximum} 之间")
    return result


def normalize_ticket(front: Sequence[int], back: Sequence[int]) -> dict:
    return {
        "front": list(_numbers(front, RED_MAX, RED_PICK, "红球")),
        "back": list(_numbers(back, BLUE_MAX, BLUE_PICK, "蓝球")),
    }


def _issue_key(issue: str) -> tuple[int, str]:
    value = str(issue)
    return (int(value), value) if value.isdigit() else (0, value)


def select_history(history: Sequence[dict], cutoff: str, window: Mapping[str, object] | None = None) -> list[dict]:
    if not cutoff:
        raise SsqLabValidationError("历史截止期不能为空")
    eligible = sorted(
        (row for row in history if _issue_key(row["issue"]) <= _issue_key(cutoff)),
        key=lambda row: _issue_key(row["issue"]),
    )
    spec = dict(window or {"mode": "all_history"})
    mode = str(spec.get("mode") or "all_history")
    if mode == "last_N":
        count = int(spec.get("count") or 0)
        if count < 1:
            raise SsqLabValidationError("最近期数必须大于 0")
        eligible = eligible[-count:]
    elif mode == "custom":
        start = str(spec.get("start_issue") or "")
        end = str(spec.get("end_issue") or cutoff)
        if not start:
            raise SsqLabValidationError("自定义窗口需要起始期号")
        if _issue_key(end) > _issue_key(cutoff):
            raise SsqLabValidationError("窗口结束期不能超过历史截止期")
        eligible = [row for row in eligible if _issue_key(start) <= _issue_key(row["issue"]) <= _issue_key(end)]
    elif mode != "all_history":
        raise SsqLabValidationError("历史窗口仅支持全部、最近 N 期或自定义")
    if not eligible:
        raise SsqLabValidationError("历史窗口内没有可用开奖记录")
    return eligible


def _mask(values: Sequence[int]) -> int:
    result = 0
    for value in values:
        result |= 1 << (int(value) - 1)
    return result


def collision_profile(ticket: dict, history: Sequence[dict]) -> dict:
    normalized = normalize_ticket(ticket["front"], ticket["back"])
    front_mask = _mask(normalized["front"])
    back_mask = _mask(normalized["back"])
    totals = [0] * 8
    matrix = [[0] * 2 for _ in range(7)]
    for draw in history:
        front_hits = (front_mask & _mask(draw["front"])).bit_count()
        back_hits = (back_mask & _mask(draw["back"])).bit_count()
        matrix[front_hits][back_hits] += 1
        totals[front_hits + back_hits] += 1
    return {
        "n_total_hits": totals,
        "n_front_back": matrix,
        "history_draw_count": len(history),
        "history_start_issue": history[0]["issue"] if history else None,
        "history_end_issue": history[-1]["issue"] if history else None,
        "max_total_hits": max((index for index, count in enumerate(totals) if count), default=0),
        "scarcity_key": [totals[index] for index in range(7, 0, -1)],
    }


def aggregate_profiles(profiles: Sequence[dict]) -> dict:
    m_total = [0] * 8
    u_total = [0] * 8
    m_matrix = [[0] * 2 for _ in range(7)]
    u_matrix = [[0] * 2 for _ in range(7)]
    for profile in profiles:
        for index, count in enumerate(profile["n_total_hits"]):
            m_total[index] += count
            u_total[index] += int(count > 0)
        for front_hits in range(7):
            for back_hits in range(2):
                count = profile["n_front_back"][front_hits][back_hits]
                m_matrix[front_hits][back_hits] += count
                u_matrix[front_hits][back_hits] += int(count > 0)
    return {
        "candidate_count": len(profiles),
        "m_total_hits": m_total,
        "u_total_hits": u_total,
        "m_front_back": m_matrix,
        "u_front_back": u_matrix,
    }


def analyze_tickets(history: Sequence[dict], cutoff: str, window: Mapping[str, object], tickets: Sequence[dict]) -> dict:
    selected = select_history(history, cutoff, window)
    normalized = [normalize_ticket(ticket["front"], ticket["back"]) for ticket in tickets]
    profiles = [collision_profile(ticket, selected) for ticket in normalized]
    return {
        "mode": "collision",
        "history_cutoff_issue": cutoff,
        "history": {"start_issue": selected[0]["issue"], "end_issue": selected[-1]["issue"], "draw_count": len(selected)},
        "tickets": [{**ticket, "collision": profile, "cost_yuan": 2} for ticket, profile in zip(normalized, profiles)],
        "aggregate": aggregate_profiles(profiles),
        "total_bets": len(normalized),
        "total_cost_yuan": len(normalized) * 2,
        "disclaimer": "完整组合碰撞只描述历史匹配次数，不代表未来开奖概率。",
    }


def generate_random(history: Sequence[dict], *, target_issue: str, cutoff: str, count: int, seed: int | None = None) -> dict:
    if count < 1 or count > 200:
        raise SsqLabValidationError("随机注数必须在 1 至 200 之间")
    rng = random.Random(seed) if seed is not None else secrets.SystemRandom()
    seen: set[tuple[tuple[int, ...], int]] = set()
    tickets = []
    while len(tickets) < count:
        front = tuple(sorted(rng.sample(range(1, RED_MAX + 1), RED_PICK)))
        back = rng.randint(1, BLUE_MAX)
        key = (front, back)
        if key in seen:
            continue
        seen.add(key)
        tickets.append({"front": list(front), "back": [back]})
    result = analyze_tickets(history, cutoff, {"mode": "all_history"}, tickets)
    return {**result, "mode": "random", "target_issue": target_issue, "model_version": "ssq-secure-random-v1", "random_seed": seed}


def generate_model(
    history: Sequence[dict],
    *,
    target_issue: str,
    cutoff: str,
    window: Mapping[str, object],
    front_pool_size: int = 10,
    back_pool_size: int = 4,
    output_count: int = 8,
) -> dict:
    if not 6 <= front_pool_size <= 12 or not 1 <= back_pool_size <= 8:
        raise SsqLabValidationError("候选池范围为红球 6 至 12、蓝球 1 至 8")
    if not 1 <= output_count <= 50:
        raise SsqLabValidationError("输出注数必须在 1 至 50 之间")
    selected = select_history(history, cutoff, window)
    trends = calculate_ssq_trends(selected, min(120, len(selected)))
    front_scores = score_ssq_front_numbers(trends)
    back_scores = score_ssq_back_numbers(trends)
    front_pool = [row["number"] for row in front_scores[:front_pool_size]]
    back_pool = [row["number"] for row in back_scores[:back_pool_size]]
    score_map = {row["number"]: float(row["total_score"]) for row in front_scores}
    back_score_map = {row["number"]: float(row["total_score"]) for row in back_scores}
    candidates = []
    for front in combinations(front_pool, RED_PICK):
        for blue in back_pool:
            ticket = normalize_ticket(front, [blue])
            profile = collision_profile(ticket, selected)
            score = (sum(score_map[number] for number in front) + back_score_map[blue]) / 7
            candidates.append((tuple(profile["scarcity_key"]), -score, ticket, profile, score))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]["front"], row[2]["back"]))
    picked = candidates[:output_count]
    tickets = [
        {**ticket, "collision": profile, "score_breakdown": {"secondary": round(score, 3)}, "cost_yuan": 2}
        for _, _, ticket, profile, score in picked
    ]
    profiles = [ticket["collision"] for ticket in tickets]
    return {
        "mode": "model",
        "model_version": "ceway-ssq-collision-v1",
        "target_issue": target_issue,
        "history_cutoff_issue": cutoff,
        "history": {"start_issue": selected[0]["issue"], "end_issue": selected[-1]["issue"], "draw_count": len(selected)},
        "config": {"history_window": dict(window), "front_pool_size": front_pool_size, "back_pool_size": back_pool_size, "output_count": output_count},
        "tickets": tickets,
        "aggregate": aggregate_profiles(profiles),
        "candidate_count": len(candidates),
        "total_bets": len(tickets),
        "total_cost_yuan": len(tickets) * 2,
        "disclaimer": "模型先按历史评分形成候选池，再按完整组合历史碰撞排序；结果不代表未来概率提升。",
    }
