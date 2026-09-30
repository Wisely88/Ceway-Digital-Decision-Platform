from __future__ import annotations

from collections import Counter
from itertools import combinations
from statistics import mean
from typing import Iterable, Sequence

from generator import TICKET_PRICE, attach_budget_analysis, format_numbers, ssq_format_numbers
from multiregime_v25 import DLT, SSQ, ROLE_WEIGHTS, GameSpec, score_regimes
from research_v2 import (
    TicketConstraints,
    collision_profile,
    collision_z_scores,
    combination_collision_audit,
    diversity_summary,
    expected_collision_counts,
    jaccard_similarity,
    joint_collision_profile,
    passes_constraints,
)


MULTIREGIME_V26_VERSION = "multi-regime-collision-v2.6"

# V2.6 is a new post-review experiment. V2.5 remains frozen and unchanged.
# These weights are architectural defaults, not tuned to a lottery outcome.
TICKET_SCORE_WEIGHTS = {
    "regime_quality": 0.60,
    "collision_calibration": 0.25,
    "structure_quality": 0.15,
}
PORTFOLIO_PENALTIES = {
    "max_jaccard": 0.12,
    "number_exposure": 0.08,
    "pair_reuse": 0.08,
}
CORE_REGIME_QUOTA = 4
FRONT_CANDIDATE_BAND = {"DLT": 18, "SSQ": 18}
BACK_CANDIDATE_BAND = {"DLT": 10, "SSQ": 12}
CORE_POOL_SIZE = 12


CONSTRAINTS = {
    "DLT": TicketConstraints(
        zones=((1, 12), (13, 24), (25, 35)),
        allowed_zone_counts=((2, 2, 1), (1, 2, 2), (2, 1, 2)),
        allowed_odd_counts=(2, 3),
        sum_min=65,
        sum_max=105,
        max_consecutive_groups=1,
    ),
    "SSQ": TicketConstraints(
        zones=((1, 11), (12, 22), (23, 33)),
        allowed_zone_counts=((2, 2, 2), (2, 1, 3), (3, 1, 2)),
        allowed_odd_counts=(2, 3, 4),
        sum_min=85,
        sum_max=120,
        max_consecutive_groups=1,
    ),
}


def _issue_key(issue: object) -> tuple[int, str]:
    text = str(issue or "")
    if text.isdigit():
        return (0, f"{int(text):020d}")
    return (1, text)


def _cutoff(history: Sequence[dict], issue: str | None) -> list[dict]:
    rows = sorted(history, key=lambda row: _issue_key(row.get("issue")))
    if issue is None:
        return list(rows)
    key = _issue_key(issue)
    return [row for row in rows if _issue_key(row.get("issue")) <= key]


def _blend(row: dict) -> float:
    return (
        ROLE_WEIGHTS["evidence"] * float(row["evidence_score"])
        + ROLE_WEIGHTS["scarcity"] * float(row["scarcity_score"])
        + ROLE_WEIGHTS["neutral"] * float(row["neutral_score"])
    )


def _ranked_numbers(rows: list[dict], band_size: int) -> list[int]:
    by_number = {int(row["number"]): row for row in rows}
    required: set[int] = set()
    for regime in ("evidence", "scarcity", "neutral"):
        ordered = sorted(rows, key=lambda row: (row[f"{regime}_rank"], row["number"]))
        required.update(int(row["number"]) for row in ordered[:CORE_REGIME_QUOTA])

    ranked = sorted(rows, key=lambda row: (-_blend(row), row["number"]))
    output = sorted(required, key=lambda number: (-_blend(by_number[number]), number))
    for row in ranked:
        number = int(row["number"])
        if number not in output:
            output.append(number)
        if len(output) >= max(band_size, len(required)):
            break
    return output


def _core_pool(rows: list[dict], count: int = CORE_POOL_SIZE) -> list[int]:
    ranked = _ranked_numbers(rows, max(count, CORE_REGIME_QUOTA * 3))
    return ranked[:count]


def _structure_quality(ticket: Iterable[int], constraints: TicketConstraints) -> float:
    numbers = tuple(sorted(ticket))
    if not numbers:
        return 0.0
    pick_size = len(numbers)

    odd = sum(number % 2 for number in numbers)
    odd_score = max(0.0, 1.0 - abs(odd - pick_size / 2.0) / max(1.0, pick_size / 2.0))

    if constraints.zones:
        counts = [sum(low <= number <= high for number in numbers) for low, high in constraints.zones]
        target = pick_size / len(constraints.zones)
        zone_score = max(0.0, 1.0 - sum(abs(count - target) for count in counts) / (2.0 * pick_size))
    else:
        zone_score = 1.0

    if constraints.sum_min is not None and constraints.sum_max is not None:
        center = (constraints.sum_min + constraints.sum_max) / 2.0
        radius = max(1.0, (constraints.sum_max - constraints.sum_min) / 2.0)
        sum_score = max(0.0, 1.0 - abs(sum(numbers) - center) / radius)
    else:
        sum_score = 1.0

    return (odd_score + zone_score + sum_score) / 3.0


def _collision_metrics(
    candidate: tuple[int, ...],
    history_numbers: list[tuple[int, ...]],
    *,
    pool_size: int,
    pick_size: int,
) -> dict:
    profile = collision_profile(candidate, history_numbers, pick_size)
    z_scores = collision_z_scores(profile, pool_size, pick_size, len(history_numbers))
    mean_abs_z = mean(abs(float(value)) for value in z_scores.values()) if z_scores else 0.0
    calibration = 1.0 / (1.0 + mean_abs_z)
    tail_from = max(2, pick_size - 2)
    high_hit_recurrence = sum(int(profile.get(k, 0)) for k in range(tail_from, pick_size + 1))
    return {
        "profile": profile,
        "descriptive_z": {k: round(float(value), 6) for k, value in z_scores.items()},
        "calibration_score": round(calibration, 6),
        "mean_abs_z": round(mean_abs_z, 6),
        "high_hit_recurrence": high_hit_recurrence,
    }


def _candidate_records(
    rows: list[dict],
    history: Sequence[dict],
    spec: GameSpec,
    *,
    area: str,
) -> list[dict]:
    pick_size = spec.main_pick if area == "front" else spec.bonus_pick
    pool_size = spec.main_pool if area == "front" else spec.bonus_pool
    band_size = FRONT_CANDIDATE_BAND[spec.game] if area == "front" else BACK_CANDIDATE_BAND[spec.game]
    ranked_numbers = _ranked_numbers(rows, band_size)
    row_by_number = {int(row["number"]): row for row in rows}
    history_numbers = [tuple(int(number) for number in row.get(area, [])) for row in history]
    constraints = CONSTRAINTS[spec.game] if area == "front" else TicketConstraints()

    candidates: list[dict] = []
    for candidate in combinations(ranked_numbers, pick_size):
        candidate = tuple(sorted(candidate))
        if area == "front" and not passes_constraints(candidate, constraints):
            continue
        regime_quality = mean(_blend(row_by_number[number]) for number in candidate)
        collision = _collision_metrics(candidate, history_numbers, pool_size=pool_size, pick_size=pick_size)
        structure_quality = _structure_quality(candidate, constraints) if area == "front" else 1.0
        rank_score = (
            TICKET_SCORE_WEIGHTS["regime_quality"] * regime_quality
            + TICKET_SCORE_WEIGHTS["collision_calibration"] * collision["calibration_score"]
            + TICKET_SCORE_WEIGHTS["structure_quality"] * structure_quality
        )
        candidates.append(
            {
                "numbers": candidate,
                "regime_quality": round(regime_quality, 6),
                "structure_quality": round(structure_quality, 6),
                "collision": collision,
                "rank_score": round(rank_score, 6),
            }
        )

    return sorted(
        candidates,
        key=lambda item: (
            -item["rank_score"],
            item["collision"]["mean_abs_z"],
            tuple(item["numbers"]),
        ),
    )


def _choose_portfolio(candidates: list[dict], ticket_count: int) -> list[dict]:
    selected: list[dict] = []
    usage: Counter[int] = Counter()
    pair_usage: Counter[tuple[int, int]] = Counter()
    remaining = list(candidates)

    while remaining and len(selected) < ticket_count:
        best = None
        best_key = None
        for candidate in remaining:
            numbers = tuple(candidate["numbers"])
            if selected:
                max_jaccard = max(jaccard_similarity(numbers, item["numbers"]) for item in selected)
            else:
                max_jaccard = 0.0
            average_usage = sum(usage[number] for number in numbers) / max(1, len(numbers) * max(1, len(selected)))
            reused_pairs = sum(pair_usage[pair] for pair in combinations(numbers, 2)) / max(1, len(list(combinations(numbers, 2))))
            objective = (
                float(candidate["rank_score"])
                - PORTFOLIO_PENALTIES["max_jaccard"] * max_jaccard
                - PORTFOLIO_PENALTIES["number_exposure"] * average_usage
                - PORTFOLIO_PENALTIES["pair_reuse"] * reused_pairs
            )
            key = (
                objective,
                candidate["rank_score"],
                -max_jaccard,
                -candidate["collision"]["mean_abs_z"],
                tuple(-number for number in numbers),
            )
            if best_key is None or key > best_key:
                best_key = key
                best = candidate
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)
        numbers = tuple(best["numbers"])
        usage.update(numbers)
        pair_usage.update(combinations(numbers, 2))

    return selected


def _find_core_reference(items: list[dict]) -> dict:
    if not items:
        return {}
    return max(
        items,
        key=lambda item: (
            float(item["rank_score"]),
            float(item["front_rank_score"]),
            -float(item["front_collision"]["mean_abs_z"]),
            tuple(-number for number in item["front"]),
        ),
    )


def generate_multiregime_collision_plan(
    history: Sequence[dict],
    spec: GameSpec,
    *,
    budget: int = 20,
    strategy: str = "balanced",
    history_cutoff_issue: str | None = None,
) -> dict:
    training = _cutoff(history, history_cutoff_issue)
    if len(training) < 30:
        raise ValueError("V2.6 requires at least 30 historical draws")

    ticket_count = max(1, budget // TICKET_PRICE)
    front_rows = score_regimes(training, spec, area="front")
    back_rows = score_regimes(training, spec, area="back")
    front_candidates = _candidate_records(front_rows, training, spec, area="front")
    back_candidates = _candidate_records(back_rows, training, spec, area="back")
    selected_fronts = _choose_portfolio(front_candidates, ticket_count)
    selected_backs = _choose_portfolio(back_candidates, ticket_count)

    items: list[dict] = []
    for index, front_record in enumerate(selected_fronts):
        back_record = selected_backs[index % len(selected_backs)] if selected_backs else None
        front = list(front_record["numbers"])
        back = list(back_record["numbers"]) if back_record else []
        joint = {
            f"{main_hits}+{bonus_hits}": count
            for (main_hits, bonus_hits), count in joint_collision_profile(front, back, training).items()
        }
        rank_score = 0.82 * float(front_record["rank_score"]) + 0.18 * float(back_record["rank_score"] if back_record else 0.0)
        items.append(
            {
                "front": front,
                "back": back,
                "front_display": format_numbers(front) if spec.game == "DLT" else ssq_format_numbers(front),
                "back_display": format_numbers(back) if spec.game == "DLT" else ssq_format_numbers(back),
                "score": round(rank_score * 100.0, 4),
                "rank_score": round(rank_score, 6),
                "front_rank_score": front_record["rank_score"],
                "back_rank_score": back_record["rank_score"] if back_record else 0.0,
                "front_regime_quality": front_record["regime_quality"],
                "front_structure_quality": front_record["structure_quality"],
                "front_collision": front_record["collision"],
                "back_collision": back_record["collision"] if back_record else {},
                "joint_collision_profile": joint,
                "explanation": [
                    "V2.6：先对完整组合计算历史碰撞 N_k / Z，再与 V2.5 三轴质量和结构约束共同排序；碰撞仅作历史校准与覆盖描述。"
                ],
            }
        )

    core_reference = _find_core_reference(items)
    audit = combination_collision_audit(items, training, spec, include_per_ticket=False)
    plan = {
        "mode": "single",
        "strategy": strategy,
        "generator_version": MULTIREGIME_V26_VERSION,
        "algorithm_version": f"CEWAY-FWD-{spec.game}-{MULTIREGIME_V26_VERSION}",
        "cost": len(items) * TICKET_PRICE,
        "tickets": len(items),
        "items": items,
        "score": round(sum(float(item["score"]) for item in items), 2),
        "reason": "V2.6 research candidate: V2.5 multi-regime number states plus combination-level historical collision calibration and lighter portfolio dispersion.",
        "history_cutoff_issue": training[-1].get("issue"),
        "production_enabled": False,
        "research_guard": "Combination collision statistics are descriptive historical calibration features, not future-win probabilities.",
        "regime_parameters": {
            "role_weights": dict(ROLE_WEIGHTS),
            "ticket_score_weights": dict(TICKET_SCORE_WEIGHTS),
            "portfolio_penalties": dict(PORTFOLIO_PENALTIES),
            "front_candidate_band": FRONT_CANDIDATE_BAND[spec.game],
            "back_candidate_band": BACK_CANDIDATE_BAND[spec.game],
            "post_review_version": True,
            "outcome_tuned_v25": False,
        },
        "front_regime_table": front_rows,
        "back_regime_table": back_rows,
        "core_pool": _core_pool(front_rows),
        "core_reference": {
            "front": list(core_reference.get("front", [])),
            "back": list(core_reference.get("back", [])),
            "rank_score": core_reference.get("rank_score", 0.0),
            "front_collision": core_reference.get("front_collision", {}),
            "joint_collision_profile": core_reference.get("joint_collision_profile", {}),
        },
        "combination_collision_audit": audit,
        "coverage_diagnostics": {
            "front_candidates_after_constraints": len(front_candidates),
            "back_candidates": len(back_candidates),
            "front_diversity": diversity_summary(item["front"] for item in items),
            "core_pool_source": "V2.5 regime blend ranking with independent top-regime quota; not ticket usage count.",
            "core_reference_source": "highest V2.6 combined ticket rank_score; not first generated ticket.",
        },
    }
    return attach_budget_analysis(plan, budget)
