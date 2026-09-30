from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from statistics import mean
from typing import Sequence

from multiregime_v25 import GameSpec
from multiregime_v26 import CONSTRAINTS, _collision_metrics, _structure_quality
from multiregime_v29 import generate_multiregime_protected_fusion_plan
from research_v2 import jaccard_similarity, passes_constraints

MULTIREGIME_V30_VERSION = "protected-core-aggregation-v3.0"
AGGREGATION_POOL_SIZE = {"DLT": 15, "SSQ": 16}
MAX_AGGREGATION_REPLACEMENTS = 2


def _front_union(items: Sequence[dict]) -> set[int]:
    out: set[int] = set()
    for item in items:
        out.update(int(n) for n in item["front"])
    return out


def _support_table(items: Sequence[dict], core_front: Sequence[int]) -> dict[int, dict]:
    exposure: Counter[int] = Counter()
    tracks: dict[int, set[str]] = defaultdict(set)
    track_exposure: dict[int, Counter[str]] = defaultdict(Counter)
    core = {int(n) for n in core_front}
    for item in items:
        track = str(item["origin_track"])
        for raw in item["front"]:
            number = int(raw)
            exposure[number] += 1
            tracks[number].add(track)
            track_exposure[number][track] += 1
    max_exposure = max(exposure.values(), default=1)
    rows: dict[int, dict] = {}
    for number in sorted(exposure):
        exposure_norm = exposure[number] / max_exposure
        breadth = len(tracks[number]) / 4.0
        core_support = 1.0 if number in core else 0.0
        quality = 0.60 * exposure_norm + 0.25 * breadth + 0.15 * core_support
        rows[number] = {
            "number": number,
            "exposure_count": int(exposure[number]),
            "track_support": sorted(tracks[number]),
            "track_support_count": len(tracks[number]),
            "track_exposure": dict(track_exposure[number]),
            "core_support": bool(number in core),
            "aggregation_number_quality": round(quality, 6),
        }
    return rows


def _aggregation_pool(items: Sequence[dict], core_front: Sequence[int], spec: GameSpec) -> list[dict]:
    rows = _support_table(items, core_front)
    target = AGGREGATION_POOL_SIZE[spec.game]
    seeded: set[int] = {int(n) for n in core_front}

    # Preserve the strongest exposed number from every origin that survives V2.9.
    by_track: dict[str, Counter[int]] = defaultdict(Counter)
    for item in items:
        track = str(item["origin_track"])
        by_track[track].update(int(n) for n in item["front"])
    for track in sorted(by_track):
        ordered = sorted(by_track[track], key=lambda n: (-by_track[track][n], -rows[n]["aggregation_number_quality"], n))
        seeded.update(ordered[:2])

    key = lambda row: (
        -float(row["aggregation_number_quality"]),
        -int(row["track_support_count"]),
        -int(row["exposure_count"]),
        int(row["number"]),
    )
    seed_rows = sorted((rows[n] for n in seeded if n in rows), key=key)
    rest = sorted((row for n, row in rows.items() if n not in seeded), key=key)
    selected = (seed_rows + rest)[:target]
    selected.sort(key=key)
    for rank, row in enumerate(selected, 1):
        row["aggregation_pool_rank"] = rank
    return selected


def _combo_quality(candidate: tuple[int, ...], row_by_number: dict[int, dict]) -> dict:
    member_rows = [row_by_number[n] for n in candidate]
    qualities = [float(row["aggregation_number_quality"]) for row in member_rows]
    member_quality = 0.65 * mean(qualities) + 0.35 * min(qualities)
    provenance = set()
    consensus = []
    for row in member_rows:
        provenance.update(str(track) for track in row["track_support"])
        consensus.append(int(row["track_support_count"]) / 4.0)
    provenance_coverage = len(provenance) / 4.0
    consensus_strength = mean(consensus)
    quality = 0.60 * member_quality + 0.25 * provenance_coverage + 0.15 * consensus_strength
    return {
        "member_quality": round(member_quality, 6),
        "minimum_member_quality": round(min(qualities), 6),
        "provenance_tracks": sorted(provenance),
        "provenance_coverage": round(provenance_coverage, 6),
        "consensus_strength": round(consensus_strength, 6),
        "quality": round(quality, 6),
    }


def _aggregation_records(items: Sequence[dict], history: Sequence[dict], spec: GameSpec, core_front: Sequence[int]) -> tuple[list[dict], list[dict]]:
    pool = _aggregation_pool(items, core_front, spec)
    numbers = tuple(int(row["number"]) for row in pool)
    row_by_number = {int(row["number"]): row for row in pool}
    history_fronts = [tuple(int(n) for n in row["front"]) for row in history]
    constraints = CONSTRAINTS[spec.game]
    records: list[dict] = []
    for candidate in combinations(numbers, spec.main_pick):
        candidate = tuple(sorted(candidate))
        if not passes_constraints(candidate, constraints):
            continue
        quality = _combo_quality(candidate, row_by_number)
        collision = _collision_metrics(candidate, history_fronts, pool_size=spec.main_pool, pick_size=spec.main_pick)
        structure = _structure_quality(candidate, constraints)
        rank_score = 0.50 * float(quality["quality"]) + 0.30 * float(collision["calibration_score"]) + 0.20 * float(structure)
        records.append({
            "origin_track": "aggregation",
            "front": list(candidate),
            "aggregation_quality": quality,
            "front_collision": collision,
            "front_structure_quality": round(float(structure), 6),
            "rank_score": round(rank_score, 6),
        })
    records.sort(key=lambda row: (
        -float(row["rank_score"]),
        -float(row["aggregation_quality"]["provenance_coverage"]),
        -float(row["aggregation_quality"]["minimum_member_quality"]),
        float(row["front_collision"]["mean_abs_z"]),
        tuple(int(n) for n in row["front"]),
    ))
    for rank, row in enumerate(records, 1):
        row["front_track_rank"] = rank
    return pool, records


def _protected_indices(items: list[dict]) -> set[int]:
    protected: set[int] = set()
    by_track: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for idx, item in enumerate(items):
        by_track[str(item["origin_track"])].append((idx, item))
    for track, rows in by_track.items():
        idx, _ = max(rows, key=lambda pair: (float(pair[1]["rank_score"]), -int(pair[1].get("front_track_rank", 999999))))
        protected.add(idx)
    return protected


def _replacement_gain(current: list[dict], remove_idx: int, candidate: dict) -> tuple[float, dict]:
    remaining = [item for idx, item in enumerate(current) if idx != remove_idx]
    remaining_union = _front_union(remaining)
    old = current[remove_idx]
    old_front = {int(n) for n in old["front"]}
    new_front = {int(n) for n in candidate["front"]}
    pick_size = max(1, len(new_front))
    added_unique = len(new_front - remaining_union) / pick_size
    lost_unique = len(old_front - remaining_union) / pick_size
    score_delta = float(candidate["rank_score"]) - float(old["rank_score"])
    max_jaccard = max((jaccard_similarity(new_front, item["front"]) for item in remaining), default=0.0)
    provenance = float(candidate["aggregation_quality"]["provenance_coverage"])
    gain = 0.45 * score_delta + 0.25 * (added_unique - lost_unique) + 0.20 * provenance + 0.10 * (1.0 - max_jaccard)
    return gain, {
        "score_delta": round(score_delta, 6),
        "added_unique_ratio": round(added_unique, 6),
        "lost_unique_ratio": round(lost_unique, 6),
        "max_jaccard": round(max_jaccard, 6),
        "provenance_coverage": round(provenance, 6),
        "replacement_gain": round(gain, 6),
    }


def generate_multiregime_aggregation_plan(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    budget: int = 20,
    strategy: str = "balanced",
    history_cutoff_issue: str | None = None,
) -> dict:
    baseline = generate_multiregime_protected_fusion_plan(
        history, spec, budget=budget, strategy=strategy, history_cutoff_issue=history_cutoff_issue
    )
    current = [dict(item) for item in baseline["items"]]
    training = [row for row in history if history_cutoff_issue is None or int(str(row["issue"])) <= int(str(history_cutoff_issue))]
    pool, records = _aggregation_records(current, training, spec, baseline["core_reference"]["front"])
    protected = _protected_indices(current)
    decisions = []
    used_fronts = {tuple(sorted(int(n) for n in item["front"])) for item in current}

    for candidate in records:
        if sum(1 for row in decisions if row.get("accepted")) >= MAX_AGGREGATION_REPLACEMENTS:
            break
        candidate_front = tuple(sorted(int(n) for n in candidate["front"]))
        if candidate_front in used_fronts:
            continue
        best = None
        for idx, old in enumerate(current):
            if idx in protected or str(old["origin_track"]) == "aggregation":
                continue
            gain, detail = _replacement_gain(current, idx, candidate)
            key = (gain, float(candidate["rank_score"]), -float(old["rank_score"]), -idx)
            if best is None or key > best[0]:
                best = (key, idx, old, detail)
        if best is None:
            continue
        gain, idx, old, detail = best[0][0], best[1], best[2], best[3]
        accepted = (
            gain > 0
            and detail["lost_unique_ratio"] <= detail["added_unique_ratio"]
            and detail["provenance_coverage"] >= 0.75
            and detail["max_jaccard"] <= 0.60
        )
        decision = {
            "aggregation_front": list(candidate["front"]),
            "aggregation_rank": int(candidate["front_track_rank"]),
            "candidate_remove_track": str(old["origin_track"]),
            "candidate_remove_front": list(old["front"]),
            "accepted": bool(accepted),
            **detail,
        }
        decisions.append(decision)
        if not accepted:
            continue
        replacement = dict(candidate)
        replacement["back"] = list(old["back"])
        replacement["back_display"] = old.get("back_display")
        replacement["front_display"] = old.get("front_display")
        replacement["score"] = round(float(candidate["rank_score"]) * 100.0, 4)
        replacement["v30_replaced_track"] = str(old["origin_track"])
        replacement["v30_replaced_front"] = list(old["front"])
        replacement["v30_replacement_gain"] = detail["replacement_gain"]
        replacement["back_track_rank"] = old.get("back_track_rank")
        current[idx] = replacement
        used_fronts.add(candidate_front)
        protected = _protected_indices(current)

    counts = dict(Counter(str(item["origin_track"]) for item in current))
    core = max(current, key=lambda item: (float(item["rank_score"]), -int(item.get("front_track_rank", 999999))))
    return {
        **baseline,
        "generator_version": MULTIREGIME_V30_VERSION,
        "algorithm_version": f"CEWAY-FWD-{spec.game}-{MULTIREGIME_V30_VERSION}",
        "items": current,
        "core_reference": {
            "origin_track": str(core["origin_track"]),
            "front": list(core["front"]),
            "back": list(core["back"]),
            "rank_score": float(core["rank_score"]),
            "front_track_rank": int(core.get("front_track_rank", 0)),
        },
        "production_enabled": False,
        "reason": "V3.0 research: preserve V2.9 core/fusion logic, then run a second-stage complete-combination aggregation ranking only over numbers already captured by the frozen V2.9 portfolio; at most two non-core seats may be replaced when the deterministic aggregation gate passes.",
        "v30_parameters": {
            "baseline": "V2.9 protected-core incremental-fusion portfolio",
            "aggregation_pool_size": AGGREGATION_POOL_SIZE[spec.game],
            "number_quality": "0.60*exposure_norm + 0.25*track_breadth + 0.15*core_support",
            "combo_quality": "0.60*(0.65*mean_member+0.35*min_member) + 0.25*provenance_coverage + 0.15*consensus_strength",
            "rank_score": "0.50*aggregation_quality + 0.30*collision_calibration + 0.20*structure_quality",
            "max_replacements": MAX_AGGREGATION_REPLACEMENTS,
            "replacement_objective": "0.45*score_delta + 0.25*(added_unique-lost_unique) + 0.20*provenance_coverage + 0.10*(1-max_jaccard)",
            "acceptance": "gain>0 AND lost_unique<=added_unique AND provenance>=0.75 AND max_jaccard<=0.60",
            "new_number_injection": False,
            "outcome_probability_claim": False,
        },
        "v30_replacement_decisions": decisions,
        "aggregation_analysis": {
            "pool": pool,
            "pool_size": len(pool),
            "combination_count_after_constraints": len(records),
            "full_combination_ranking": records,
        },
        "track_diagnostics": {**baseline.get("track_diagnostics", {}), "selected_counts_v30": counts},
    }
