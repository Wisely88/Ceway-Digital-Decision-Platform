from __future__ import annotations

from collections import Counter
from itertools import combinations
from statistics import mean
from typing import Iterable, Sequence

from generator import TICKET_PRICE, attach_budget_analysis, format_numbers, ssq_format_numbers
from multiregime_v25 import DLT, SSQ, ROLE_WEIGHTS, GameSpec, score_regimes
from multiregime_v26 import CONSTRAINTS, _collision_metrics, _core_pool, _cutoff, _structure_quality
from multiregime_v27 import (
    BACK_TRACK_POOL_SIZE,
    CROSS_TRACK_PENALTIES,
    TRACK_POOL_SIZE,
    _ordered_track_pool,
    _scarcity_analysis,
    _select_back_for_track,
    _select_complete_track_portfolio,
    _track_candidate_records,
    _track_quotas,
)
from research_v2 import combination_collision_audit, diversity_summary, intersection_count, jaccard_similarity, joint_collision_profile, passes_constraints


MULTIREGIME_V28_VERSION = "multi-regime-cross-fusion-v2.8"

# V2.8 does not retune V2.7 from observed outcomes. It reserves a fixed 20%
# forward-shadow budget for a deterministic cross-regime fusion track while
# preserving the existing Evidence / Scarcity / Neutral scorers and collision
# machinery unchanged.
FUSION_SHARE = 0.20
FUSION_POOL_SIZE = {"DLT": 14, "SSQ": 14}
FUSION_BACK_POOL_SIZE = {"DLT": 10, "SSQ": 12}
FUSION_SEED_QUOTAS = {"evidence": 4, "scarcity": 3, "neutral": 3}
FUSION_MEMBER_WEIGHTS = dict(ROLE_WEIGHTS)
FUSION_COMBO_QUALITY_WEIGHTS = {
    "member_quality": 0.60,
    "provenance_coverage": 0.25,
    "consensus_strength": 0.15,
}
FUSION_MEMBER_QUALITY_WEIGHTS = {"average": 0.70, "minimum": 0.30}
FUSION_RANK_WEIGHTS = {
    "fusion_quality": 0.55,
    "collision_calibration": 0.25,
    "structure_quality": 0.20,
}


def _fusion_score(row: dict) -> float:
    return sum(float(FUSION_MEMBER_WEIGHTS[track]) * float(row[f"{track}_score"]) for track in ("evidence", "scarcity", "neutral"))


def _track_top_sets(rows: list[dict], pool_size: int) -> dict[str, set[int]]:
    return {
        track: {int(row["number"]) for row in _ordered_track_pool(rows, track, pool_size)}
        for track in ("evidence", "scarcity", "neutral")
    }


def _fusion_number_key(row: dict) -> tuple:
    return (
        -float(row["fusion_score"]),
        -int(row["fusion_support_count"]),
        -max(float(row["evidence_score"]), float(row["scarcity_score"]), float(row["neutral_score"])),
        int(row["number"]),
    )


def _fusion_pool(rows: list[dict], spec: GameSpec, *, area: str) -> list[dict]:
    legacy_pool_size = TRACK_POOL_SIZE[spec.game] if area == "front" else BACK_TRACK_POOL_SIZE[spec.game]
    target_pool_size = FUSION_POOL_SIZE[spec.game] if area == "front" else FUSION_BACK_POOL_SIZE[spec.game]
    top_sets = _track_top_sets(rows, legacy_pool_size)

    enriched: dict[int, dict] = {}
    for row in rows:
        number = int(row["number"])
        copied = dict(row)
        support_tracks = [track for track in ("evidence", "scarcity", "neutral") if number in top_sets[track]]
        copied["fusion_score"] = round(_fusion_score(row), 6)
        copied["fusion_support_tracks"] = support_tracks
        copied["fusion_support_count"] = len(support_tracks)
        enriched[number] = copied

    # Seed the pool with each legacy track's leading numbers before filling by
    # fused score. This is the pre-registered mechanism that prevents useful
    # track-specific information from disappearing before combination ranking.
    seed_numbers: set[int] = set()
    for track in ("evidence", "scarcity", "neutral"):
        ordered = _ordered_track_pool(rows, track, legacy_pool_size)
        seed_numbers.update(int(row["number"]) for row in ordered[: FUSION_SEED_QUOTAS[track]])

    seeded = sorted((enriched[number] for number in seed_numbers), key=_fusion_number_key)
    remaining = sorted((row for number, row in enriched.items() if number not in seed_numbers), key=_fusion_number_key)
    selected = (seeded + remaining)[:target_pool_size]
    selected.sort(key=_fusion_number_key)
    for rank, row in enumerate(selected, 1):
        row["fusion_pool_rank"] = rank
    return selected


def _fusion_combo_quality(candidate: tuple[int, ...], row_by_number: dict[int, dict]) -> dict:
    rows = [row_by_number[number] for number in candidate]
    scores = [float(row["fusion_score"]) for row in rows]
    average_score = mean(scores)
    minimum_score = min(scores)
    member_quality = (
        FUSION_MEMBER_QUALITY_WEIGHTS["average"] * average_score
        + FUSION_MEMBER_QUALITY_WEIGHTS["minimum"] * minimum_score
    )
    represented = set()
    support_counts = []
    for row in rows:
        represented.update(str(track) for track in row["fusion_support_tracks"])
        support_counts.append(int(row["fusion_support_count"]))
    provenance_coverage = len(represented) / 3.0
    consensus_strength = mean(count / 3.0 for count in support_counts)
    quality = (
        FUSION_COMBO_QUALITY_WEIGHTS["member_quality"] * member_quality
        + FUSION_COMBO_QUALITY_WEIGHTS["provenance_coverage"] * provenance_coverage
        + FUSION_COMBO_QUALITY_WEIGHTS["consensus_strength"] * consensus_strength
    )
    return {
        "average": round(average_score, 6),
        "minimum": round(minimum_score, 6),
        "member_quality": round(member_quality, 6),
        "provenance_tracks": sorted(represented),
        "provenance_coverage": round(provenance_coverage, 6),
        "consensus_strength": round(consensus_strength, 6),
        "quality": round(quality, 6),
    }


def _fusion_candidate_records(
    rows: list[dict],
    history: Sequence[dict],
    spec: GameSpec,
    *,
    area: str,
) -> tuple[list[dict], list[dict]]:
    pick_size = spec.main_pick if area == "front" else spec.bonus_pick
    pool_size = spec.main_pool if area == "front" else spec.bonus_pool
    pool_rows = _fusion_pool(rows, spec, area=area)
    pool_numbers = tuple(int(row["number"]) for row in pool_rows)
    row_by_number = {int(row["number"]): row for row in pool_rows}
    history_numbers = [tuple(int(number) for number in row.get(area, [])) for row in history]
    constraints = CONSTRAINTS[spec.game] if area == "front" else None

    records: list[dict] = []
    for candidate in combinations(pool_numbers, pick_size):
        candidate = tuple(sorted(candidate))
        if area == "front" and constraints is not None and not passes_constraints(candidate, constraints):
            continue
        fusion_quality = _fusion_combo_quality(candidate, row_by_number)
        collision = _collision_metrics(candidate, history_numbers, pool_size=pool_size, pick_size=pick_size)
        structure_quality = _structure_quality(candidate, constraints) if area == "front" and constraints is not None else 1.0
        rank_score = (
            FUSION_RANK_WEIGHTS["fusion_quality"] * float(fusion_quality["quality"])
            + FUSION_RANK_WEIGHTS["collision_calibration"] * float(collision["calibration_score"])
            + FUSION_RANK_WEIGHTS["structure_quality"] * float(structure_quality)
        )
        records.append(
            {
                "track": "fusion",
                "numbers": list(candidate),
                "fusion_quality": fusion_quality,
                "structure_quality": round(float(structure_quality), 6),
                "collision": collision,
                "rank_score": round(rank_score, 6),
            }
        )

    records.sort(
        key=lambda item: (
            -float(item["rank_score"]),
            -float(item["fusion_quality"]["provenance_coverage"]),
            -float(item["fusion_quality"]["minimum"]),
            float(item["collision"]["mean_abs_z"]),
            tuple(item["numbers"]),
        )
    )
    for rank, record in enumerate(records, 1):
        record["track_rank"] = rank
    return pool_rows, records


def _fusion_count(ticket_count: int) -> int:
    if ticket_count <= 1:
        return ticket_count
    return max(1, int(round(ticket_count * FUSION_SHARE)))


def _select_fusion_portfolio(records: list[dict], count: int, existing: Sequence[dict]) -> list[dict]:
    selected: list[dict] = []
    usage: Counter[int] = Counter()
    pair_usage: Counter[tuple[int, int]] = Counter()
    for item in existing:
        numbers = tuple(int(number) for number in item["numbers"])
        usage.update(numbers)
        pair_usage.update(combinations(numbers, 2))

    used = {tuple(int(number) for number in item["numbers"]) for item in existing}
    while len(selected) < count:
        best = None
        best_key = None
        all_existing = [*existing, *selected]
        for candidate in records:
            numbers = tuple(int(number) for number in candidate["numbers"])
            if numbers in used:
                continue
            max_jaccard = max((jaccard_similarity(numbers, item["numbers"]) for item in all_existing), default=0.0)
            average_usage = sum(usage[number] for number in numbers) / max(1, len(numbers) * max(1, len(all_existing)))
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
                float(candidate["fusion_quality"]["provenance_coverage"]),
                -int(candidate["track_rank"]),
                tuple(-number for number in numbers),
            )
            if best_key is None or key > best_key:
                best_key = key
                best = candidate
        if best is None:
            raise RuntimeError("V2.8 could not fill fusion quota")
        copied = dict(best)
        copied["portfolio_objective"] = round(float(best_key[0]), 6)
        selected.append(copied)
        numbers = tuple(int(number) for number in copied["numbers"])
        used.add(numbers)
        usage.update(numbers)
        pair_usage.update(combinations(numbers, 2))
    return selected


def _fusion_analysis(pool_rows: list[dict], records: list[dict]) -> dict:
    return {
        "number_ordering": {
            "seed_quotas": dict(FUSION_SEED_QUOTAS),
            "fill_score": "0.50 * evidence_score + 0.30 * scarcity_score + 0.20 * neutral_score",
            "tie_breakers": ["support_count desc", "max component score desc", "number asc"],
            "manual_selection": False,
        },
        "pool": pool_rows,
        "pool_size": len(pool_rows),
        "combination_count_after_constraints": len(records),
        "combination_ordering": {
            "member_quality": "0.70 * average fusion_score + 0.30 * minimum fusion_score",
            "fusion_quality": "0.60 * member_quality + 0.25 * provenance_coverage + 0.15 * consensus_strength",
            "rank_score": "0.55 * fusion_quality + 0.25 * collision_calibration + 0.20 * structure_quality",
            "tie_breakers": ["provenance coverage desc", "minimum fusion score desc", "mean_abs_collision_z asc", "numbers asc"],
        },
        "full_combination_ranking": records,
    }


def _review_ranked_area(section: dict, actual: set[int], *, rank_field: str) -> dict:
    pool = section["pool"]
    ranking = section["full_combination_ranking"]
    pool_numbers = [int(row["number"]) for row in pool]
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
        first_rank_by_hits.setdefault(str(hits), rank)
    buckets = {}
    for limit in (10, 50, 100, len(evaluated)):
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
        "pool_hits": sorted(set(pool_numbers) & actual),
        "pool_hit_count": len(set(pool_numbers) & actual),
        "number_ranking_review": [
            {
                "pool_rank": int(row[rank_field]),
                "number": int(row["number"]),
                "hit": int(row["number"]) in actual,
                "fusion_score": float(row.get("fusion_score", 0.0)),
                "support_tracks": list(row.get("fusion_support_tracks", [])),
            }
            for row in pool
        ],
        "exact_actual_combination_rank": exact_rank,
        "best_matching_combination": list(best_row.get("numbers", [])),
        "best_matching_rank": best_rank or None,
        "best_matching_hits": best_hits,
        "first_rank_by_hit_count": first_rank_by_hits,
        "rank_buckets": buckets,
    }


def review_fusion_ranking(plan: dict, actual_front: Iterable[int], actual_back: Iterable[int]) -> dict:
    """Replay the frozen V2.8 fusion ranking and final portfolio without regeneration."""
    if plan.get("generator_version") != MULTIREGIME_V28_VERSION:
        raise ValueError("Fusion review only accepts a frozen V2.8 plan")
    actual_front_set = {int(number) for number in actual_front}
    actual_back_set = {int(number) for number in actual_back}
    front_review = _review_ranked_area(plan["fusion_analysis"]["front"], actual_front_set, rank_field="fusion_pool_rank")
    back_review = _review_ranked_area(plan["fusion_analysis"]["back"], actual_back_set, rank_field="fusion_pool_rank")

    per_track: dict[str, dict] = {}
    all_front_union: set[int] = set()
    for item in plan.get("items", []):
        track = str(item["origin_track"])
        front = {int(number) for number in item["front"]}
        back = {int(number) for number in item["back"]}
        all_front_union.update(front)
        row = per_track.setdefault(track, {"tickets": 0, "front_hit_total": 0, "best_front_hits": 0, "back_hit_total": 0, "front_union": set()})
        front_hits = len(front & actual_front_set)
        back_hits = len(back & actual_back_set)
        row["tickets"] += 1
        row["front_hit_total"] += front_hits
        row["back_hit_total"] += back_hits
        row["best_front_hits"] = max(row["best_front_hits"], front_hits)
        row["front_union"].update(front)
    for row in per_track.values():
        union = set(row.pop("front_union"))
        row["front_union_hits"] = sorted(union & actual_front_set)
        row["front_union_hit_count"] = len(union & actual_front_set)

    return {
        "generator_version": plan.get("generator_version"),
        "history_cutoff_issue": plan.get("history_cutoff_issue"),
        "front": front_review,
        "back": back_review,
        "portfolio": {
            "per_track": per_track,
            "all_front_union_hits": sorted(all_front_union & actual_front_set),
            "all_front_union_hit_count": len(all_front_union & actual_front_set),
        },
    }


def generate_multiregime_cross_fusion_plan(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    budget: int = 20,
    strategy: str = "balanced",
    history_cutoff_issue: str | None = None,
) -> dict:
    training = _cutoff(history, history_cutoff_issue)
    if len(training) < 30:
        raise ValueError("V2.8 requires at least 30 historical draws")

    ticket_count = max(1, budget // TICKET_PRICE)
    fusion_count = _fusion_count(ticket_count)
    legacy_count = ticket_count - fusion_count
    front_rows = score_regimes(training, spec, area="front")
    back_rows = score_regimes(training, spec, area="back")

    front_pools: dict[str, list[dict]] = {}
    front_records: dict[str, list[dict]] = {}
    back_pools: dict[str, list[dict]] = {}
    back_records: dict[str, list[dict]] = {}
    for track in ("evidence", "scarcity", "neutral"):
        front_pools[track], front_records[track] = _track_candidate_records(front_rows, training, spec, area="front", track=track)
        back_pools[track], back_records[track] = _track_candidate_records(back_rows, training, spec, area="back", track=track)
    fusion_front_pool, fusion_front_records = _fusion_candidate_records(front_rows, training, spec, area="front")
    fusion_back_pool, fusion_back_records = _fusion_candidate_records(back_rows, training, spec, area="back")
    front_records["fusion"] = fusion_front_records
    back_records["fusion"] = fusion_back_records

    legacy_selected = _select_complete_track_portfolio({track: front_records[track] for track in ("evidence", "scarcity", "neutral")}, legacy_count) if legacy_count else []
    fusion_selected = _select_fusion_portfolio(fusion_front_records, fusion_count, legacy_selected)
    selected_fronts = [*legacy_selected, *fusion_selected]

    back_index: Counter[str] = Counter()
    items = []
    for front_record in selected_fronts:
        track = str(front_record["track"])
        back_record = _select_back_for_track(back_records, track, back_index)
        front = [int(number) for number in front_record["numbers"]]
        back = [int(number) for number in back_record["numbers"]]
        joint = {f"{main_hits}+{bonus_hits}": count for (main_hits, bonus_hits), count in joint_collision_profile(front, back, training).items()}
        combined_score = 0.82 * float(front_record["rank_score"]) + 0.18 * float(back_record["rank_score"])
        quality = front_record.get("fusion_quality", front_record.get("track_quality", {}))
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
                "front_quality": quality,
                "front_structure_quality": front_record["structure_quality"],
                "front_collision": front_record["collision"],
                "back_collision": back_record["collision"],
                "joint_collision_profile": joint,
                "explanation": [
                    "V2.8 完整组合轨：80% 保留 V2.7 三轨前瞻结构，20% 固定给预注册的跨轨 Fusion 完整组合；所有组合继续执行碰撞与结构评分。"
                ],
            }
        )

    core_reference = max(items, key=lambda item: (float(item["rank_score"]), -int(item["front_track_rank"]), tuple(-number for number in item["front"])))
    legacy_quotas = _track_quotas(legacy_count) if legacy_count else {"evidence": 0, "scarcity": 0, "neutral": 0}
    quotas = {**legacy_quotas, "fusion": fusion_count}
    audit = combination_collision_audit(items, training, spec, include_per_ticket=False)
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": MULTIREGIME_V28_VERSION,
        "algorithm_version": f"CEWAY-FWD-{spec.game}-{MULTIREGIME_V28_VERSION}",
        "cost": len(items) * TICKET_PRICE,
        "tickets": len(items),
        "items": items,
        "score": round(sum(float(item["score"]) for item in items), 2),
        "reason": "V2.8 research candidate: preserves V2.7 regime tracks while adding a pre-registered cross-regime full-combination fusion shadow.",
        "history_cutoff_issue": training[-1].get("issue"),
        "production_enabled": False,
        "research_guard": "Fusion, scarcity and collision rankings are descriptive research features, not future-win probabilities.",
        "regime_parameters": {
            "legacy_combination_track_weights": dict(ROLE_WEIGHTS),
            "fusion_share": FUSION_SHARE,
            "fusion_member_weights": dict(FUSION_MEMBER_WEIGHTS),
            "fusion_seed_quotas": dict(FUSION_SEED_QUOTAS),
            "fusion_pool_size": FUSION_POOL_SIZE[spec.game],
            "fusion_back_pool_size": FUSION_BACK_POOL_SIZE[spec.game],
            "fusion_combo_quality_weights": dict(FUSION_COMBO_QUALITY_WEIGHTS),
            "fusion_member_quality_weights": dict(FUSION_MEMBER_QUALITY_WEIGHTS),
            "fusion_rank_weights": dict(FUSION_RANK_WEIGHTS),
            "track_quotas": quotas,
            "parent_version": "multi-regime-scarcity-combo-v2.7",
            "outcome_tuned_v27": False,
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
        "fusion_analysis": {
            "front": _fusion_analysis(fusion_front_pool, fusion_front_records),
            "back": _fusion_analysis(fusion_back_pool, fusion_back_records),
        },
        "track_diagnostics": {
            "quotas": quotas,
            "selected_counts": dict(Counter(item["origin_track"] for item in items)),
            "candidate_counts_front": {**{track: len(front_records[track]) for track in ("evidence", "scarcity", "neutral")}, "fusion": len(fusion_front_records)},
            "candidate_counts_back": {**{track: len(back_records[track]) for track in ("evidence", "scarcity", "neutral")}, "fusion": len(fusion_back_records)},
            "front_diversity": diversity_summary(item["front"] for item in items),
        },
    }
    return attach_budget_analysis(plan, budget)
