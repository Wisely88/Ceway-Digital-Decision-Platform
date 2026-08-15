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


def holdout_history(history: list[dict], development_periods: int) -> list[dict]:
    if development_periods <= 0:
        raise ValueError("development_periods must be positive")
    if len(history) <= development_periods + 32:
        raise ValueError("not enough history for a non-overlapping holdout block")
    return history[:-development_periods]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V2.1 exposure generator on non-overlapping historical holdout")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--development-periods", type=int, default=50)
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

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    full_histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    histories = {
        game: holdout_history(history, args.development_periods)
        for game, history in full_histories.items()
    }

    rows = []
    for game in ("DLT", "SSQ"):
        for window in windows:
            print(
                f"V2.1 HOLDOUT {game}: periods={args.periods}, window={window}, "
                f"excluded_recent_points={args.development_periods}",
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
        "schema_version": "ceway.v2.1.exposure-holdout.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "retrospective_historical_holdout_non_overlapping",
        "parameter_provenance": (
            "V2.1 structural defaults were fixed from synthetic score/diversity tests before this historical holdout. "
            "The holdout excludes the recent development prediction block."
        ),
        "settings": {
            "periods": args.periods,
            "development_periods_excluded": args.development_periods,
            "windows": windows,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "data": {
            game: {
                "full_history_count": len(full_histories[game]),
                "holdout_history_count": len(histories[game]),
                "full_latest_issue": full_histories[game][-1]["issue"],
                "holdout_latest_issue": histories[game][-1]["issue"],
            }
            for game in ("DLT", "SSQ")
        },
        "rows": rows,
        "interpretation": (
            "This is a retrospective non-overlapping holdout. A positive result can justify frozen forward shadow validation, "
            "but not a claim of predictive certainty or guaranteed return."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
