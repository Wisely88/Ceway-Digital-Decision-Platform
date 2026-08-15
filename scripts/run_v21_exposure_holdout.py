from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from engine import load_dlt_history, load_ssq_history  # noqa: E402
from scripts.run_v21_exposure_ablation import run_game  # noqa: E402


FRESH_HOLDOUT_EXCLUDED_RECENT_POINTS = 100


def holdout_history(history: list[dict], excluded_recent_points: int) -> list[dict]:
    if excluded_recent_points <= 0:
        raise ValueError("excluded_recent_points must be positive")
    if len(history) <= excluded_recent_points + 32:
        raise ValueError("not enough history for a non-overlapping holdout block")
    return history[:-excluded_recent_points]


def block_provenance(history: list[dict], periods: int, excluded_recent_points: int) -> dict:
    """Describe the three non-overlapping outcome blocks used by CEWAY V2 research.

    With the default 50-point blocks:
    - newest 50 outcomes: V2.1 development diagnostics;
    - preceding 50 outcomes: already consumed by coverage-aware-greedy-v1 holdout;
    - preceding 50 outcomes: fresh V2.1 holdout evaluated by this script.
    """
    if periods <= 0:
        raise ValueError("periods must be positive")
    if excluded_recent_points < periods * 2:
        raise ValueError(
            "fresh V2.1 holdout must exclude at least two prior blocks: "
            "development + V1 consumed holdout"
        )
    required = excluded_recent_points + periods
    if len(history) < required + 1:
        raise ValueError("not enough history to describe fresh holdout boundaries")

    n = len(history)

    def outcome_block(end_exclusive: int, count: int) -> dict:
        start = end_exclusive - count
        rows = history[start:end_exclusive]
        return {
            "count": len(rows),
            "first_issue": rows[0]["issue"],
            "last_issue": rows[-1]["issue"],
        }

    development = outcome_block(n, periods)
    v1_consumed = outcome_block(n - periods, periods)
    fresh_holdout = outcome_block(n - excluded_recent_points, periods)

    return {
        "development_block": development,
        "v1_consumed_holdout_block": v1_consumed,
        "v21_fresh_holdout_block": fresh_holdout,
        "blocks_overlap": False,
        "rule": (
            "V2.1 fresh holdout outcomes must be older than both the recent development block "
            "and the V1 holdout block already inspected during coverage-aware-greedy-v1 evaluation."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V2.1 exposure generator on a fresh historical holdout")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument(
        "--excluded-recent-points",
        "--development-periods",
        dest="excluded_recent_points",
        type=int,
        default=FRESH_HOLDOUT_EXCLUDED_RECENT_POINTS,
        help="Recent prediction outcomes excluded before the fresh holdout. Default 100 = dev50 + V1 holdout50.",
    )
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v21_exposure_holdout.json",
    )
    args = parser.parse_args()

    if args.excluded_recent_points < args.periods * 2:
        raise ValueError(
            "V2.1 fresh holdout refused: excluded_recent_points must cover both "
            "the recent development block and the already-consumed V1 holdout block"
        )

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    full_histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    histories = {
        game: holdout_history(history, args.excluded_recent_points)
        for game, history in full_histories.items()
    }
    provenance = {
        game: block_provenance(
            history,
            periods=args.periods,
            excluded_recent_points=args.excluded_recent_points,
        )
        for game, history in full_histories.items()
    }

    rows = []
    for game in ("DLT", "SSQ"):
        for window in windows:
            print(
                f"V2.1 FRESH HOLDOUT {game}: periods={args.periods}, window={window}, "
                f"excluded_recent_points={args.excluded_recent_points}",
                flush=True,
            )
            row = run_game(
                game=game,
                history=histories[game],
                window=window,
                periods=args.periods,
                baseline_seeds=args.baseline_seeds,
                budget=args.budget,
                strategy=args.strategy,
            )
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)

    report = {
        "schema_version": "ceway.v2.1.exposure-holdout.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "fresh_retrospective_holdout_excluding_dev_and_v1_holdout",
        "parameter_provenance": (
            "V2.1 structural defaults were fixed from synthetic score/diversity tests before historical evaluation. "
            "This holdout excludes both the recent V2.1 development outcomes and the immediately preceding V1 holdout outcomes."
        ),
        "settings": {
            "periods": args.periods,
            "excluded_recent_points": args.excluded_recent_points,
            "windows": windows,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "block_provenance": provenance,
        "data": {
            game: {
                "full_history_count": len(full_histories[game]),
                "holdout_history_count": len(histories[game]),
                "full_latest_issue": full_histories[game][-1]["issue"],
                "holdout_cutoff_issue": histories[game][-1]["issue"],
            }
            for game in ("DLT", "SSQ")
        },
        "rows": rows,
        "interpretation": (
            "This is a fresh retrospective holdout that excludes two already-consumed 50-point blocks. "
            "A positive result can justify frozen forward shadow validation, but not a claim of predictive certainty or guaranteed return."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
