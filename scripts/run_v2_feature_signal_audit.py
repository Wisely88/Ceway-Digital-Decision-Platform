from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import calculate_ssq_trends, calculate_trends, load_dlt_history, load_ssq_history  # noqa: E402
from research_v2 import bootstrap_mean_ci, history_through_issue  # noqa: E402
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402


CONSUMED_BLOCKS = (
    ("development", 0),
    ("v1_consumed_holdout", 50),
    ("v21_fresh_holdout", 100),
)
FEATURES = ("heat_score", "missing_score", "balance_score", "total_score")
# exclude=150 is allocated to the separately frozen V2.2 multi-window consensus
# holdout. Any scorer redesigned after this feature audit must move one full
# 50-outcome block farther back to avoid reusing that evidence.
NEXT_SCORER_HOLDOUT_EXCLUDED_RECENT_POINTS = 200


def feature_auc(rows: list[dict], winners: list[int], pool_size: int, feature: str) -> float:
    values = {int(row["number"]): float(row.get(feature, 0.0)) for row in rows}
    winner_set = set(int(number) for number in winners)
    losers = [number for number in range(1, pool_size + 1) if number not in winner_set]
    if not winner_set or not losers:
        return 0.5

    wins = 0.0
    comparisons = 0
    for winner in winner_set:
        winner_value = values.get(winner, 0.0)
        for loser in losers:
            loser_value = values.get(loser, 0.0)
            comparisons += 1
            if winner_value > loser_value:
                wins += 1.0
            elif winner_value == loser_value:
                wins += 0.5
    return wins / comparisons if comparisons else 0.5


def top_quartile_delta(rows: list[dict], winners: list[int], pool_size: int, feature: str) -> float:
    top_count = max(1, (pool_size + 3) // 4)
    ranked = sorted(
        ((int(row["number"]), float(row.get(feature, 0.0))) for row in rows),
        key=lambda item: (-item[1], item[0]),
    )
    top_numbers = {number for number, _ in ranked[:top_count]}
    winner_set = set(int(number) for number in winners)
    observed = len(winner_set & top_numbers) / max(1, len(winner_set))
    expected = top_count / pool_size
    return observed - expected


def ci(values: list[float], seed: str) -> dict:
    result = bootstrap_mean_ci(values, seed=seed)
    return {
        "mean": round(float(result["mean"]), 4),
        "ci95_low": round(float(result["low"]), 4),
        "ci95_high": round(float(result["high"]), 4),
    }


def block_history(full_history: list[dict], excluded_recent_points: int) -> list[dict]:
    return full_history[:-excluded_recent_points] if excluded_recent_points else full_history


def audit_block(
    *,
    game: str,
    full_history: list[dict],
    block_name: str,
    excluded_recent_points: int,
    periods: int,
    window: int,
) -> dict:
    history = block_history(full_history, excluded_recent_points)
    if len(history) < periods + 31:
        raise ValueError(f"not enough history for {game} {block_name}")

    if game == "DLT":
        trend_builder = calculate_trends
        front_scorer = score_front_numbers
        back_scorer = score_back_numbers
        front_pool = 35
        back_pool = 12
    else:
        trend_builder = calculate_ssq_trends
        front_scorer = score_ssq_front_numbers
        back_scorer = score_ssq_back_numbers
        front_pool = 33
        back_pool = 16

    end_source = len(history) - 2
    start_source = end_source - periods + 1
    values: dict[str, dict[str, list[float]]] = {
        zone: {feature: [] for feature in FEATURES}
        for zone in ("front", "back")
    }
    top_values: dict[str, dict[str, list[float]]] = {
        zone: {feature: [] for feature in FEATURES}
        for zone in ("front", "back")
    }
    outcomes: list[str] = []

    for index in range(start_source, end_source + 1):
        source_issue = str(history[index]["issue"])
        actual = history[index + 1]
        training = history_through_issue(history, source_issue)
        trends = trend_builder(training, window=min(window, len(training)))
        front_rows = front_scorer(trends)
        back_rows = back_scorer(trends)

        for feature in FEATURES:
            values["front"][feature].append(
                feature_auc(front_rows, actual["front"], front_pool, feature) - 0.5
            )
            values["back"][feature].append(
                feature_auc(back_rows, actual["back"], back_pool, feature) - 0.5
            )
            top_values["front"][feature].append(
                top_quartile_delta(front_rows, actual["front"], front_pool, feature)
            )
            top_values["back"][feature].append(
                top_quartile_delta(back_rows, actual["back"], back_pool, feature)
            )
        outcomes.append(str(actual["issue"]))

    return {
        "game": game,
        "block": block_name,
        "excluded_recent_points": excluded_recent_points,
        "window": window,
        "periods": len(outcomes),
        "first_outcome_issue": outcomes[0],
        "last_outcome_issue": outcomes[-1],
        "features": {
            zone: {
                feature: {
                    "auc_advantage_over_random": ci(
                        values[zone][feature],
                        f"feature-{game}-{block_name}-{window}-{zone}-{feature}-auc",
                    ),
                    "top_quartile_hit_rate_delta": ci(
                        top_values[zone][feature],
                        f"feature-{game}-{block_name}-{window}-{zone}-{feature}-topq",
                    ),
                }
                for feature in FEATURES
            }
            for zone in ("front", "back")
        },
    }


def classify_feature(rows: list[dict], game: str, zone: str, feature: str) -> dict:
    selected = [row for row in rows if row["game"] == game]
    auc_rows = [
        row["features"][zone][feature]["auc_advantage_over_random"]
        for row in selected
    ]
    positive = sum(metric["ci95_low"] > 0 for metric in auc_rows)
    negative = sum(metric["ci95_high"] < 0 for metric in auc_rows)
    positive_means = sum(metric["mean"] > 0 for metric in auc_rows)
    negative_means = sum(metric["mean"] < 0 for metric in auc_rows)
    mean_auc_advantage = round(mean(metric["mean"] for metric in auc_rows), 4)

    # Nine correlated cells: 3 consumed blocks x 3 windows. Classification is
    # intentionally conservative and descriptive, not a formal multiple-test claim.
    if negative >= 3 and negative_means >= 6:
        status = "HARMFUL_DIRECTION_RISK"
    elif positive >= 3 and positive_means >= 6:
        status = "PROMISING_DIRECTION"
    elif negative_means >= 6 and positive == 0:
        status = "WEAK_NEGATIVE"
    elif positive_means >= 6 and negative == 0:
        status = "WEAK_POSITIVE"
    else:
        status = "NEUTRAL_OR_UNSTABLE"

    return {
        "status": status,
        "mean_auc_advantage_across_consumed_cells": mean_auc_advantage,
        "significant_positive_cells": positive,
        "significant_negative_cells": negative,
        "positive_mean_cells": positive_means,
        "negative_mean_cells": negative_means,
        "cells": len(auc_rows),
    }


def build_recommendation(classifications: dict) -> dict:
    harmful = []
    promising = []
    neutral = []
    for game, zones in classifications.items():
        for zone, features in zones.items():
            for feature, result in features.items():
                item = f"{game}.{zone}.{feature}"
                if result["status"] == "HARMFUL_DIRECTION_RISK":
                    harmful.append(item)
                elif result["status"] in {"PROMISING_DIRECTION", "WEAK_POSITIVE"}:
                    promising.append(item)
                else:
                    neutral.append(item)
    return {
        "harmful_or_reverse_direction_candidates": harmful,
        "promising_candidates": promising,
        "neutral_or_unstable": neutral,
        "next_rule": (
            "Do not tune against exclude=150 or exclude=200. The exclude=150 block is allocated to the frozen V2.2 "
            "consensus holdout. Build any scorer redesign only from consumed feature-audit evidence, freeze its formula/version, "
            "then evaluate exactly once on the reserved exclude=200 50-outcome block."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit individual CEWAY scorer features on consumed research blocks")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v2_feature_signal_audit.json",
    )
    args = parser.parse_args()

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    rows = []
    for game in ("DLT", "SSQ"):
        for block_name, excluded in CONSUMED_BLOCKS:
            for window in windows:
                print(
                    f"FEATURE AUDIT {game}: block={block_name}, window={window}, periods={args.periods}",
                    flush=True,
                )
                row = audit_block(
                    game=game,
                    full_history=histories[game],
                    block_name=block_name,
                    excluded_recent_points=excluded,
                    periods=args.periods,
                    window=window,
                )
                rows.append(row)

    classifications = {
        game: {
            zone: {
                feature: classify_feature(rows, game, zone, feature)
                for feature in FEATURES
            }
            for zone in ("front", "back")
        }
        for game in ("DLT", "SSQ")
    }
    recommendation = build_recommendation(classifications)

    report = {
        "schema_version": "ceway.v2.feature-signal-audit.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Decompose the current 40/30/30 scorer into feature-level historical ordering signal.",
        "features": list(FEATURES),
        "settings": {
            "periods": args.periods,
            "windows": windows,
            "consumed_blocks": [name for name, _ in CONSUMED_BLOCKS],
        },
        "holdout_allocation": {
            "exclude_150": {
                "status": "ALLOCATED_TO_FROZEN_V22_CONSENSUS_HOLDOUT",
                "read_by_this_audit": False,
            },
            "exclude_200": {
                "status": "RESERVED_FOR_FUTURE_SCORER_REDESIGN_HOLDOUT",
                "periods": 50,
                "read_by_this_audit": False,
            },
        },
        "rows": rows,
        "classifications": classifications,
        "recommendation": recommendation,
        "guardrail": (
            "Classifications summarize correlated historical cells and are architecture diagnostics, not proof of prediction. "
            "This audit reads only exclude=0/50/100 blocks. Exclude=150 is owned by the frozen V2.2 consensus path; "
            "exclude=200 remains reserved for a future frozen scorer candidate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(classifications, ensure_ascii=False, indent=2), flush=True)
    print(json.dumps(recommendation, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
