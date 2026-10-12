from __future__ import annotations

from typing import Callable


SCORER_V23_VERSION = "feature-pruned-shrink-v2.3"
NEUTRAL_SCORE = 50.0


def _finalize(rows: list[dict], scorer_label: str) -> list[dict]:
    rows.sort(key=lambda row: (-float(row["total_score"]), int(row["number"])))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        row["score"] = row["total_score"]
        row["scorer_version"] = SCORER_V23_VERSION
        row["scorer_label"] = scorer_label
    return rows


def _transform(
    source_rows: list[dict],
    score_fn: Callable[[dict], float],
    *,
    scorer_label: str,
    explanation: str,
) -> list[dict]:
    rows = []
    for source in source_rows:
        row = dict(source)
        row["legacy_total_score"] = float(source.get("total_score", 0.0))
        row["total_score"] = round(float(score_fn(source)), 4)
        row["explanation"] = explanation
        rows.append(row)
    return _finalize(rows, scorer_label)


def score_dlt_front_v23(source_rows: list[dict]) -> list[dict]:
    """DLT front: retain only the consumed-data feature with positive evidence.

    Feature audit classified DLT.front.balance_score as PROMISING_DIRECTION,
    while heat and omission were weak-negative. No outcome-derived coefficient
    search is performed: the candidate is simply balance-only.
    """
    return _transform(
        source_rows,
        lambda row: float(row.get("balance_score", NEUTRAL_SCORE)),
        scorer_label="DLT.front.balance_only",
        explanation=(
            "V2.3研究评分：前区只保留已消费特征审计中方向较稳定的均衡项；"
            "热度与遗漏不参与本候选评分。"
        ),
    )


def score_dlt_back_v23(source_rows: list[dict]) -> list[dict]:
    """DLT back: equal-weight heat + balance, with omission pruned.

    Heat and balance were weak-positive in consumed diagnostics. Equal 1/2 +
    1/2 is pre-registered as the simplest non-tuned combination.
    """
    return _transform(
        source_rows,
        lambda row: (
            float(row.get("heat_score", NEUTRAL_SCORE))
            + float(row.get("balance_score", NEUTRAL_SCORE))
        )
        / 2.0,
        scorer_label="DLT.back.heat_balance_equal",
        explanation=(
            "V2.3研究评分：后区等权使用热度与结构均衡，遗漏项删除；"
            "权重固定为1/2+1/2，不按开奖结果调参。"
        ),
    )


def score_ssq_front_v23(source_rows: list[dict]) -> list[dict]:
    """SSQ front: shrink fully to a neutral score.

    No SSQ front feature showed stable positive evidence across consumed blocks.
    Equal scores explicitly encode 'no ranking claim' instead of forcing noise
    into a predictive ordering.
    """
    return _transform(
        source_rows,
        lambda _row: NEUTRAL_SCORE,
        scorer_label="SSQ.front.neutral_shrink",
        explanation=(
            "V2.3研究评分：红球特征未出现稳定正向证据，因此全部收缩到中性分；"
            "该候选不声称红球历史冷热/遗漏具备预测排序能力。"
        ),
    )


def score_ssq_back_v23(source_rows: list[dict]) -> list[dict]:
    """SSQ back: shrink fully to a neutral score for the same reason as front."""
    return _transform(
        source_rows,
        lambda _row: NEUTRAL_SCORE,
        scorer_label="SSQ.back.neutral_shrink",
        explanation=(
            "V2.3研究评分：蓝球特征未出现稳定正向证据，因此全部收缩到中性分；"
            "该候选不声称蓝球历史冷热/遗漏具备预测排序能力。"
        ),
    )
