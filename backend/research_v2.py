from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from math import comb, sqrt
from statistics import mean
from typing import Iterable, Sequence


@dataclass(frozen=True)
class GameSpec:
    name: str
    main_pool: int
    main_pick: int
    bonus_pool: int
    bonus_pick: int


SSQ = GameSpec("ssq", 33, 6, 16, 1)
DLT = GameSpec("dlt", 35, 5, 12, 2)


@dataclass(frozen=True)
class TicketConstraints:
    zones: tuple[tuple[int, int], ...] = ()
    allowed_zone_counts: tuple[tuple[int, ...], ...] = ()
    allowed_odd_counts: tuple[int, ...] = ()
    sum_min: int | None = None
    sum_max: int | None = None
    max_consecutive_groups: int | None = None


def history_through_issue(history: Sequence[dict], history_cutoff_issue: str) -> list[dict]:
    """Return only rows known at the declared cutoff issue.

    This is the V2 anti-leakage gate. Every research/backtest caller should
    derive its training history through this function (or an equivalent
    explicit index slice) before feature generation.
    """
    rows = [row for row in history if str(row.get("issue", "")) <= str(history_cutoff_issue)]
    rows.sort(key=lambda row: str(row.get("issue", "")))
    return rows


def intersection_count(a: Iterable[int], b: Iterable[int]) -> int:
    return len(set(a) & set(b))


def collision_profile(
    candidate: Iterable[int],
    history_numbers: Iterable[Iterable[int]],
    max_k: int | None = None,
) -> dict[int, int]:
    candidate = tuple(candidate)
    max_k = len(candidate) if max_k is None else max_k
    counts: Counter[int] = Counter()
    for draw in history_numbers:
        counts[intersection_count(candidate, draw)] += 1
    return {k: counts.get(k, 0) for k in range(max_k + 1)}


def joint_collision_profile(
    candidate_main: Iterable[int],
    candidate_bonus: Iterable[int],
    history: Iterable[dict],
) -> dict[tuple[int, int], int]:
    counts: Counter[tuple[int, int]] = Counter()
    for row in history:
        main_hits = intersection_count(candidate_main, row.get("front", []))
        bonus_hits = intersection_count(candidate_bonus, row.get("back", []))
        counts[(main_hits, bonus_hits)] += 1
    return dict(sorted(counts.items()))


def hypergeom_pmf(population: int, success_states: int, draws: int, k: int) -> float:
    if k < 0 or k > success_states or k > draws:
        return 0.0
    failures = population - success_states
    if draws - k < 0 or draws - k > failures:
        return 0.0
    return comb(success_states, k) * comb(failures, draws - k) / comb(population, draws)


def theoretical_collision_distribution(pool_size: int, pick_size: int) -> dict[int, float]:
    return {
        k: hypergeom_pmf(pool_size, pick_size, pick_size, k)
        for k in range(pick_size + 1)
    }


def expected_collision_counts(pool_size: int, pick_size: int, history_len: int) -> dict[int, float]:
    return {
        k: history_len * probability
        for k, probability in theoretical_collision_distribution(pool_size, pick_size).items()
    }


def collision_z_scores(
    observed: dict[int, int],
    pool_size: int,
    pick_size: int,
    history_len: int,
) -> dict[int, float]:
    scores: dict[int, float] = {}
    for k, probability in theoretical_collision_distribution(pool_size, pick_size).items():
        expected = history_len * probability
        variance = history_len * probability * (1 - probability)
        scores[k] = 0.0 if variance <= 0 else (observed.get(k, 0) - expected) / sqrt(variance)
    return scores


def aggregate_collision_counts(
    tickets: Iterable[Iterable[int]],
    history_numbers: Iterable[Iterable[int]],
    max_k: int,
) -> dict[int, int]:
    """Count all candidate-ticket x historical-draw collision pairs."""
    history_rows = [tuple(draw) for draw in history_numbers]
    counts: Counter[int] = Counter()
    for ticket in tickets:
        for draw in history_rows:
            counts[intersection_count(ticket, draw)] += 1
    return {k: counts.get(k, 0) for k in range(max_k + 1)}


def combination_collision_audit(
    tickets: Iterable[dict],
    history: Sequence[dict],
    spec: GameSpec,
    include_per_ticket: bool = False,
) -> dict:
    """Audit complete candidate combinations against all history at the cutoff.

    The aggregate Z values are descriptive only because candidate-history pairs
    are not fully independent when tickets overlap. They are useful for scale
    comparison, not as formal proof of predictive signal.
    """
    ticket_rows = [
        {
            "front": tuple(sorted(ticket.get("front", []))),
            "back": tuple(sorted(ticket.get("back", []))),
        }
        for ticket in tickets
    ]
    front_history = [tuple(row.get("front", [])) for row in history]
    back_history = [tuple(row.get("back", [])) for row in history]
    pair_count = len(ticket_rows) * len(history)

    front_observed = aggregate_collision_counts(
        [ticket["front"] for ticket in ticket_rows], front_history, spec.main_pick
    )
    back_observed = aggregate_collision_counts(
        [ticket["back"] for ticket in ticket_rows], back_history, spec.bonus_pick
    )
    front_expected = expected_collision_counts(spec.main_pool, spec.main_pick, pair_count)
    back_expected = expected_collision_counts(spec.bonus_pool, spec.bonus_pick, pair_count)
    front_z = collision_z_scores(front_observed, spec.main_pool, spec.main_pick, pair_count)
    back_z = collision_z_scores(back_observed, spec.bonus_pool, spec.bonus_pick, pair_count)

    joint: Counter[str] = Counter()
    for ticket in ticket_rows:
        for row in history:
            main_hits = intersection_count(ticket["front"], row.get("front", []))
            bonus_hits = intersection_count(ticket["back"], row.get("back", []))
            joint[f"{main_hits}+{bonus_hits}"] += 1

    audit = {
        "ticket_count": len(ticket_rows),
        "history_count": len(history),
        "pair_count": pair_count,
        "front": {
            "observed": front_observed,
            "expected": {k: round(value, 4) for k, value in front_expected.items()},
            "descriptive_z": {k: round(value, 4) for k, value in front_z.items()},
        },
        "back": {
            "observed": back_observed,
            "expected": {k: round(value, 4) for k, value in back_expected.items()},
            "descriptive_z": {k: round(value, 4) for k, value in back_z.items()},
        },
        "joint_observed": dict(sorted(joint.items())),
    }

    if include_per_ticket:
        audit["per_ticket"] = [
            {
                "front": list(ticket["front"]),
                "back": list(ticket["back"]),
                "front_profile": collision_profile(ticket["front"], front_history, spec.main_pick),
                "back_profile": collision_profile(ticket["back"], back_history, spec.bonus_pick),
                "joint_profile": {
                    f"{main_hits}+{bonus_hits}": count
                    for (main_hits, bonus_hits), count in joint_collision_profile(
                        ticket["front"], ticket["back"], history
                    ).items()
                },
            }
            for ticket in ticket_rows
        ]
    return audit


def zone_counts(ticket: Iterable[int], zones: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    numbers = tuple(ticket)
    return tuple(sum(1 for number in numbers if low <= number <= high) for low, high in zones)


def odd_count(ticket: Iterable[int]) -> int:
    return sum(1 for number in ticket if number % 2)


def consecutive_groups(ticket: Iterable[int]) -> int:
    numbers = sorted(set(ticket))
    groups = 0
    in_group = False
    for left, right in zip(numbers, numbers[1:]):
        if right == left + 1:
            if not in_group:
                groups += 1
                in_group = True
        else:
            in_group = False
    return groups


def passes_constraints(ticket: Iterable[int], constraints: TicketConstraints) -> bool:
    numbers = tuple(sorted(ticket))
    if constraints.zones and constraints.allowed_zone_counts:
        if zone_counts(numbers, constraints.zones) not in constraints.allowed_zone_counts:
            return False
    if constraints.allowed_odd_counts and odd_count(numbers) not in constraints.allowed_odd_counts:
        return False
    total = sum(numbers)
    if constraints.sum_min is not None and total < constraints.sum_min:
        return False
    if constraints.sum_max is not None and total > constraints.sum_max:
        return False
    if constraints.max_consecutive_groups is not None:
        if consecutive_groups(numbers) > constraints.max_consecutive_groups:
            return False
    return True


def conditional_random_tickets(
    pool_size: int,
    pick_size: int,
    ticket_count: int,
    constraints: TicketConstraints | None = None,
    seed: str | int = 42,
    max_attempts: int = 1_000_000,
) -> list[tuple[int, ...]]:
    """Generate a reproducible structure-matched random control group."""
    constraints = constraints or TicketConstraints()
    rng = random.Random(str(seed))
    tickets: set[tuple[int, ...]] = set()
    attempts = 0
    while len(tickets) < ticket_count and attempts < max_attempts:
        attempts += 1
        ticket = tuple(sorted(rng.sample(range(1, pool_size + 1), pick_size)))
        if passes_constraints(ticket, constraints):
            tickets.add(ticket)
    if len(tickets) < ticket_count:
        raise RuntimeError(
            f"Only generated {len(tickets)} conditional-random tickets after {attempts} attempts."
        )
    return sorted(tickets)


def constraints_like_ticket(
    ticket: Iterable[int],
    zones: tuple[tuple[int, int], ...],
    *,
    sum_tolerance: int | None,
) -> TicketConstraints:
    numbers = tuple(sorted(ticket))
    total = sum(numbers)
    return TicketConstraints(
        zones=zones,
        allowed_zone_counts=(zone_counts(numbers, zones),) if zones else (),
        allowed_odd_counts=(odd_count(numbers),),
        sum_min=None if sum_tolerance is None else total - sum_tolerance,
        sum_max=None if sum_tolerance is None else total + sum_tolerance,
        max_consecutive_groups=consecutive_groups(numbers),
    )


def expand_plan_tickets(plan: dict, spec: GameSpec) -> list[dict]:
    """Expand single or dantuo plans into complete ticket rows."""
    if plan.get("mode") != "dantuo":
        return [
            {
                "front": sorted(item.get("front", [])),
                "back": sorted(item.get("back", [])),
            }
            for item in plan.get("items", [])
        ]

    dan = list(plan.get("front_dan", []))
    tuo = list(plan.get("front_tuo", []))
    back_pool = list(plan.get("back", []))
    need_tuo = max(0, spec.main_pick - len(dan))
    rows = []
    for front_combo in combinations(tuo, need_tuo):
        front = sorted(dan + list(front_combo))
        for back_combo in combinations(back_pool, spec.bonus_pick):
            rows.append({"front": front, "back": sorted(back_combo)})
    return rows


def structure_matched_random_plan(
    reference_plan: dict,
    spec: GameSpec,
    *,
    seed: str | int,
    main_zones: tuple[tuple[int, int], ...],
    bonus_zones: tuple[tuple[int, int], ...],
    main_sum_tolerance: int = 5,
    bonus_sum_tolerance: int | None = 2,
) -> dict:
    """Build a single-ticket baseline matched to each reference ticket.

    Each baseline ticket matches its paired CEWAY ticket on zone allocation,
    odd/even count, an allowed sum band, and maximum consecutive-group count.
    For SSQ blue-ball (pick=1), callers should pass bonus_sum_tolerance=None so
    the random control does not collapse to the exact same number.
    """
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
            front = conditional_random_tickets(
                spec.main_pool,
                spec.main_pick,
                1,
                main_constraints,
                seed=f"{seed}-front-{index}-{retry}",
                max_attempts=100_000,
            )[0]
            back = conditional_random_tickets(
                spec.bonus_pool,
                spec.bonus_pick,
                1,
                bonus_constraints,
                seed=f"{seed}-back-{index}-{retry}",
                max_attempts=100_000,
            )[0]
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
                "explanation": ["V2 条件随机基线：结构匹配，仅用于对照。"],
            }
        )

    return {
        "mode": "single",
        "strategy": "random",
        "baseline_type": "conditional_random_v2",
        "cost": len(output) * 2,
        "tickets": len(output),
        "items": output,
        "score": 0,
        "reason": "V2 条件随机对照组：逐票匹配分区、奇偶、和值带与连号结构。",
    }


def jaccard_similarity(a: Iterable[int], b: Iterable[int]) -> float:
    left, right = set(a), set(b)
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def symmetric_difference_distance(a: Iterable[int], b: Iterable[int]) -> int:
    return len(set(a) ^ set(b))


def diversity_summary(tickets: Iterable[Iterable[int]]) -> dict[str, float | int]:
    rows = [tuple(ticket) for ticket in tickets]
    if len(rows) < 2:
        return {
            "pair_count": 0,
            "mean_jaccard": 0.0,
            "max_jaccard": 0.0,
            "mean_symdiff": 0.0,
            "min_symdiff": 0.0,
        }
    similarities: list[float] = []
    distances: list[int] = []
    for left, right in combinations(rows, 2):
        similarities.append(jaccard_similarity(left, right))
        distances.append(symmetric_difference_distance(left, right))
    return {
        "pair_count": len(similarities),
        "mean_jaccard": mean(similarities),
        "max_jaccard": max(similarities),
        "mean_symdiff": mean(distances),
        "min_symdiff": min(distances),
    }


def bootstrap_mean_ci(
    values: Iterable[float],
    confidence: float = 0.95,
    samples: int = 5000,
    seed: str | int = 42,
) -> dict[str, float | int]:
    rows = list(values)
    if not rows:
        raise ValueError("values must not be empty")
    if len(rows) == 1:
        value = float(rows[0])
        return {"mean": value, "low": value, "high": value, "n": 1}
    rng = random.Random(str(seed))
    n = len(rows)
    bootstrap_means = []
    for _ in range(samples):
        bootstrap_means.append(mean(rows[rng.randrange(n)] for _ in range(n)))
    bootstrap_means.sort()
    alpha = 1 - confidence
    low_index = max(0, int((alpha / 2) * (samples - 1)))
    high_index = min(samples - 1, int((1 - alpha / 2) * (samples - 1)))
    return {
        "mean": mean(rows),
        "low": bootstrap_means[low_index],
        "high": bootstrap_means[high_index],
        "n": n,
    }


def _canonical_ticket_rows(tickets: Iterable[dict]) -> list[dict]:
    canonical = []
    for ticket in tickets:
        canonical.append(
            {
                "front": sorted(int(number) for number in ticket.get("front", [])),
                "back": sorted(int(number) for number in ticket.get("back", [])),
            }
        )
    return canonical


def build_freeze_manifest(
    *,
    game: str,
    target_issue: str,
    history_cutoff_issue: str,
    algorithm_version: str,
    parameters: dict,
    tickets: Iterable[dict],
    budget: int,
    seed: str | int | None = None,
) -> dict:
    """Create an immutable, content-addressed prediction snapshot.

    The digest excludes the digest field itself and is stable under JSON key
    ordering. A frozen plan must be superseded by a new manifest rather than
    edited in place.
    """
    payload = {
        "schema_version": "ceway.freeze.v2",
        "game": game,
        "target_issue": str(target_issue),
        "history_cutoff_issue": str(history_cutoff_issue),
        "algorithm_version": algorithm_version,
        "parameters": parameters,
        "tickets": _canonical_ticket_rows(tickets),
        "budget": int(budget),
        "seed": None if seed is None else str(seed),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload
