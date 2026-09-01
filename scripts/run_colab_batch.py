#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from backtest import build_dlt_backtest, build_ssq_backtest
from engine import load_dlt_history, load_ssq_history


def build_payload(game: str, budget: int, periods: int, window: int) -> dict:
    if game == "dlt":
        result = build_dlt_backtest(
            load_dlt_history(), budget=budget, periods=periods, window=window
        )
    else:
        result = build_ssq_backtest(
            load_ssq_history(), budget=budget, periods=periods, window=window
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game": game,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic CEWAY backtests.")
    parser.add_argument("--game", choices=("dlt", "ssq"), required=True)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--periods", type=int, default=100)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if min(args.budget, args.periods, args.window) <= 0:
        parser.error("budget, periods, and window must be positive")

    payload = build_payload(args.game, args.budget, args.periods, args.window)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
