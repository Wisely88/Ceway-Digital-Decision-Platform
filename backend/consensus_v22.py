from __future__ import annotations

from statistics import pstdev

from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single


CONSENSUS_V22_VERSION = "multi-window-rank-consensus-v2.2"
CONSENSUS_WINDOWS = (50, 100, 200)


def equal_rank_consensus(
    score_tables: list[list[dict]],
    *,
    windows: tuple[int, ...] = CONSENSUS_WINDOWS,
) -> list[dict]:
    """Combine score tables by equal-weight rank percentile.

    Rank percentiles deliberately ignore absolute score scale. Each source window
    contributes exactly the same mass, so a window cannot dominate merely because
    its raw scorer values have a wider numerical range.
    """
    if not score_tables:
        return []
    if len(score_tables) != len(windows):
        raise ValueError("score_tables and windows must have the same length")

    number_sets = [{int(row["number"]) for row in table} for table in score_tables]
    if any(numbers != number_sets[0] for numbers in number_sets[1:]):
        raise ValueError("all consensus score tables must contain the same numbers")

    numbers = sorted(number_sets[0])
    if not numbers:
        return []

    percentile_by_window: list[dict[int, float]] = []
    raw_score_by_window: list[dict[int, float]] = []
    rank_by_window: list[dict[int, int]] = []

    for table in score_tables:
        ordered = sorted(
            table,
            key=lambda row: (-float(row.get("total_score", 0.0)), int(row["number"])),
        )
        count = len(ordered)
        ranks: dict[int, int] = {}
        percentiles: dict[int, float] = {}
        raw_scores: dict[int, float] = {}
        for index, row in enumerate(ordered):
            number = int(row["number"])
            rank = index + 1
            percentile = 100.0 if count <= 1 else 100.0 * (count - 1 - index) / (count - 1)
            ranks[number] = rank
            percentiles[number] = percentile
            raw_scores[number] = float(row.get("total_score", 0.0))
        rank_by_window.append(ranks)
        percentile_by_window.append(percentiles)
        raw_score_by_window.append(raw_scores)

    rows = []
    for number in numbers:
        percentiles = [source[number] for source in percentile_by_window]
        ranks = [source[number] for source in rank_by_window]
        raw_scores = [source[number] for source in raw_score_by_window]
        consensus_score = sum(percentiles) / len(percentiles)
        rows.append(
            {
                "number": number,
                "total_score": round(consensus_score, 4),
                "score": round(consensus_score, 4),
                "consensus_method": "equal_rank_percentile",
                "consensus_windows": list(windows),
                "source_ranks": {str(window): rank for window, rank in zip(windows, ranks)},
                "source_scores": {str(window): score for window, score in zip(windows, raw_scores)},
                "rank_stddev": round(pstdev(ranks), 4),
                "explanation": (
                    "V2.2 多窗口等权排名共识：分别计算50/100/200期排名百分位，"
                    "再按1/3、1/3、1/3平均；不使用开奖结果调权。"
                ),
            }
        )

    rows.sort(key=lambda row: (-float(row["total_score"]), float(row["rank_stddev"]), int(row["number"])))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _tag_consensus_plan(plan: dict) -> dict:
    plan["generator_version"] = CONSENSUS_V22_VERSION
    plan["reason"] = (
        "V2.2 实验：50/100/200期评分先做等权排名共识，再使用冻结的V2.1曝光预算组合器。"
    )
    plan["consensus_diagnostics"] = {
        "method": "equal_rank_percentile",
        "windows": list(CONSENSUS_WINDOWS),
        "weights": [1 / 3, 1 / 3, 1 / 3],
        "outcome_tuned_weights": False,
        "combination_engine": "score-exposure-balanced-v2.1",
    }
    for item in plan.get("items", []):
        item.setdefault("explanation", []).append(
            "V2.2 评分输入来自50/100/200期等权排名共识；组合覆盖机制沿用冻结V2.1。"
        )
    return plan


def generate_dlt_consensus_exposure_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
) -> dict:
    return _tag_consensus_plan(
        generate_dlt_exposure_single(budget, score_table, back_scores, strategy)
    )


def generate_ssq_consensus_exposure_single(
    budget: int,
    score_table: list[dict],
    back_scores: list[dict],
    strategy: str = "balanced",
) -> dict:
    return _tag_consensus_plan(
        generate_ssq_exposure_single(budget, score_table, back_scores, strategy)
    )
