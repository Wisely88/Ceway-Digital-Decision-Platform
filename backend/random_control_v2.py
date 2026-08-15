from __future__ import annotations

import random
from itertools import combinations

from research_v2 import (
    GameSpec,
    TicketConstraints,
    conditional_random_tickets,
    constraints_like_ticket,
    expand_plan_tickets,
    passes_constraints,
)


def _enumerated_random_ticket(
    pool_size: int,
    pick_size: int,
    constraints: TicketConstraints,
    *,
    seed: str | int,
) -> tuple[int, ...]:
    """Uniformly sample one valid ticket by reservoir sampling over valid combos.

    This is a deterministic fallback for narrow constraint sets where rejection
    sampling can miss a perfectly valid structure even after many attempts.
    """
    rng = random.Random(str(seed))
    selected: tuple[int, ...] | None = None
    valid_count = 0
    for candidate in combinations(range(1, pool_size + 1), pick_size):
        if not passes_constraints(candidate, constraints):
            continue
        valid_count += 1
        if rng.randrange(valid_count) == 0:
            selected = candidate
    if selected is None:
        raise RuntimeError("No ticket exists for the requested structure-matched constraints")
    return selected


def robust_conditional_random_ticket(
    pool_size: int,
    pick_size: int,
    constraints: TicketConstraints,
    *,
    seed: str | int,
    rejection_attempts: int = 20_000,
) -> tuple[int, ...]:
    try:
        return conditional_random_tickets(
            pool_size,
            pick_size,
            1,
            constraints,
            seed=seed,
            max_attempts=rejection_attempts,
        )[0]
    except RuntimeError:
        return _enumerated_random_ticket(
            pool_size,
            pick_size,
            constraints,
            seed=f"{seed}-enumerated",
        )


def robust_structure_matched_random_plan(
    reference_plan: dict,
    spec: GameSpec,
    *,
    seed: str | int,
    main_zones: tuple[tuple[int, int], ...],
    bonus_zones: tuple[tuple[int, int], ...],
    main_sum_tolerance: int = 5,
    bonus_sum_tolerance: int | None = 2,
) -> dict:
    reference_tickets = expand_plan_tickets(reference_plan, spec)
    if not reference_tickets:
        raise ValueError("reference plan has no complete tickets")

    output = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for index, reference in enumerate(reference_tickets):
        main_constraints = constraints_like_ticket(
            reference["front"], main_zones, sum_tolerance=main_sum_tolerance
        )
        bonus_constraints = constraints_like_ticket(
            reference["back"], bonus_zones, sum_tolerance=bonus_sum_tolerance
        )

        selected = None
        for retry in range(100):
            front = robust_conditional_random_ticket(
                spec.main_pool,
                spec.main_pick,
                main_constraints,
                seed=f"{seed}-front-{index}-{retry}",
            )
            back = robust_conditional_random_ticket(
                spec.bonus_pool,
                spec.bonus_pick,
                bonus_constraints,
                seed=f"{seed}-back-{index}-{retry}",
            )
            key = (front, back)
            if key not in seen:
                selected = key
                seen.add(key)
                break
        if selected is None:
            raise RuntimeError("Unable to generate a unique structure-matched baseline ticket")

        front, back = selected
        output.append(
            {
                "front": list(front),
                "back": list(back),
                "front_display": [f"{number:02d}" for number in front],
                "back_display": [f"{number:02d}" for number in back],
                "score": 0,
                "explanation": ["V2 条件随机基线：结构匹配；拒绝采样失败时使用穷举均匀兜底。"],
            }
        )

    return {
        "mode": "single",
        "strategy": "random",
        "baseline_type": "conditional_random_v2_robust",
        "cost": len(output) * 2,
        "tickets": len(output),
        "items": output,
        "score": 0,
        "reason": "V2 鲁棒条件随机对照组：逐票匹配分区、奇偶、和值带与连号结构。",
    }
