from __future__ import annotations

from collections import Counter
from itertools import combinations

from generator import TICKET_PRICE, attach_budget_analysis, format_numbers, plan_score, ssq_format_numbers, ssq_plan_score
from research_v2 import diversity_summary, jaccard_similarity


# Frozen completed experiment. Keep this version and its functions unchanged so
# historical A/B and holdout artifacts remain reproducible through Git history.
GENERATOR_V2_VERSION = "coverage-aware-greedy-v1"

# New structural experiment. Its parameters were selected against synthetic
# monotonic score tables and target portfolio diversity, not lottery outcomes.
GENERATOR_EXPOSURE_VERSION = "score-exposure-balanced-v2.1"


def _score_map(score_table: list[dict]) -> dict[int, float]:
    return {int(item["number"]): float(item.get("total_score", 0.0)) for item in score_table}


def _normalized_number_scores(score_table: list[dict]) -> dict[int, float]:
    raw = _score_map(score_table)
    if not raw:
        return {}
    low = min(raw.values())
    high = max(raw.values())
    if high <= low:
        return {number: 1.0 for number in raw}
    return {number: (value - low) / (high - low) for number, value in raw.items()}


def _normalized_combo_scores(candidates: list[tuple[int, ...]], score_by_number: dict[int, float]) -> dict[tuple[int, ...], float]:
    raw = {candidate: sum(score_by_number.get(number, 0.0) for number in candidate) for candidate in candidates}
    if not raw:
        return {}
    low = min(raw.values())
    high = max(raw.values())
    if high <= low:
        return {candidate: 1.0 for candidate in candidates}
    return {candidate: (value - low) / (high - low) for candidate, value in raw.items()}


def _choose_diverse_combinations(
    *,
    ranked_numbers: list[int],
    pick_size: int,
    ticket_count: int,
    score_table: list[dict],
    candidate_band: int,
    preferred_max_overlap: int,
    quality_weight: float = 0.45,
    diversity_weight: float = 0.45,
    coverage_weight: float = 0.10,
) -> list[tuple[int, ...]]:
    """Frozen v1 greedy score/diversity selector over a ranked candidate band."""
    band = tuple(ranked_numbers[: max(pick_size, min(candidate_band, len(ranked_numbers)))])
    candidates = list(combinations(band, pick_size))
    if not candidates:
        return []

    score_by_number = _score_map(score_table)
    normalized = _normalized_combo_scores(candidates, score_by_number)
    selected: list[tuple[int, ...]] = []
    usage: Counter[int] = Counter()
    remaining = set(candidates)

    while remaining and len(selected) < ticket_count:
        best_candidate = None
        best_key = None
        for candidate in remaining:
            if not selected:
                max_overlap = 0
                max_jaccard = 0.0
            else:
                overlaps = [len(set(candidate) & set(existing)) for existing in selected]
                max_overlap = max(overlaps)
                max_jaccard = max(jaccard_similarity(candidate, existing) for existing in selected)

            soft_cap_bonus = 1.0 if max_overlap <= preferred_max_overlap else 0.0
            new_numbers = sum(1 for number in candidate if usage[number] == 0) / pick_size
            average_usage = sum(usage[number] for number in candidate) / (pick_size * max(1, len(selected)))
            diversity_value = 1.0 - max_jaccard
            quality_value = normalized[candidate]
            objective = (
                quality_weight * quality_value
                + diversity_weight * diversity_value
                + coverage_weight * new_numbers
                - 0.12 * average_usage
                + 0.08 * soft_cap_bonus
            )
            key = (objective, -max_overlap, quality_value, tuple(-number for number in candidate))
            if best_key is None or key > best_key:
                best_key = key
                best_candidate = candidate

        if best_candidate is None:
            break
        selected.append(best_candidate)
        remaining.remove(best_candidate)
        usage.update(best_candidate)

    return selected


def _choose_back_pairs(ranked_back: list[int], ticket_count: int, candidate_band: int = 8) -> list[tuple[int, int]]:
    band = tuple(ranked_back[: min(candidate_band, len(ranked_back))])
    pairs = list(combinations(band, 2))
    if not pairs:
        return []
    selected = []
    usage: Counter[int] = Counter()
    while len(selected) < ticket_count:
        best = min(
            pairs,
            key=lambda pair: (
                usage[pair[0]] + usage[pair[1]],
                max(usage[pair[0]], usage[pair[1]]),
                pairs.index(pair),
            ),
        )
        selected.append(best)
        usage.update(best)
    return selected


def _choose_blue_numbers(ranked_back: list[int], ticket_count: int, candidate_band: int = 10) -> list[int]:
    band = ranked_back[: min(candidate_band, len(ranked_back))]
    if not band:
        return []
    return [band[index % len(band)] for index in range(ticket_count)]


def _choose_exposure_balanced_tickets(
    *,
    score_table: list[dict],
    pick_size: int,
    ticket_count: int,
    score_mix: float = 0.50,
    quality_weight: float = 2.00,
    exposure_weight: float = 0.25,
    pair_reuse_weight: float = 0.25,
    overlap_weight: float = 0.30,
) -> list[tuple[int, ...]]:
    """Build a score-biased but broadly exposed portfolio without a hard top-N band.

    The total slot budget (ticket_count * pick_size) is translated into a soft
    target exposure for every number. Half of that target is uniform coverage
    and half follows the normalized scorer. Ticket construction then rewards
    score quality and under-target numbers while penalizing reused pairs and
    overlap with existing tickets.

    Defaults were chosen on synthetic monotonic score tables to keep DLT/SSQ
    portfolio Jaccard near structural random baselines while preserving a clear
    preference for higher-ranked numbers. No draw outcomes were used to select
    these defaults.
    """
    normalized = _normalized_number_scores(score_table)
    if len(normalized) < pick_size:
        return []
    numbers = tuple(sorted(normalized))

    # Give even the lowest-scored number non-zero target mass. This avoids a
    # disguised hard candidate band while still allocating more exposure to
    # higher-ranked numbers.
    score_mass = {number: 0.20 + 0.80 * normalized[number] for number in numbers}
    total_score_mass = sum(score_mass.values())
    total_slots = ticket_count * pick_size
    uniform_mass = 1.0 / len(numbers)
    target_exposure = {
        number: total_slots
        * (
            (1.0 - score_mix) * uniform_mass
            + score_mix * (score_mass[number] / total_score_mass)
        )
        for number in numbers
    }

    usage: Counter[int] = Counter()
    pair_usage: Counter[tuple[int, int]] = Counter()
    tickets: list[tuple[int, ...]] = []

    for _ticket_index in range(ticket_count):
        selected: list[int] = []
        while len(selected) < pick_size:
            best_number = None
            best_key = None
            for number in numbers:
                if number in selected:
                    continue

                quality = normalized[number]
                exposure_deficit = target_exposure[number] - usage[number]
                reused_pairs = sum(
                    pair_usage[tuple(sorted((number, existing)))]
                    for existing in selected
                )
                tentative = set(selected + [number])
                max_overlap = max(
                    (len(tentative & set(existing_ticket)) for existing_ticket in tickets),
                    default=0,
                )
                objective = (
                    quality_weight * quality
                    + exposure_weight * exposure_deficit
                    - pair_reuse_weight * reused_pairs
                    - overlap_weight * (max_overlap / pick_size)
                )
                key = (
                    objective,
                    exposure_deficit,
                    -usage[number],
                    quality,
                    -number,
                )
                if best_key is None or key > best_key:
                    best_key = key
                    best_number = number

            if best_number is None:
                break
            selected.append(best_number)

        ticket = tuple(sorted(selected))
        if len(ticket) != pick_size:
            break
        tickets.append(ticket)
        usage.update(ticket)
        for left, right in combinations(ticket, 2):
            pair_usage[(left, right)] += 1

    return tickets


def generate_dlt_coverage_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
    *,
    candidate_band: int = 15,
    preferred_max_overlap: int = 2,
) -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    ranked_front = [int(item["number"]) for item in score_table]
    ranked_back = [int(item["number"]) for item in back_scores]
    fronts = _choose_diverse_combinations(
        ranked_numbers=ranked_front,
        pick_size=5,
        ticket_count=ticket_count,
        score_table=score_table,
        candidate_band=candidate_band,
        preferred_max_overlap=preferred_max_overlap,
    )
    backs = _choose_back_pairs(ranked_back, ticket_count)
    items = []
    for index, front in enumerate(fronts):
        back = backs[index % len(backs)] if backs else tuple(ranked_back[:2])
        front_list = sorted(front)
        back_list = sorted(back)
        items.append(
            {
                "front": front_list,
                "back": back_list,
                "front_display": format_numbers(front_list),
                "back_display": format_numbers(back_list),
                "score": plan_score(front_list, score_table),
                "explanation": ["V2 覆盖感知组合：保留评分排序，同时惩罚注间高度重叠。"],
            }
        )

    cost = len(items) * TICKET_PRICE
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": GENERATOR_V2_VERSION,
        "cost": cost,
        "tickets": len(items),
        "items": items,
        "score": round(sum(item["score"] for item in items), 2),
        "reason": "V2 实验组合器：评分质量与预算内组合覆盖共同优化。",
        "coverage_diagnostics": {
            "candidate_band": candidate_band,
            "preferred_max_overlap": preferred_max_overlap,
            "front_diversity": diversity_summary(item["front"] for item in items),
        },
    }
    return attach_budget_analysis(plan, budget)


def generate_ssq_coverage_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
    *,
    candidate_band: int = 17,
    preferred_max_overlap: int = 3,
) -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    ranked_front = [int(item["number"]) for item in score_table]
    ranked_back = [int(item["number"]) for item in back_scores]
    fronts = _choose_diverse_combinations(
        ranked_numbers=ranked_front,
        pick_size=6,
        ticket_count=ticket_count,
        score_table=score_table,
        candidate_band=candidate_band,
        preferred_max_overlap=preferred_max_overlap,
    )
    blues = _choose_blue_numbers(ranked_back, ticket_count)
    items = []
    for index, front in enumerate(fronts):
        back = [blues[index % len(blues)]] if blues else [ranked_back[0]]
        front_list = sorted(front)
        items.append(
            {
                "front": front_list,
                "back": back,
                "front_display": ssq_format_numbers(front_list),
                "back_display": ssq_format_numbers(back),
                "score": ssq_plan_score(front_list, score_table),
                "explanation": ["V2 覆盖感知组合：保留评分排序，同时惩罚注间高度重叠。"],
            }
        )

    cost = len(items) * TICKET_PRICE
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": GENERATOR_V2_VERSION,
        "cost": cost,
        "tickets": len(items),
        "items": items,
        "score": round(sum(item["score"] for item in items), 2),
        "reason": "V2 实验组合器：评分质量与预算内组合覆盖共同优化。",
        "coverage_diagnostics": {
            "candidate_band": candidate_band,
            "preferred_max_overlap": preferred_max_overlap,
            "front_diversity": diversity_summary(item["front"] for item in items),
        },
    }
    return attach_budget_analysis(plan, budget)


def generate_dlt_exposure_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
) -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    fronts = _choose_exposure_balanced_tickets(
        score_table=score_table,
        pick_size=5,
        ticket_count=ticket_count,
    )
    backs = _choose_exposure_balanced_tickets(
        score_table=back_scores,
        pick_size=2,
        ticket_count=ticket_count,
    )
    items = []
    for index, front in enumerate(fronts):
        back = backs[index % len(backs)] if backs else tuple()
        front_list = sorted(front)
        back_list = sorted(back)
        items.append(
            {
                "front": front_list,
                "back": back_list,
                "front_display": format_numbers(front_list),
                "back_display": format_numbers(back_list),
                "score": plan_score(front_list, score_table),
                "explanation": ["V2.1 曝光预算组合：高分号获得更多额度，同时抑制号码与号码对重复。"],
            }
        )

    cost = len(items) * TICKET_PRICE
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": GENERATOR_EXPOSURE_VERSION,
        "cost": cost,
        "tickets": len(items),
        "items": items,
        "score": round(sum(item["score"] for item in items), 2),
        "reason": "V2.1 实验组合器：用全号码池的评分曝光预算替代硬 top-N 候选带。",
        "coverage_diagnostics": {
            "score_mix": 0.50,
            "quality_weight": 2.00,
            "exposure_weight": 0.25,
            "pair_reuse_weight": 0.25,
            "overlap_weight": 0.30,
            "front_diversity": diversity_summary(item["front"] for item in items),
            "back_diversity": diversity_summary(item["back"] for item in items),
        },
    }
    return attach_budget_analysis(plan, budget)


def generate_ssq_exposure_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
) -> dict:
    ticket_count = max(1, budget // TICKET_PRICE)
    fronts = _choose_exposure_balanced_tickets(
        score_table=score_table,
        pick_size=6,
        ticket_count=ticket_count,
    )
    blues = _choose_exposure_balanced_tickets(
        score_table=back_scores,
        pick_size=1,
        ticket_count=ticket_count,
    )
    items = []
    for index, front in enumerate(fronts):
        back_tuple = blues[index % len(blues)] if blues else tuple()
        back = list(back_tuple)
        front_list = sorted(front)
        items.append(
            {
                "front": front_list,
                "back": back,
                "front_display": ssq_format_numbers(front_list),
                "back_display": ssq_format_numbers(back),
                "score": ssq_plan_score(front_list, score_table),
                "explanation": ["V2.1 曝光预算组合：高分号获得更多额度，同时抑制号码与号码对重复。"],
            }
        )

    cost = len(items) * TICKET_PRICE
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": GENERATOR_EXPOSURE_VERSION,
        "cost": cost,
        "tickets": len(items),
        "items": items,
        "score": round(sum(item["score"] for item in items), 2),
        "reason": "V2.1 实验组合器：用全号码池的评分曝光预算替代硬 top-N 候选带。",
        "coverage_diagnostics": {
            "score_mix": 0.50,
            "quality_weight": 2.00,
            "exposure_weight": 0.25,
            "pair_reuse_weight": 0.25,
            "overlap_weight": 0.30,
            "front_diversity": diversity_summary(item["front"] for item in items),
            "back_diversity": diversity_summary(item["back"] for item in items),
        },
    }
    return attach_budget_analysis(plan, budget)
