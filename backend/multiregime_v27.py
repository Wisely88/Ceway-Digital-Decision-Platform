from __future__ import annotations

from collections import Counter
from itertools import combinations
from statistics import mean
from typing import Iterable, Sequence

from generator import TICKET_PRICE, attach_budget_analysis, format_numbers, ssq_format_numbers
from multiregime_v25 import DLT, SSQ, ROLE_WEIGHTS, GameSpec, score_regimes
from multiregime_v26 import CONSTRAINTS, _collision_metrics, _core_pool, _cutoff, _structure_quality
from research_v2 import combination_collision_audit, diversity_summary, intersection_count, jaccard_similarity, joint_collision_profile, passes_constraints


MULTIREGIME_V27_VERSION = "multi-regime-scarcity-combo-v2.7"

# V2.7 is layered on top of frozen V2.6. V2.6 itself must remain unchanged.
# The 50/30/20 regime split now applies to COMPLETE COMBINATION ORIGINS, not
# only number-level exposure.
COMBINATION_TRACK_WEIGHTS = dict(ROLE_WEIGHTS)
TRACK_POOL_SIZE = {"DLT": 12, "SSQ": 12}
BACK_TRACK_POOL_SIZE = {"DLT": 8, "SSQ": 10}
TRACK_COMBO_QUALITY_WEIGHTS = {"average": 0.70, "minimum": 0.30}
TRACK_SCORE_WEIGHTS = {
    "track_quality": 0.55,
    "collision_calibration": 0.25,
    "structure_quality": 0.20,
}
CROSS_TRACK_PENALTIES = {
    "max_jaccard": 0.08,
    "number_exposure": 0.03,
    "pair_reuse": 0.04,
}


def _scarcity_number_key(row: dict) -> tuple:
    """Frozen V2.7 scarcity-pool ordering.

    Primary sort is V2.5 scarcity_score. Ties are resolved by the components
    that define scarcity state, in a deterministic order. A low number is used
    only as the final stable tie-breaker; there is no manual selection step.
    """
    return (
        -float(row["scarcity_score"]),
        -float(row["gap_percentile"]),
        -float(row["divergence_score"]),
        -float(row["rarity7"]),
        -float(row["rarity20"]),
        -float(row["rarity3"]),
        int(row["number"]),
    )


def _track_number_key(row: dict, track: str) -> tuple:
    if track == "scarcity":
        return _scarcity_number_key(row)
    if track == "evidence":
        return (-float(row["evidence_score"]), int(row["number"]))
    if track == "neutral":
        return (-float(row["neutral_score"]), int(row["number"]))
    raise ValueError(f"Unknown V2.7 track: {track}")


def _ordered_track_pool(rows: list[dict], track: str, pool_size: int) -> list[dict]:
    ordered = sorted(rows, key=lambda row: _track_number_key(row, track))
    output = []
    for rank, row in enumerate(ordered[:pool_size], 1):
        copied = dict(row)
        copied["track"] = track
        copied["track_pool_rank"] = rank
        output.append(copied)
    return output


def _combo_track_quality(candidate: tuple[int, ...], row_by_number: dict[int, dict], track: str) -> dict:
    values = [float(row_by_number[number][f"{track}_score"]) for number in candidate]
    average_score = mean(values)
    minimum_score = min(values)
    quality = (
        TRACK_COMBO_QUALITY_WEIGHTS["average"] * average_score
        + TRACK_COMBO_QUALITY_WEIGHTS["minimum"] * minimum_score
    )
    return {
        "average": round(average_score, 6),
        "minimum": round(minimum_score, 6),
        "quality": round(quality, 6),
    }


def _track_candidate_records(
    rows: list[dict],
    history: Sequence[dict],
    spec: GameSpec,
    *,
    area: str,
    track: str,
) -> tuple[list[dict], list[dict]]:
    pick_size = spec.main_pick if area == "front" else spec.bonus_pick
    pool_size = spec.main_pool if area == "front" else spec.bonus_pool
    candidate_pool_size = TRACK_POOL_SIZE[spec.game] if area == "front" else BACK_TRACK_POOL_SIZE[spec.game]
    pool_rows = _ordered_track_pool(rows, track, candidate_pool_size)
    pool_numbers = tuple(int(row["number"]) for row in pool_rows)
    row_by_number = {int(row["number"]): row for row in rows}
    history_numbers = [tuple(int(number) for number in row.get(area, [])) for row in history]
    constraints = CONSTRAINTS[spec.game] if area == "front" else None

    records: list[dict] = []
    for candidate in combinations(pool_numbers, pick_size):
        candidate = tuple(sorted(candidate))
        if area == "front" and constraints is not None and not passes_constraints(candidate, constraints):
            continue
        track_quality = _combo_track_quality(candidate, row_by_number, track)
        collision = _collision_metrics(candidate, history_numbers, pool_size=pool_size, pick_size=pick_size)
        structure_quality = _structure_quality(candidate, constraints) if area == "front" and constraints is not None else 1.0
        rank_score = (
            TRACK_SCORE_WEIGHTS["track_quality"] * float(track_quality["quality"])
            + TRACK_SCORE_WEIGHTS["collision_calibration"] * float(collision["calibration_score"])
            + TRACK_SCORE_WEIGHTS["structure_quality"] * float(structure_quality)
        )
        records.append(
            {
                "track": track,
                "numbers": list(candidate),
                "track_quality": track_quality,
                "structure_quality": round(float(structure_quality), 6),
                "collision": collision,
                "rank_score": round(rank_score, 6),
            }
        )

    records.sort(
        key=lambda item: (
            -float(item["rank_score"]),
            -float(item["track_quality"]["minimum"]),
            float(item["collision"]["mean_abs_z"]),
            tuple(item["numbers"]),
        )
    )
    for rank, record in enumerate(records, 1):
        record["track_rank"] = rank
    return pool_rows, records


def _track_quotas(ticket_count: int) -> dict[str, int]:
    evidence = int(round(ticket_count * COMBINATION_TRACK_WEIGHTS["evidence"]))
    scarcity = int(round(ticket_count * COMBINATION_TRACK_WEIGHTS["scarcity"]))
    neutral = ticket_count - evidence - scarcity
    return {"evidence": evidence, "scarcity": scarcity, "neutral": neutral}


def _track_sequence(ticket_count: int) -> list[str]:
    quotas = _track_quotas(ticket_count)
    remaining = dict(quotas)
    order = ("evidence", "scarcity", "evidence", "neutral", "evidence", "scarcity")
    output: list[str] = []
    while len(output) < ticket_count:
        progressed = False
        for track in order:
            if remaining.get(track, 0) > 0:
                output.append(track)
                remaining[track] -= 1
                progressed = True
                if len(output) >= ticket_count:
                    break
        if not progressed:
            break
    return output


def _select_complete_track_portfolio(track_records: dict[str, list[dict]], ticket_count: int) -> list[dict]:
    sequence = _track_sequence(ticket_count)
    selected: list[dict] = []
    used_combinations: set[tuple[int, ...]] = set()
    usage: Counter[int] = Counter()
    pair_usage: Counter[tuple[int, int]] = Counter()

    for track in sequence:
        best = None
        best_key = None
        for candidate in track_records[track]:
            numbers = tuple(int(number) for number in candidate["numbers"])
            if numbers in used_combinations:
                continue
            max_jaccard = max(
                (jaccard_similarity(numbers, item["numbers"]) for item in selected),
                default=0.0,
            )
            average_usage = sum(usage[number] for number in numbers) / max(1, len(numbers) * max(1, len(selected)))
            candidate_pairs = tuple(combinations(numbers, 2))
            reused_pairs = sum(pair_usage[pair] for pair in candidate_pairs) / max(1, len(candidate_pairs))
            objective = (
                float(candidate["rank_score"])
                - CROSS_TRACK_PENALTIES["max_jaccard"] * max_jaccard
                - CROSS_TRACK_PENALTIES["number_exposure"] * average_usage
                - CROSS_TRACK_PENALTIES["pair_reuse"] * reused_pairs
            )
            key = (
                objective,
                float(candidate["rank_score"]),
                -int(candidate["track_rank"]),
                -max_jaccard,
                tuple(-number for number in numbers),
            )
            if best_key is None or key > best_key:
                best_key = key
                best = candidate
        if best is None:
            raise RuntimeError(f"V2.7 could not fill {track} track quota")
        copied = dict(best)
        copied["portfolio_objective"] = round(float(best_key[0]), 6)
        selected.append(copied)
        numbers = tuple(int(number) for number in best["numbers"])
        used_combinations.add(numbers)
        usage.update(numbers)
        pair_usage.update(combinations(numbers, 2))
    return selected


def _select_back_for_track(back_records: dict[str, list[dict]], track: str, index_by_track: Counter[str]) -> dict:
    records = back_records[track]
    if not records:
        raise RuntimeError(f"V2.7 has no back candidates for {track}")
    index = index_by_track[track] % len(records)
    index_by_track[track] += 1
    return records[index]


def _scarcity_analysis(pool_rows: list[dict], records: list[dict]) -> dict:
    return {
        "number_ordering": {
            "primary": "scarcity_score desc",
            "tie_breakers": [
                "gap_percentile desc",
                "divergence_score desc",
                "rarity7 desc",
                "rarity20 desc",
                "rarity3 desc",
                "number asc",
            ],
            "manual_selection": False,
        },
        "pool": pool_rows,
        "pool_size": len(pool_rows),
        "combination_count_after_constraints": len(records),
        "combination_ordering": {
            "track_quality": "0.70 * average scarcity_score + 0.30 * minimum scarcity_score",
            "rank_score": "0.55 * track_quality + 0.25 * collision_calibration + 0.20 * structure_quality",
            "tie_breakers": ["minimum scarcity desc", "mean_abs_collision_z asc", "numbers asc"],
        },
        # Full list is intentionally persisted. Review must replay this ranking,
        # not regenerate it after seeing the target draw.
        "full_combination_ranking": records,
    }


def review_scarcity_ranking(plan: dict, actual_front: Iterable[int], actual_back: Iterable[int]) -> dict:
    """Review a frozen V2.7 scarcity ranking without regenerating candidates."""
    actual_front_set = set(int(number) for number in actual_front)
    actual_back_set = set(int(number) for number in actual_back)
    analysis = plan["scarcity_analysis"]

    def review_area(area: str, actual: set[int]) -> dict:
        section = analysis[area]
        pool = section["pool"]
        ranking = section["full_combination_ranking"]
        pool_numbers = [int(row["number"]) for row in pool]
        pool_hits = sorted(set(pool_numbers) & actual)
        number_rows = [
            {
                "pool_rank": int(row["track_pool_rank"]),
                "number": int(row["number"]),
                "hit": int(row["number"]) in actual,
                "scarcity_score": float(row["scarcity_score"]),
                "gap": int(row["gap"]),
            }
            for row in pool
        ]

        evaluated = []
        exact_rank = None
        for row in ranking:
            hits = intersection_count(row["numbers"], actual)
            rank = int(row["track_rank"])
            evaluated.append((rank, hits, row))
            if set(int(number) for number in row["numbers"]) == actual:
                exact_rank = rank
        best_rank, best_hits, best_row = max(evaluated, key=lambda item: (item[1], -item[0])) if evaluated else (0, 0, {})
        first_rank_by_hits: dict[str, int] = {}
        for rank, hits, _row in evaluated:
            key = str(hits)
            if key not in first_rank_by_hits:
                first_rank_by_hits[key] = rank

        buckets = {}
        for limit in (10, 50, 100, len(evaluated)):
            if limit <= 0:
                continue
            rows = evaluated[: min(limit, len(evaluated))]
            if not rows:
                continue
            label = "all" if limit == len(evaluated) else f"top{limit}"
            hits = [item[1] for item in rows]
            buckets[label] = {
                "count": len(rows),
                "max_hits": max(hits),
                "mean_hits": round(mean(hits), 6),
                "count_ge_2": sum(value >= 2 for value in hits),
                "count_ge_3": sum(value >= 3 for value in hits),
                "count_ge_4": sum(value >= 4 for value in hits),
            }

        return {
            "pool_hits": pool_hits,
            "pool_hit_count": len(pool_hits),
            "number_ranking_review": number_rows,
            "exact_actual_combination_rank": exact_rank,
            "best_matching_combination": list(best_row.get("numbers", [])),
            "best_matching_rank": best_rank or None,
            "best_matching_hits": best_hits,
            "first_rank_by_hit_count": first_rank_by_hits,
            "rank_buckets": buckets,
        }

    return {
        "generator_version": plan.get("generator_version"),
        "history_cutoff_issue": plan.get("history_cutoff_issue"),
        "front": review_area("front", actual_front_set),
        "back": review_area("back", actual_back_set),
    }


def generate_multiregime_scarcity_combo_plan(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    budget: int = 20,
    strategy: str = "balanced",
    history_cutoff_issue: str | None = None,
) -> dict:
    training = _cutoff(history, history_cutoff_issue)
    if len(training) < 30:
        raise ValueError("V2.7 requires at least 30 historical draws")

    ticket_count = max(1, budget // TICKET_PRICE)
    front_rows = score_regimes(training, spec, area="front")
    back_rows = score_regimes(training, spec, area="back")

    front_pools: dict[str, list[dict]] = {}
    front_records: dict[str, list[dict]] = {}
    back_pools: dict[str, list[dict]] = {}
    back_records: dict[str, list[dict]] = {}
    for track in ("evidence", "scarcity", "neutral"):
        front_pools[track], front_records[track] = _track_candidate_records(front_rows, training, spec, area="front", track=track)
        back_pools[track], back_records[track] = _track_candidate_records(back_rows, training, spec, area="back", track=track)

    selected_fronts = _select_complete_track_portfolio(front_records, ticket_count)
    back_index: Counter[str] = Counter()
    items = []
    for front_record in selected_fronts:
        track = str(front_record["track"])
        back_record = _select_back_for_track(back_records, track, back_index)
        front = [int(number) for number in front_record["numbers"]]
        back = [int(number) for number in back_record["numbers"]]
        joint = {
            f"{main_hits}+{bonus_hits}": count
            for (main_hits, bonus_hits), count in joint_collision_profile(front, back, training).items()
        }
        combined_score = 0.82 * float(front_record["rank_score"]) + 0.18 * float(back_record["rank_score"])
        items.append(
            {
                "origin_track": track,
                "front": front,
                "back": back,
                "front_display": format_numbers(front) if spec.game == "DLT" else ssq_format_numbers(front),
                "back_display": format_numbers(back) if spec.game == "DLT" else ssq_format_numbers(back),
                "score": round(combined_score * 100.0, 4),
                "rank_score": round(combined_score, 6),
                "front_track_rank": int(front_record["track_rank"]),
                "back_track_rank": int(back_record["track_rank"]),
                "front_track_quality": front_record["track_quality"],
                "front_structure_quality": front_record["structure_quality"],
                "front_collision": front_record["collision"],
                "back_collision": back_record["collision"],
                "joint_collision_profile": joint,
                "explanation": [
                    f"V2.7 {track} 完整组合轨：号码池独立排序、完整组合独立碰撞/结构评分，再按 50/30/20 组合来源配额进入最终组合。"
                ],
            }
        )

    core_reference = max(
        items,
        key=lambda item: (float(item["rank_score"]), -int(item["front_track_rank"]), tuple(-number for number in item["front"])),
    )
    quotas = _track_quotas(ticket_count)
    audit = combination_collision_audit(items, training, spec, include_per_ticket=False)
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": MULTIREGIME_V27_VERSION,
        "algorithm_version": f"CEWAY-FWD-{spec.game}-{MULTIREGIME_V27_VERSION}",
        "cost": len(items) * TICKET_PRICE,
        "tickets": len(items),
        "items": items,
        "score": round(sum(float(item["score"]) for item in items), 2),
        "reason": "V2.7 research candidate: complete-combination Evidence/Scarcity/Neutral tracks, with a fully ordered scarcity pool and replayable scarcity combination ranking.",
        "history_cutoff_issue": training[-1].get("issue"),
        "production_enabled": False,
        "research_guard": "Scarcity and collision rankings are descriptive research features, not future-win probabilities.",
        "regime_parameters": {
            "combination_track_weights": dict(COMBINATION_TRACK_WEIGHTS),
            "track_pool_size": TRACK_POOL_SIZE[spec.game],
            "back_track_pool_size": BACK_TRACK_POOL_SIZE[spec.game],
            "track_combo_quality_weights": dict(TRACK_COMBO_QUALITY_WEIGHTS),
            "track_score_weights": dict(TRACK_SCORE_WEIGHTS),
            "cross_track_penalties": dict(CROSS_TRACK_PENALTIES),
            "track_quotas": quotas,
            "post_v26_version": True,
            "outcome_tuned_v26": False,
        },
        "front_regime_table": front_rows,
        "back_regime_table": back_rows,
        "core_pool": _core_pool(front_rows),
        "core_reference": {
            "origin_track": core_reference["origin_track"],
            "front": list(core_reference["front"]),
            "back": list(core_reference["back"]),
            "rank_score": core_reference["rank_score"],
            "front_track_rank": core_reference["front_track_rank"],
            "front_collision": core_reference["front_collision"],
        },
        "combination_collision_audit": audit,
        "scarcity_analysis": {
            "front": _scarcity_analysis(front_pools["scarcity"], front_records["scarcity"]),
            "back": _scarcity_analysis(back_pools["scarcity"], back_records["scarcity"]),
        },
        "track_diagnostics": {
            "quotas": quotas,
            "selected_counts": dict(Counter(item["origin_track"] for item in items)),
            "candidate_counts_front": {track: len(front_records[track]) for track in front_records},
            "candidate_counts_back": {track: len(back_records[track]) for track in back_records},
            "front_diversity": diversity_summary(item["front"] for item in items),
        },
    }
    return attach_budget_analysis(plan, budget)
