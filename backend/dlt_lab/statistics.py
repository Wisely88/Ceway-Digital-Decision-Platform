from __future__ import annotations

from collections import Counter
from math import log
from statistics import fmean, pstdev
from typing import Mapping, Sequence

from .types import BACK_MAX, FRONT_MAX, Draw, Ticket


def zscores(values: Mapping[int, float | int]) -> dict[int, float]:
    if not values:
        return {}
    mean = fmean(float(value) for value in values.values())
    std = pstdev(float(value) for value in values.values())
    return {key: 0.0 if std == 0 else (float(value) - mean) / std for key, value in values.items()}


def number_frequency(draws: Sequence[Draw], zone: str, window: int | None = None) -> dict[int, float]:
    selected = draws[-window:] if window else draws
    maximum = FRONT_MAX if zone == "front" else BACK_MAX
    counts = {number: 0 for number in range(1, maximum + 1)}
    for draw in selected:
        for number in getattr(draw, zone):
            counts[number] += 1
    denominator = max(1, len(selected))
    return {number: count / denominator for number, count in counts.items()}


def current_omission(draws: Sequence[Draw], zone: str) -> dict[int, int]:
    maximum = FRONT_MAX if zone == "front" else BACK_MAX
    result = {}
    for number in range(1, maximum + 1):
        missing = 0
        for draw in reversed(draws):
            if number in getattr(draw, zone):
                break
            missing += 1
        result[number] = missing
    return result


def number_trends(
    draws: Sequence[Draw],
    zone: str,
    windows: Mapping[str, int] | None = None,
    weights: Mapping[str, float] | None = None,
) -> dict[int, dict[str, float | int]]:
    windows = dict(windows or {"short": 20, "mid": 60, "long": 120})
    weights = dict(weights or {"short": 0.35, "mid": 0.25, "long": 0.20, "omission": 0.20})
    frequencies = {name: number_frequency(draws, zone, int(size)) for name, size in windows.items()}
    frequency_z = {name: zscores(values) for name, values in frequencies.items()}
    omissions = current_omission(draws, zone)
    omission_z = zscores(omissions)
    maximum = FRONT_MAX if zone == "front" else BACK_MAX
    return {
        number: {
            "frequency_short": frequencies["short"][number],
            "frequency_mid": frequencies["mid"][number],
            "frequency_long": frequencies["long"][number],
            "omission": omissions[number],
            "omission_zscore": omission_z[number],
            "trend_score": sum(weights[name] * frequency_z[name][number] for name in ("short", "mid", "long"))
            + weights["omission"] * omission_z[number],
        }
        for number in range(1, maximum + 1)
    }


def front_structure(front: Sequence[int]) -> dict[str, object]:
    numbers = sorted(front)
    tail_counts = Counter(number % 10 for number in numbers)
    return {
        "odd": sum(number % 2 for number in numbers),
        "even": sum(number % 2 == 0 for number in numbers),
        "zones": [
            sum(1 <= number <= 12 for number in numbers),
            sum(13 <= number <= 24 for number in numbers),
            sum(25 <= number <= 35 for number in numbers),
        ],
        "sum": sum(numbers),
        "span": numbers[-1] - numbers[0],
        "consecutive_pairs": sum(right - left == 1 for left, right in zip(numbers, numbers[1:])),
        "same_tail_pairs": sum(count * (count - 1) // 2 for count in tail_counts.values()),
    }


def back_structure(back: Sequence[int]) -> dict[str, int]:
    numbers = sorted(back)
    return {
        "odd": sum(number % 2 for number in numbers),
        "even": sum(number % 2 == 0 for number in numbers),
        "small": sum(number <= 6 for number in numbers),
        "large": sum(number > 6 for number in numbers),
        "sum": sum(numbers),
        "span": numbers[-1] - numbers[0],
    }


def structure_features(ticket: Ticket) -> dict[str, object]:
    return {"front": front_structure(ticket.front), "back": back_structure(ticket.back)}


def structure_score(ticket: Ticket, draws: Sequence[Draw], laplace_lambda: float = 1.0) -> float:
    candidate = front_structure(ticket.front)
    signatures = Counter(
        (front_structure(draw.front)["odd"], tuple(front_structure(draw.front)["zones"]))
        for draw in draws
    )
    signature = (candidate["odd"], tuple(candidate["zones"]))
    categories = max(1, len(signatures))
    probability = (signatures[signature] + laplace_lambda) / (len(draws) + laplace_lambda * categories)
    return log(max(probability, 1e-12))


def ticket_similarity(left: Ticket, right: Ticket, front_weight: float = 0.75) -> float:
    front_left, front_right = set(left.front), set(right.front)
    back_left, back_right = set(left.back), set(right.back)
    front_jaccard = len(front_left & front_right) / len(front_left | front_right)
    back_jaccard = len(back_left & back_right) / len(back_left | back_right)
    return front_weight * front_jaccard + (1 - front_weight) * back_jaccard
