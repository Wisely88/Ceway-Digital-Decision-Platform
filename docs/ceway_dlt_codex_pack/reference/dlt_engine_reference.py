"""Pure-Python reference implementation for Ceway DLT domain logic.

This file intentionally has no FastAPI/DB/network dependencies.
Codex should adapt names/packaging to the actual repository while preserving behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb
import random
import secrets
from typing import Iterable, Mapping, Sequence

FRONT_MIN, FRONT_MAX, FRONT_PICK = 1, 35, 5
BACK_MIN, BACK_MAX, BACK_PICK = 1, 12, 2


class DltValidationError(ValueError):
    pass


def _sorted_unique(nums: Sequence[int], lo: int, hi: int, *, expected: int | None = None) -> tuple[int, ...]:
    values = tuple(sorted(int(x) for x in nums))
    if len(set(values)) != len(values):
        raise DltValidationError("numbers must be unique within a zone")
    if any(x < lo or x > hi for x in values):
        raise DltValidationError(f"number outside range {lo}..{hi}")
    if expected is not None and len(values) != expected:
        raise DltValidationError(f"expected {expected} numbers, got {len(values)}")
    return values


def mask(nums: Iterable[int]) -> int:
    value = 0
    for n in nums:
        if n < 1 or n > 63:
            raise DltValidationError("mask supports numbers 1..63")
        value |= 1 << (n - 1)
    return value


@dataclass(frozen=True)
class Draw:
    issue: str
    front: tuple[int, ...]
    back: tuple[int, ...]

    @classmethod
    def create(cls, issue: str, front: Sequence[int], back: Sequence[int]) -> "Draw":
        return cls(
            issue=str(issue),
            front=_sorted_unique(front, FRONT_MIN, FRONT_MAX, expected=FRONT_PICK),
            back=_sorted_unique(back, BACK_MIN, BACK_MAX, expected=BACK_PICK),
        )

    @property
    def front_mask(self) -> int:
        return mask(self.front)

    @property
    def back_mask(self) -> int:
        return mask(self.back)


@dataclass(frozen=True)
class Ticket:
    front: tuple[int, ...]
    back: tuple[int, ...]

    @classmethod
    def create(cls, front: Sequence[int], back: Sequence[int]) -> "Ticket":
        return cls(
            front=_sorted_unique(front, FRONT_MIN, FRONT_MAX, expected=FRONT_PICK),
            back=_sorted_unique(back, BACK_MIN, BACK_MAX, expected=BACK_PICK),
        )

    @property
    def front_mask(self) -> int:
        return mask(self.front)

    @property
    def back_mask(self) -> int:
        return mask(self.back)


@dataclass(frozen=True)
class CollisionProfile:
    # index 0..7
    n_total_hits: tuple[int, ...]
    # rows front hits 0..5, columns back hits 0..2
    n_front_back: tuple[tuple[int, int, int], ...]

    @property
    def history_draw_count(self) -> int:
        return sum(self.n_total_hits)

    @property
    def max_total_hits(self) -> int:
        return max((k for k, n in enumerate(self.n_total_hits) if n), default=0)

    @property
    def scarcity_key(self) -> tuple[int, ...]:
        # High collision orders first: N7,N6,...N1. Ascending => historically scarcer high collisions first.
        return tuple(self.n_total_hits[k] for k in range(7, 0, -1))


def hit_pair(ticket: Ticket, draw: Draw) -> tuple[int, int]:
    return (
        (ticket.front_mask & draw.front_mask).bit_count(),
        (ticket.back_mask & draw.back_mask).bit_count(),
    )


def collision_profile(ticket: Ticket, draws: Sequence[Draw]) -> CollisionProfile:
    totals = [0] * 8
    matrix = [[0] * 3 for _ in range(6)]
    for draw in draws:
        a, b = hit_pair(ticket, draw)
        matrix[a][b] += 1
        totals[a + b] += 1
    return CollisionProfile(
        n_total_hits=tuple(totals),
        n_front_back=tuple(tuple(row) for row in matrix),
    )


def aggregate_collision_profiles(profiles: Sequence[CollisionProfile]) -> dict[str, object]:
    m_total = [0] * 8
    u_total = [0] * 8
    m_ab = [[0] * 3 for _ in range(6)]
    u_ab = [[0] * 3 for _ in range(6)]

    for p in profiles:
        for k, n in enumerate(p.n_total_hits):
            m_total[k] += n
            if n > 0:
                u_total[k] += 1
        for a in range(6):
            for b in range(3):
                n = p.n_front_back[a][b]
                m_ab[a][b] += n
                if n > 0:
                    u_ab[a][b] += 1

    return {
        "m_total_hits": tuple(m_total),
        "u_total_hits": tuple(u_total),
        "m_front_back": tuple(tuple(r) for r in m_ab),
        "u_front_back": tuple(tuple(r) for r in u_ab),
    }


def front_structure(front: Sequence[int]) -> dict[str, object]:
    nums = _sorted_unique(front, FRONT_MIN, FRONT_MAX, expected=FRONT_PICK)
    odd = sum(n % 2 for n in nums)
    zones = (
        sum(1 <= n <= 12 for n in nums),
        sum(13 <= n <= 24 for n in nums),
        sum(25 <= n <= 35 for n in nums),
    )
    consecutive_pairs = sum(1 for a, b in zip(nums, nums[1:]) if b - a == 1)
    tail_counts: dict[int, int] = {}
    for n in nums:
        tail_counts[n % 10] = tail_counts.get(n % 10, 0) + 1
    same_tail_pairs = sum(c * (c - 1) // 2 for c in tail_counts.values())
    return {
        "odd": odd,
        "even": FRONT_PICK - odd,
        "zones": zones,
        "sum": sum(nums),
        "span": nums[-1] - nums[0],
        "consecutive_pairs": consecutive_pairs,
        "same_tail_pairs": same_tail_pairs,
    }


def number_frequency(draws: Sequence[Draw], *, zone: str, window: int | None = None) -> dict[int, float]:
    if zone not in {"front", "back"}:
        raise DltValidationError("zone must be front or back")
    selected = draws[-window:] if window else draws
    max_n = FRONT_MAX if zone == "front" else BACK_MAX
    counts = {n: 0 for n in range(1, max_n + 1)}
    if not selected:
        return {n: 0.0 for n in counts}
    for draw in selected:
        for n in getattr(draw, zone):
            counts[n] += 1
    total = len(selected)
    return {n: c / total for n, c in counts.items()}


def current_omission(draws: Sequence[Draw], *, zone: str) -> dict[int, int]:
    if zone not in {"front", "back"}:
        raise DltValidationError("zone must be front or back")
    max_n = FRONT_MAX if zone == "front" else BACK_MAX
    result: dict[int, int] = {}
    for n in range(1, max_n + 1):
        omission = 0
        for draw in reversed(draws):
            if n in getattr(draw, zone):
                break
            omission += 1
        result[n] = omission
    return result


def zscores(values: Mapping[int, float | int]) -> dict[int, float]:
    if not values:
        return {}
    xs = [float(v) for v in values.values()]
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    std = var ** 0.5
    if std == 0:
        return {k: 0.0 for k in values}
    return {k: (float(v) - mean) / std for k, v in values.items()}


def compound_bet_count(front_count: int, back_count: int) -> int:
    if front_count < FRONT_PICK or front_count > FRONT_MAX:
        raise DltValidationError("invalid front compound count")
    if back_count < BACK_PICK or back_count > BACK_MAX:
        raise DltValidationError("invalid back compound count")
    return comb(front_count, FRONT_PICK) * comb(back_count, BACK_PICK)


def dantuo_bet_count(front_dan: int, front_tuo: int, back_dan: int, back_tuo: int) -> int:
    if not (0 <= front_dan <= 4):
        raise DltValidationError("front dan must be 0..4")
    if not (0 <= back_dan <= 1):
        raise DltValidationError("back dan must be 0..1")
    need_front = FRONT_PICK - front_dan
    need_back = BACK_PICK - back_dan
    if front_tuo < need_front or back_tuo < need_back:
        raise DltValidationError("not enough tuo numbers")
    return comb(front_tuo, need_front) * comb(back_tuo, need_back)


def bet_cost_yuan(expanded_bets: int, *, addon: bool, multiplier: int) -> int:
    if expanded_bets < 1:
        raise DltValidationError("expanded_bets must be >=1")
    if multiplier < 1 or multiplier > 99:
        raise DltValidationError("multiplier must be 1..99")
    unit = 2 + (1 if addon else 0)
    return expanded_bets * unit * multiplier


def generate_random_singles(count: int, *, seed: int | None = None) -> list[Ticket]:
    if count < 1:
        raise DltValidationError("count must be >=1")
    rng = random.Random(seed) if seed is not None else secrets.SystemRandom()
    tickets: list[Ticket] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    while len(tickets) < count:
        front = tuple(sorted(rng.sample(range(FRONT_MIN, FRONT_MAX + 1), FRONT_PICK)))
        back = tuple(sorted(rng.sample(range(BACK_MIN, BACK_MAX + 1), BACK_PICK)))
        key = (front, back)
        if key in seen:
            continue
        seen.add(key)
        tickets.append(Ticket(front=front, back=back))
    return tickets
