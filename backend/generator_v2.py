from __future__ import annotations

from collections import Counter
from itertools import combinations

from generator import TICKET_PRICE, attach_budget_analysis, format_numbers, plan_score, ssq_format_numbers, ssq_plan_score
from research_v2 import diversity_summary, jaccard_similarity


GENERATOR_V2_VERSION = "coverage-aware-greedy-v1"


def _score_map(score_table: list[dict]) -> dict[int, float]:
    return {int(item["number"]): float(item.get("total_score", 0.0)) for item in score_table}


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
    """Greedy score/diversity selector over a ranked candidate band.

    The first ticket is score-led. Later tickets prefer candidates that keep
    pairwise overlap under a soft cap, add under-used numbers, and retain score
    quality. The cap is relaxed only if the current pool cannot fill the budget.
    """
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
