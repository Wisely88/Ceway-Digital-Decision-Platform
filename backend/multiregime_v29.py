from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Sequence

from multiregime_v25 import GameSpec
from multiregime_v27 import generate_multiregime_scarcity_combo_plan
from multiregime_v28 import generate_multiregime_cross_fusion_plan
from research_v2 import jaccard_similarity

MULTIREGIME_V29_VERSION = "protected-core-incremental-fusion-v2.9"
MAX_FUSION_REPLACEMENTS = 2


def _front_union(items: Sequence[dict]) -> set[int]:
    out: set[int] = set()
    for item in items:
        out.update(int(n) for n in item["front"])
    return out


def _protected_indices(items: list[dict]) -> set[int]:
    protected: set[int] = set()
    by_track: dict[str, list[tuple[int, dict]]] = {}
    for idx, item in enumerate(items):
        by_track.setdefault(str(item["origin_track"]), []).append((idx, item))
    for track in ("evidence", "scarcity", "neutral"):
        rows = by_track.get(track, [])
        if not rows:
            continue
        idx, _ = max(rows, key=lambda pair: (float(pair[1]["rank_score"]), -int(pair[1]["front_track_rank"])))
        protected.add(idx)
    return protected


def _replacement_gain(current: list[dict], remove_idx: int, fusion: dict) -> tuple[float, dict]:
    remaining = [item for idx, item in enumerate(current) if idx != remove_idx]
    union = _front_union(remaining)
    old = current[remove_idx]
    old_front = {int(n) for n in old["front"]}
    new_front = {int(n) for n in fusion["front"]}
    pick_size = max(1, len(new_front))

    added_unique = len(new_front - union) / pick_size
    lost_unique = len(old_front - union) / pick_size
    score_delta = float(fusion["rank_score"]) - float(old["rank_score"])
    max_jaccard = max((jaccard_similarity(new_front, item["front"]) for item in remaining), default=0.0)

    # Pre-registered portfolio objective: Fusion must compensate any loss of
    # legacy-only coverage. Score uplift alone is not enough to justify a swap.
    gain = 0.50 * score_delta + 0.35 * (added_unique - lost_unique) + 0.15 * (1.0 - max_jaccard)
    detail = {
        "score_delta": round(score_delta, 6),
        "added_unique_ratio": round(added_unique, 6),
        "lost_unique_ratio": round(lost_unique, 6),
        "max_jaccard": round(max_jaccard, 6),
        "replacement_gain": round(gain, 6),
    }
    return gain, detail


def generate_multiregime_protected_fusion_plan(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    budget: int = 20,
    strategy: str = "balanced",
    history_cutoff_issue: str | None = None,
) -> dict:
    legacy = generate_multiregime_scarcity_combo_plan(
        history, spec, budget=budget, strategy=strategy, history_cutoff_issue=history_cutoff_issue
    )
    fusion_shadow = generate_multiregime_cross_fusion_plan(
        history, spec, budget=budget, strategy=strategy, history_cutoff_issue=history_cutoff_issue
    )

    current = [dict(item) for item in legacy["items"]]
    protected = _protected_indices(current)
    fusion_candidates = [dict(item) for item in fusion_shadow["items"] if item["origin_track"] == "fusion"]
    decisions = []

    for fusion in fusion_candidates[:MAX_FUSION_REPLACEMENTS]:
        best = None
        for idx, old in enumerate(current):
            if idx in protected or old["origin_track"] == "fusion":
                continue
            gain, detail = _replacement_gain(current, idx, fusion)
            key = (gain, float(fusion["rank_score"]), -float(old["rank_score"]), -idx)
            if best is None or key > best[0]:
                best = (key, idx, old, detail)
        if best is None:
            continue
        gain = best[0][0]
        idx, old, detail = best[1], best[2], best[3]
        accepted = gain > 0 and detail["lost_unique_ratio"] <= detail["added_unique_ratio"]
        decisions.append({
            "fusion_front": list(fusion["front"]),
            "candidate_remove_track": old["origin_track"],
            "candidate_remove_front": list(old["front"]),
            "accepted": accepted,
            **detail,
        })
        if accepted:
            fusion = dict(fusion)
            fusion["v29_replaced_track"] = old["origin_track"]
            fusion["v29_replaced_front"] = list(old["front"])
            fusion["v29_replacement_gain"] = detail["replacement_gain"]
            current[idx] = fusion

    counts = dict(Counter(str(item["origin_track"]) for item in current))
    core = max(current, key=lambda item: (float(item["rank_score"]), -int(item["front_track_rank"])))
    return {
        **legacy,
        "generator_version": MULTIREGIME_V29_VERSION,
        "algorithm_version": f"CEWAY-FWD-{spec.game}-{MULTIREGIME_V29_VERSION}",
        "items": current,
        "core_reference": {
            "origin_track": core["origin_track"],
            "front": list(core["front"]),
            "back": list(core["back"]),
            "rank_score": core["rank_score"],
            "front_track_rank": core["front_track_rank"],
        },
        "production_enabled": False,
        "reason": "V2.9 research: protect the strongest complete ticket from each legacy track; Fusion may replace at most two non-core tickets only when its pre-registered incremental portfolio objective is positive and unique-number coverage is not reduced.",
        "v29_parameters": {
            "baseline": "V2.7 5/3/2 complete-ticket portfolio",
            "protected_core": "highest combined-score selected ticket from Evidence, Scarcity and Neutral",
            "max_fusion_replacements": MAX_FUSION_REPLACEMENTS,
            "replacement_objective": "0.50*score_delta + 0.35*(added_unique-lost_unique) + 0.15*(1-max_jaccard)",
            "acceptance": "gain > 0 AND lost_unique_ratio <= added_unique_ratio",
            "outcome_probability_claim": False,
        },
        "v29_replacement_decisions": decisions,
        "track_diagnostics": {**legacy.get("track_diagnostics", {}), "selected_counts_v29": counts},
        "fusion_shadow_analysis": fusion_shadow.get("fusion_analysis"),
    }
