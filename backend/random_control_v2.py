from __future__ import annotations

import random
from itertools import combinations, product

from research_v2 import (
    GameSpec,
    TicketConstraints,
    conditional_random_tickets,
    constraints_like_ticket,
    expand_plan_tickets,
    passes_constraints,
)


def _zone_values(
    pool_size: int,
    zones: tuple[tuple[int, int], ...],
) -> list[tuple[int, ...]] | None:
    values_by_zone: list[tuple[int, ...]] = []
    covered: list[int] = []
    for low, high in zones:
        values = tuple(number for number in range(max(1, low), min(pool_size, high) + 1))
        values_by_zone.append(values)
        covered.extend(values)
    # Require a true partition of the game pool. If zones overlap or leave gaps,
    # use the generic sampler so the proposal distribution stays correct.
    if sorted(covered) != list(range(1, pool_size + 1)):
        return None
    return values_by_zone


def _zone_constrained_candidates(
    pool_size: int,
    pick_size: int,
    constraints: TicketConstraints,
):
    """Yield candidates from declared zone quotas before other filters."""
    zone_values = _zone_values(pool_size, constraints.zones)
    if zone_values is None or not constraints.allowed_zone_counts:
        yield from combinations(range(1, pool_size + 1), pick_size)
        return

    for counts in constraints.allowed_zone_counts:
        if len(counts) != len(zone_values) or sum(counts) != pick_size:
            continue
        per_zone = []
        valid_pattern = True
        for values, count in zip(zone_values, counts):
            if count < 0 or count > len(values):
                valid_pattern = False
                break
            per_zone.append(combinations(values, count))
        if not valid_pattern:
            continue
        for pieces in product(*per_zone):
            merged = tuple(sorted(number for piece in pieces for number in piece))
            if len(merged) == pick_size:
                yield merged


def _zone_rejection_ticket(
    pool_size: int,
    pick_size: int,
    constraints: TicketConstraints,
    *,
    seed: str | int,
    attempts: int,
) -> tuple[int, ...] | None:
    """Sample uniformly inside one exact zone-count pattern, then filter.

    constraints_like_ticket() always produces one exact zone pattern. Drawing
    uniformly from each zone's combinations makes the Cartesian-product
    proposal uniform over that structural subspace, so rejection on odd/even,
    sum and consecutive constraints remains unbiased inside the matched shape.
    """
    if len(constraints.allowed_zone_counts) != 1:
        return None
    zone_values = _zone_values(pool_size, constraints.zones)
    if zone_values is None:
        return None
    counts = constraints.allowed_zone_counts[0]
    if len(counts) != len(zone_values) or sum(counts) != pick_size:
        return None
    if any(count < 0 or count > len(values) for values, count in zip(zone_values, counts)):
        return None

    rng = random.Random(str(seed))
    for _ in range(max(1, attempts)):
        ticket = tuple(
            sorted(
                number
                for values, count in zip(zone_values, counts)
                for number in rng.sample(values, count)
            )
        )
        if passes_constraints(ticket, constraints):
            return ticket
    return None


def _enumerated_random_ticket(
    pool_size: int,
    pick_size: int,
    constraints: TicketConstraints,
    *,
    seed: str | int,
) -> tuple[int, ...]:
    """Uniformly sample one valid ticket by reservoir sampling over valid combos."""
    rng = random.Random(str(seed))
    selected: tuple[int, ...] | None = None
    valid_count = 0
    for candidate in _zone_constrained_candidates(pool_size, pick_size, constraints):
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
    rejection_attempts: int = 2_000,
) -> tuple[int, ...]:
    # Fast path: sample directly inside the exact zone-allocation subspace.
    structured = _zone_rejection_ticket(
        pool_size,
        pick_size,
        constraints,
        seed=f"{seed}-zone",
        attempts=rejection_attempts,
    )
    if structured is not None:
        return structured

    # Generic path for callers without an exact partitioned zone shape.
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
        # Deterministic exact fallback guarantees a valid draw whenever the
        # constraint set is non-empty, while preserving uniform reservoir
        # sampling over the valid enumerated candidate set.
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
                "explanation": ["V2 条件随机基线：先在匹配分区内均匀抽样，极窄结构再用穷举均匀兜底。"],
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
