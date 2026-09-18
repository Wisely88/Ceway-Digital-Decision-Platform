from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Sequence

from generator import TICKET_PRICE, attach_budget_analysis, format_numbers, ssq_format_numbers
from research_v2 import diversity_summary


MULTIREGIME_V25_VERSION = "multi-regime-exposure-v2.5"
ROLE_WEIGHTS = {"evidence": 0.50, "scarcity": 0.30, "neutral": 0.20}
SCARCITY_WEIGHTS = {"rarity3": 0.30, "rarity7": 0.20, "rarity20": 0.15, "gap": 0.15, "divergence": 0.20}
EVIDENCE_WEIGHTS = {"long_frequency": 0.25, "recency": 0.15, "momentum": 0.10, "stability": 0.10}


@dataclass(frozen=True)
class GameSpec:
    game: str
    main_pool: int
    main_pick: int
    bonus_pool: int
    bonus_pick: int


DLT = GameSpec("DLT", 35, 5, 12, 2)
SSQ = GameSpec("SSQ", 33, 6, 16, 1)


def _issue_key(issue: object) -> tuple[int, str]:
    text = str(issue or "")
    if text.isdigit():
        return (0, f"{int(text):020d}")
    return (1, text)


def _cutoff(history: Sequence[dict], issue: str | None) -> list[dict]:
    rows = sorted(history, key=lambda row: _issue_key(row.get("issue")))
    if issue is None:
        return list(rows)
    key = _issue_key(issue)
    return [row for row in rows if _issue_key(row.get("issue")) <= key]


def _percentiles(values: dict[int, float], *, higher_is_better: bool = True) -> dict[int, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]), reverse=higher_is_better)
    n = len(ordered)
    if n == 1:
        return {ordered[0][0]: 1.0}
    return {number: 1.0 - index / (n - 1) for index, (number, _value) in enumerate(ordered)}


def _rate(rows: Sequence[dict], number: int, area: str, window: int) -> float:
    sample = rows[-min(window, len(rows)):]
    if not sample:
        return 0.0
    return sum(number in row.get(area, []) for row in sample) / len(sample)


def _recency_rate(rows: Sequence[dict], number: int, area: str, window: int = 20, half_life: float = 7.0) -> float:
    sample = rows[-min(window, len(rows)):]
    if not sample:
        return 0.0
    decay = math.log(2.0) / half_life
    weighted = 0.0
    total = 0.0
    for age, row in enumerate(reversed(sample)):
        weight = math.exp(-decay * age)
        total += weight
        weighted += weight * (number in row.get(area, []))
    return weighted / total if total else 0.0


def _gap(rows: Sequence[dict], number: int, area: str) -> int:
    for age, row in enumerate(reversed(rows)):
        if number in row.get(area, []):
            return age
    return len(rows)


def score_regimes(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    area: str,
    history_cutoff_issue: str | None = None,
) -> list[dict]:
    rows = _cutoff(history, history_cutoff_issue)
    if len(rows) < 30:
        raise ValueError("V2.5 requires at least 30 historical draws")
    pool = spec.main_pool if area == "front" else spec.bonus_pool
    numbers = range(1, pool + 1)

    rates3 = {n: _rate(rows, n, area, 3) for n in numbers}
    rates7 = {n: _rate(rows, n, area, 7) for n in numbers}
    rates20 = {n: _rate(rows, n, area, 20) for n in numbers}
    rates50 = {n: _rate(rows, n, area, 50) for n in numbers}
    rates100 = {n: _rate(rows, n, area, 100) for n in numbers}
    recency = {n: _recency_rate(rows, n, area) for n in numbers}
    momentum = {n: rates20[n] - rates100[n] for n in numbers}
    stability_raw = {n: pstdev([rates20[n], rates50[n], rates100[n]]) for n in numbers}
    gaps = {n: float(_gap(rows, n, area)) for n in numbers}
    divergence = {n: max(0.0, rates100[n] - rates7[n]) for n in numbers}

    p_long = _percentiles(rates100)
    p_recency = _percentiles(recency)
    p_momentum = _percentiles(momentum)
    p_stability = _percentiles(stability_raw, higher_is_better=False)
    p_rarity3 = _percentiles(rates3, higher_is_better=False)
    p_rarity7 = _percentiles(rates7, higher_is_better=False)
    p_rarity20 = _percentiles(rates20, higher_is_better=False)
    p_gap = _percentiles(gaps)
    p_divergence = _percentiles(divergence)

    result = []
    for number in numbers:
        evidence = (
            EVIDENCE_WEIGHTS["long_frequency"] * p_long[number]
            + EVIDENCE_WEIGHTS["recency"] * p_recency[number]
            + EVIDENCE_WEIGHTS["momentum"] * p_momentum[number]
            + EVIDENCE_WEIGHTS["stability"] * p_stability[number]
        ) / sum(EVIDENCE_WEIGHTS.values())
        scarcity = (
            SCARCITY_WEIGHTS["rarity3"] * p_rarity3[number]
            + SCARCITY_WEIGHTS["rarity7"] * p_rarity7[number]
            + SCARCITY_WEIGHTS["rarity20"] * p_rarity20[number]
            + SCARCITY_WEIGHTS["gap"] * p_gap[number]
            + SCARCITY_WEIGHTS["divergence"] * p_divergence[number]
        )
        neutral = max(0.0, 1.0 - (abs(evidence - 0.5) + abs(scarcity - 0.5)))
        result.append({
            "number": number,
            "evidence_score": round(evidence, 6),
            "scarcity_score": round(scarcity, 6),
            "neutral_score": round(neutral, 6),
            "rarity3": round(p_rarity3[number], 6),
            "rarity7": round(p_rarity7[number], 6),
            "rarity20": round(p_rarity20[number], 6),
            "gap_percentile": round(p_gap[number], 6),
            "divergence_score": round(p_divergence[number], 6),
            "gap": int(gaps[number]),
            "rate3": round(rates3[number], 6),
            "rate7": round(rates7[number], 6),
            "rate20": round(rates20[number], 6),
            "rate100": round(rates100[number], 6),
        })

    for key in ("evidence", "scarcity", "neutral"):
        ordered = sorted(result, key=lambda row: (-row[f"{key}_score"], row["number"]))
        for rank, row in enumerate(ordered, 1):
            row[f"{key}_rank"] = rank
    return sorted(result, key=lambda row: row["number"])


def _role_sequence(total_slots: int) -> list[str]:
    evidence = int(round(total_slots * ROLE_WEIGHTS["evidence"]))
    scarcity = int(round(total_slots * ROLE_WEIGHTS["scarcity"]))
    neutral = total_slots - evidence - scarcity
    roles = ["evidence"] * evidence + ["scarcity"] * scarcity + ["neutral"] * neutral
    # Interleave deterministically so every ticket gets a regime mix rather than
    # concentrating one regime in early tickets.
    buckets = {role: [role] * roles.count(role) for role in ROLE_WEIGHTS}
    output = []
    order = ("evidence", "scarcity", "evidence", "neutral", "scarcity")
    while len(output) < total_slots:
        progressed = False
        for role in order:
            if buckets[role]:
                output.append(buckets[role].pop())
                progressed = True
                if len(output) >= total_slots:
                    break
        if not progressed:
            break
    return output


def _choose_portfolio(rows: list[dict], *, pick_size: int, ticket_count: int) -> tuple[list[tuple[int, ...]], dict]:
    row_by_number = {row["number"]: row for row in rows}
    numbers = tuple(sorted(row_by_number))
    roles = _role_sequence(ticket_count * pick_size)
    role_counts = Counter(roles)
    usage: Counter[int] = Counter()
    pair_usage: Counter[tuple[int, int]] = Counter()
    tickets: list[tuple[int, ...]] = []
    role_index = 0

    for _ in range(ticket_count):
        selected: list[int] = []
        while len(selected) < pick_size:
            role = roles[role_index]
            role_index += 1
            best = None
            best_key = None
            for number in numbers:
                if number in selected:
                    continue
                row = row_by_number[number]
                role_quality = float(row[f"{role}_score"])
                reused_pairs = sum(pair_usage[tuple(sorted((number, other)))] for other in selected)
                tentative = set(selected + [number])
                max_overlap = max((len(tentative & set(ticket)) for ticket in tickets), default=0)
                # Broad exposure is deliberately strong enough that a low evidence
                # rank can still enter via scarcity/neutral role, but no role can
                # monopolize repeated numbers or pairs.
                objective = (
                    2.20 * role_quality
                    - 0.32 * usage[number]
                    - 0.28 * reused_pairs
                    - 0.35 * (max_overlap / max(1, pick_size))
                )
                key = (objective, role_quality, -usage[number], -number)
                if best_key is None or key > best_key:
                    best_key = key
                    best = number
            if best is None:
                break
            selected.append(best)
        if len(selected) != pick_size:
            break
        ticket = tuple(sorted(selected))
        tickets.append(ticket)
        usage.update(ticket)
        for i, left in enumerate(ticket):
            for right in ticket[i + 1:]:
                pair_usage[(left, right)] += 1

    return tickets, {
        "role_slot_targets": dict(role_counts),
        "number_usage": dict(sorted(usage.items())),
        "max_number_exposure": max(usage.values(), default=0),
        "max_pair_reuse": max(pair_usage.values(), default=0),
        "diversity": diversity_summary(tickets),
    }


def generate_multiregime_plan(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    budget: int = 20,
    strategy: str = "balanced",
    history_cutoff_issue: str | None = None,
) -> dict:
    training = _cutoff(history, history_cutoff_issue)
    if len(training) < 30:
        raise ValueError("V2.5 requires at least 30 historical draws")
    ticket_count = max(1, budget // TICKET_PRICE)
    front_rows = score_regimes(training, spec, area="front")
    back_rows = score_regimes(training, spec, area="back")
    fronts, front_diag = _choose_portfolio(front_rows, pick_size=spec.main_pick, ticket_count=ticket_count)
    backs, back_diag = _choose_portfolio(back_rows, pick_size=spec.bonus_pick, ticket_count=ticket_count)
    front_map = {row["number"]: row for row in front_rows}

    items = []
    for index, front in enumerate(fronts):
        back = backs[index % len(backs)] if backs else tuple()
        front_list = list(front)
        back_list = list(back)
        avg_evidence = mean(front_map[number]["evidence_score"] for number in front)
        avg_scarcity = mean(front_map[number]["scarcity_score"] for number in front)
        items.append({
            "front": front_list,
            "back": back_list,
            "front_display": format_numbers(front_list) if spec.game == "DLT" else ssq_format_numbers(front_list),
            "back_display": format_numbers(back_list) if spec.game == "DLT" else ssq_format_numbers(back_list),
            "score": round((0.6 * avg_evidence + 0.4 * avg_scarcity) * 100, 4),
            "explanation": ["V2.5 多状态曝光：Evidence/Scarcity/Neutral 独立分配预算；稀缺仅作覆盖状态，不解释为更高中奖概率。"],
        })

    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": MULTIREGIME_V25_VERSION,
        "algorithm_version": f"CEWAY-FWD-{spec.game}-{MULTIREGIME_V25_VERSION}",
        "cost": len(items) * TICKET_PRICE,
        "tickets": len(items),
        "items": items,
        "score": round(sum(item["score"] for item in items), 2),
        "reason": "V2.5 research candidate: independent Evidence/Scarcity/Neutral regimes with pre-registered 50/30/20 slot exposure.",
        "history_cutoff_issue": training[-1].get("issue"),
        "production_enabled": False,
        "research_guard": "Scarcity is a descriptive coverage regime, not a future-win probability claim.",
        "regime_parameters": {
            "role_weights": ROLE_WEIGHTS,
            "evidence_weights": EVIDENCE_WEIGHTS,
            "scarcity_weights": SCARCITY_WEIGHTS,
            "outcome_tuned": False,
        },
        "front_regime_table": front_rows,
        "back_regime_table": back_rows,
        "coverage_diagnostics": {"front": front_diag, "back": back_diag},
    }
    return attach_budget_analysis(plan, budget)
