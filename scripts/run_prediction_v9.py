#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from engine import load_dlt_history, load_ssq_history
from predictor_v9 import DLT, SSQ, freeze_prediction, generate_prediction_v9


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a CEWAY Prediction V9 research plan.")
    parser.add_argument("--game", choices=("dlt", "ssq"), required=True)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--seed", default="ceway-v9")
    parser.add_argument("--cutoff-issue", default=None)
    parser.add_argument("--windows", default="20,50,100,200")
    parser.add_argument("--candidate-band", type=int, default=18)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    spec = DLT if args.game == "dlt" else SSQ
    history = load_dlt_history() if args.game == "dlt" else load_ssq_history()
    windows = tuple(int(item.strip()) for item in args.windows.split(",") if item.strip())
    plan = generate_prediction_v9(
        history,
        spec,
        budget=args.budget,
        windows=windows,
        seed=args.seed,
        candidate_band=args.candidate_band,
        history_cutoff_issue=args.cutoff_issue,
    )
    plan = freeze_prediction(plan)
    payload = json.dumps(plan, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
