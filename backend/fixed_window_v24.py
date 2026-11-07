from __future__ import annotations

from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single


FIXED_WINDOW_V24_VERSION = "fixed-window-100-exposure-v2.4"
FIXED_WINDOW_V24 = 100


def _tag(plan: dict) -> dict:
    plan["generator_version"] = FIXED_WINDOW_V24_VERSION
    plan["reason"] = (
        "V2.4 验证候选：固定100期评分窗口，组合器原样沿用冻结的 score-exposure-balanced-v2.1。"
    )
    plan["scoring_window_diagnostics"] = {
        "fixed_window": FIXED_WINDOW_V24,
        "window_selected_post_hoc": True,
        "promotion_evidence_must_be_fresh": True,
        "combination_engine": "score-exposure-balanced-v2.1",
    }
    for item in plan.get("items", []):
        item.setdefault("explanation", []).append(
            "V2.4 使用固定100期评分窗口；组合覆盖参数与V2.1完全一致。"
        )
    return plan


def generate_dlt_fixed100_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
) -> dict:
    return _tag(generate_dlt_exposure_single(budget, score_table, back_scores, strategy))


def generate_ssq_fixed100_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
) -> dict:
    return _tag(generate_ssq_exposure_single(budget, score_table, back_scores, strategy))
