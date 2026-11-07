from __future__ import annotations

from statistics import mean, median, pstdev

from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single


CONSENSUS_V23_VERSION = "median-rank-consensus-v2.3"
CONSENSUS_WINDOWS = (50, 100, 200)


def median_rank_consensus(
    score_tables: list[list[dict]],
    *,
    windows: tuple[int, ...] = CONSENSUS_WINDOWS,
) -> list[dict]:
    """Combine three score tables with a parameter-free two-of-three rule.

    Each source score table is converted to rank percentiles. The consensus
    score is the median percentile, so one anomalous window cannot dominate.
    Ties use the mean percentile, then lower rank dispersion, then number.
    """
    if not score_tables:
        return []
    if len(score_tables) != len(windows):
        raise ValueError("score_tables and windows must have the same length")
    if len(score_tables) != 3:
        raise ValueError("V2.3 median consensus requires exactly three score tables")

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
        median_percentile = float(median(percentiles))
        mean_percentile = float(mean(percentiles))
        rows.append(
            {
                "number": number,
                "total_score": round(median_percentile, 4),
                "score": round(median_percentile, 4),
                "consensus_method": "median_rank_percentile",
                "consensus_windows": list(windows),
                "source_ranks": {str(window): rank for window, rank in zip(windows, ranks)},
                "source_percentiles": {
                    str(window): round(percentile, 4)
                    for window, percentile in zip(windows, percentiles)
                },
                "source_scores": {str(window): score for window, score in zip(windows, raw_scores)},
                "mean_percentile": round(mean_percentile, 4),
                "rank_stddev": round(pstdev(ranks), 4),
                "explanation": (
                    "V2.3 两窗共识：50/100/200期各自转排名百分位后取中位数；"
                    "同分再看平均百分位与排名稳定度，不使用开奖结果学习权重。"
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            -float(row["total_score"]),
            -float(row["mean_percentile"]),
            float(row["rank_stddev"]),
            int(row["number"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _tag_consensus_plan(plan: dict) -> dict:
    plan["generator_version"] = CONSENSUS_V23_VERSION
    plan["reason"] = (
        "V2.3 实验：50/100/200期评分先做中位排名共识，再使用冻结的V2.1曝光预算组合器。"
    )
    plan["consensus_diagnostics"] = {
        "method": "median_rank_percentile",
        "windows": list(CONSENSUS_WINDOWS),
        "learned_weights": False,
        "combination_engine": "score-exposure-balanced-v2.1",
    }
    for item in plan.get("items", []):
        item.setdefault("explanation", []).append(
            "V2.3 评分输入采用50/100/200期排名中位数；组合覆盖机制沿用冻结V2.1。"
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
