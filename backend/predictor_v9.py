from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from statistics import mean, pstdev
from typing import Iterable, Sequence

V9_VERSION = "CEWAY-PRED-V9.0"


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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _weighted_rate(history: Sequence[dict], number: int, area: str, window: int, half_life: float | None = None) -> float:
    rows = history[-window:]
    if not rows:
        return 0.0
    if half_life is None:
        hits = sum(number in row.get(area, []) for row in rows)
        opportunities = sum(len(row.get(area, [])) for row in rows)
        return hits / opportunities if opportunities else 0.0
    decay = math.log(2.0) / max(1.0, half_life)
    weighted_hits = 0.0
    weighted_opportunities = 0.0
    for age, row in enumerate(reversed(rows)):
        weight = math.exp(-decay * age)
        weighted_hits += weight * (number in row.get(area, []))
        weighted_opportunities += weight * len(row.get(area, []))
    return weighted_hits / weighted_opportunities if weighted_opportunities else 0.0


def _gap(history: Sequence[dict], number: int, area: str) -> int:
    for age, row in enumerate(reversed(history)):
        if number in row.get(area, []):
            return age
    return len(history)


def _posterior_rate(hits: float, opportunities: float, prior_rate: float, strength: float = 24.0) -> float:
    alpha = max(0.001, prior_rate * strength)
    beta = max(0.001, (1.0 - prior_rate) * strength)
    return (hits + alpha) / (opportunities + alpha + beta)


def _rates_for_number(history: Sequence[dict], number: int, area: str, windows: Sequence[int], prior_rate: float) -> dict:
    window_rates = []
    for window in windows:
        rows = history[-min(window, len(history)):]
        if not rows:
            continue
        opportunities = sum(len(row.get(area, [])) for row in rows)
        hits = sum(number in row.get(area, []) for row in rows)
        posterior = _posterior_rate(hits, opportunities, prior_rate)
        window_rates.append((window, posterior))
    if not window_rates:
        return {"rates": [], "mean": prior_rate, "std": 0.0, "short": prior_rate, "long": prior_rate}
    values = [value for _, value in window_rates]
    return {
        "rates": window_rates,
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
        "short": window_rates[0][1],
        "long": window_rates[-1][1],
    }


def _percentile(values: Sequence[float], value: float) -> float:
    if not values:
        return 0.5
    less = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return (less + 0.5 * equal) / len(values)


def _number_rows(history: Sequence[dict], spec: GameSpec, area: str, windows: Sequence[int]) -> list[dict]:
    pool = spec.main_pool if area == "front" else spec.bonus_pool
    pick = spec.main_pick if area == "front" else spec.bonus_pick
    prior = pick / pool
    raw = []
    for number in range(1, pool + 1):
        rates = _rates_for_number(history, number, area, windows, prior)
        recency = _weighted_rate(history, number, area, min(max(windows), len(history)), half_life=max(6, min(24, max(windows) / 4)))
        gap = _gap(history, number, area)
        momentum = rates["short"] - rates["long"]
        stability = 1.0 - _clamp(rates["std"] / max(prior * 1.5, 1e-9))
        rate_ratio = rates["mean"] / prior if prior else 1.0
        recency_ratio = recency / prior if prior else 1.0
        raw.append({
            "number": number,
            "prior_rate": prior,
            "window_rates": rates["rates"],
            "posterior_rate": rates["mean"],
            "recency_rate": recency,
            "momentum": momentum,
            "stability": stability,
            "gap": gap,
            "gap_ratio": gap / max(1.0, pool / pick),
            "rate_ratio": rate_ratio,
            "recency_ratio": recency_ratio,
        })

    rate_values = [item["rate_ratio"] for item in raw]
    recency_values = [item["recency_ratio"] for item in raw]
    momentum_values = [item["momentum"] for item in raw]
    gap_values = [math.log1p(item["gap"]) for item in raw]

    for item in raw:
        freq_pct = _percentile(rate_values, item["rate_ratio"])
        recency_pct = _percentile(recency_values, item["recency_ratio"])
        momentum_pct = _percentile(momentum_values, item["momentum"])
        gap_pct = _percentile(gap_values, math.log1p(item["gap"]))
        stability = item["stability"]
        total = 0.46 * freq_pct + 0.26 * recency_pct + 0.14 * momentum_pct + 0.10 * stability + 0.04 * gap_pct
        item["frequency_score"] = round(freq_pct * 100, 2)
        item["recency_score"] = round(recency_pct * 100, 2)
        item["momentum_score"] = round(momentum_pct * 100, 2)
        item["stability_score"] = round(stability * 100, 2)
        item["gap_score"] = round(gap_pct * 100, 2)
        item["total_score"] = round(total * 100, 2)
        item["evidence_strength"] = round(_clamp((len(history) / max(windows)) * 0.7 + stability * 0.3), 3)
        item["explanation"] = (
            f"频率{item['frequency_score']:.1f}、近期{item['recency_score']:.1f}、"
            f"动量{item['momentum_score']:.1f}、稳定{item['stability_score']:.1f}、"
            f"遗漏状态{item['gap_score']:.1f}；V9综合{item['total_score']:.1f}。"
        )

    raw.sort(key=lambda row: (-row["total_score"], -row["evidence_strength"], row["number"]))
    for rank, row in enumerate(raw, 1):
        row["rank"] = rank
    return raw


def score_numbers_v9(history: Sequence[dict], spec: GameSpec, windows: Sequence[int] = (20, 50, 100, 200), history_cutoff_issue: str | None = None) -> dict:
    if history_cutoff_issue is not None:
        cutoff_key = _issue_key(history_cutoff_issue)
        history = [row for row in history if _issue_key(row.get("issue")) <= cutoff_key]
        history = sorted(history, key=lambda row: _issue_key(row.get("issue")))
    if len(history) < 30:
        raise ValueError("V9 至少需要 30 期历史数据")
    usable_windows = tuple(sorted({min(int(window), len(history)) for window in windows if int(window) >= 10}))
    if not usable_windows:
        raise ValueError("windows 不能为空")
    front = _number_rows(history, spec, "front", usable_windows)
    back = _number_rows(history, spec, "back", usable_windows)
    return {
        "version": V9_VERSION,
        "game": spec.game,
        "history_cutoff_issue": history[-1].get("issue"),
        "history_count": len(history),
        "windows": list(usable_windows),
        "front": front,
        "back": back,
        "method": {
            "frequency": 0.46,
            "recency": 0.26,
            "momentum": 0.14,
            "stability": 0.10,
            "gap_descriptor": 0.04,
            "prior": "Beta-Binomial shrinkage toward uniform theoretical rate",
            "claim": "descriptive ranking only; no future-win probability claim",
        },
    }


def _ticket_structure(ticket: Sequence[int], spec: GameSpec) -> dict:
    numbers = sorted(ticket)
    zones = ((1, 12), (13, 24), (25, 35)) if spec.game == "DLT" else ((1, 11), (12, 22), (23, 33))
    zone_counts = tuple(sum(low <= n <= high for n in numbers) for low, high in zones)
    odd = sum(n % 2 for n in numbers)
    total = sum(numbers)
    consecutive_groups = 0
    in_group = False
    for left, right in zip(numbers, numbers[1:]):
        if right == left + 1:
            if not in_group:
                consecutive_groups += 1
                in_group = True
        else:
            in_group = False
    return {"zone_counts": zone_counts, "odd": odd, "sum": total, "consecutive_groups": consecutive_groups}


def _combination_score(ticket: Sequence[int], rows: dict[int, dict], spec: GameSpec) -> float:
    base = mean(rows[number]["total_score"] for number in ticket)
    structure = _ticket_structure(ticket, spec)
    center = spec.main_pick * (spec.main_pool + 1) / 2.0
    sum_distance = abs(structure["sum"] - center) / max(center, 1.0)
    sum_score = 1.0 - _clamp(sum_distance * 2.0)
    zone_nonempty = sum(1 for count in structure["zone_counts"] if count > 0) / 3.0
    parity_balance = 1.0 - abs(structure["odd"] - spec.main_pick / 2.0) / max(spec.main_pick / 2.0, 1.0)
    consecutive_score = 1.0 if structure["consecutive_groups"] <= 2 else 0.72
    return round(0.78 * base + 8.0 * sum_score + 4.0 * zone_nonempty + 3.0 * parity_balance + 2.0 * consecutive_score, 4)


def _portfolio_select(candidates: Sequence[tuple[int, ...]], score_by_ticket: dict[tuple[int, ...], float], ticket_count: int, seed: str) -> list[tuple[int, ...]]:
    if not candidates:
        return []
    rng = random.Random(seed)
    remaining = list(candidates)
    selected: list[tuple[int, ...]] = []
    usage: Counter[int] = Counter()
    pair_usage: Counter[tuple[int, int]] = Counter()
    while remaining and len(selected) < ticket_count:
        best = None
        best_value = None
        for candidate in remaining:
            candidate_set = set(candidate)
            overlap = max((len(candidate_set & set(item)) for item in selected), default=0)
            jaccard = max((len(candidate_set & set(item)) / len(candidate_set | set(item)) for item in selected), default=0.0)
            new_numbers = sum(usage[n] == 0 for n in candidate) / len(candidate)
            pair_reuse = sum(pair_usage[tuple(sorted((left, right)))] for left, right in combinations(candidate, 2))
            score = score_by_ticket[candidate]
            objective = score + 6.0 * new_numbers - 10.0 * jaccard - 1.25 * overlap - 0.45 * pair_reuse
            key = objective + rng.random() * 0.0001
            if best_value is None or key > best_value:
                best_value = key
                best = candidate
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)
        usage.update(best)
        for left, right in combinations(best, 2):
            pair_usage[(left, right)] += 1
    return selected


def _diversity(numbers: Iterable[Iterable[int]]) -> dict:
    rows = [set(row) for row in numbers]
    if len(rows) < 2:
        return {"pair_count": 0, "mean_jaccard": 0.0, "max_jaccard": 0.0}
    values = []
    for left, right in combinations(rows, 2):
        union = left | right
        values.append(len(left & right) / len(union) if union else 1.0)
    return {"pair_count": len(values), "mean_jaccard": round(mean(values), 4), "max_jaccard": round(max(values), 4)}


def _next_issue(issue: str | None) -> str | None:
    if not issue or not str(issue).isdigit():
        return None
    text = str(issue)
    return f"{int(text) + 1:0{len(text)}d}"


def generate_prediction_v9(history: Sequence[dict], spec: GameSpec, budget: int = 20, windows: Sequence[int] = (20, 50, 100, 200), seed: str | int = 42, candidate_band: int = 18, history_cutoff_issue: str | None = None) -> dict:
    if budget < 2:
        raise ValueError("budget 必须 >= 2")
    scored = score_numbers_v9(history, spec, windows, history_cutoff_issue=history_cutoff_issue)
    cutoff_key = _issue_key(scored["history_cutoff_issue"])
    history = [row for row in history if _issue_key(row.get("issue")) <= cutoff_key]
    history = sorted(history, key=lambda row: _issue_key(row.get("issue")))
    ticket_count = max(1, budget // 2)
    front_rows = {row["number"]: row for row in scored["front"]}
    ranked_front = [row["number"] for row in scored["front"]]
    candidate_numbers = ranked_front[:max(spec.main_pick, min(candidate_band, len(ranked_front)))]
    candidates = list(combinations(candidate_numbers, spec.main_pick))
    score_by_ticket = {candidate: _combination_score(candidate, front_rows, spec) for candidate in candidates}
    fronts = _portfolio_select(candidates, score_by_ticket, ticket_count, str(seed))
    back_rows = {row["number"]: row for row in scored["back"]}
    ranked_back = [row["number"] for row in scored["back"]]
    if spec.bonus_pick == 1:
        backs = [(ranked_back[index % len(ranked_back)],) for index in range(ticket_count)]
    else:
        back_candidates = list(combinations(ranked_back[:min(8, len(ranked_back))], spec.bonus_pick))
        back_scores = {candidate: mean(back_rows[n]["total_score"] for n in candidate) for candidate in back_candidates}
        backs = _portfolio_select(back_candidates, back_scores, ticket_count, f"{seed}-back")
    tickets = []
    for index, front in enumerate(fronts):
        back = backs[index % len(backs)] if backs else tuple(ranked_back[:spec.bonus_pick])
        tickets.append({
            "front": list(front),
            "back": list(back),
            "front_display": [f"{n:02d}" for n in front],
            "back_display": [f"{n:02d}" for n in back],
            "score": score_by_ticket.get(front, 0.0),
            "explanation": [front_rows[n]["explanation"] for n in front[:spec.main_pick]],
        })
    tickets.sort(key=lambda item: (-item["score"], item["front"], item["back"]))
    return {
        "schema_version": "ceway.prediction.v9",
        "algorithm_version": V9_VERSION,
        "game": spec.game,
        "history_cutoff_issue": scored["history_cutoff_issue"],
        "recommended_issue": _next_issue(scored["history_cutoff_issue"]),
        "budget": ticket_count * 2,
        "tickets": len(tickets),
        "items": tickets,
        "score_table": scored,
        "portfolio": {"front_diversity": _diversity(t["front"] for t in tickets), "back_diversity": _diversity(t["back"] for t in tickets), "candidate_band": len(candidate_numbers)},
        "research_guard": {"production_enabled": False, "claim": "descriptive ranking and portfolio construction; not a claim of lottery predictability"},
    }


def freeze_prediction(plan: dict) -> dict:
    payload = {"schema_version": plan.get("schema_version"), "algorithm_version": plan.get("algorithm_version"), "game": plan.get("game"), "history_cutoff_issue": plan.get("history_cutoff_issue"), "recommended_issue": plan.get("recommended_issue"), "budget": plan.get("budget"), "items": plan.get("items", [])}
    digest = hashlib.sha256(json_bytes(payload)).hexdigest()
    frozen = dict(plan)
    frozen["freeze_manifest"] = {**payload, "sha256": digest, "frozen": True}
    return frozen


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
