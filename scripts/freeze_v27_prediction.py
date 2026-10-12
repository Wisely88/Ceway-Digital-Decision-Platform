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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from multiregime_v25 import DLT, SSQ  # noqa: E402
from multiregime_v27 import generate_multiregime_scarcity_combo_plan  # noqa: E402
from push_v27_prediction import load_history, next_issue  # noqa: E402
from pushplus_v27 import build_v27_prediction_digest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the complete CEWAY V2.7 plan including full scarcity rankings")
    parser.add_argument("--game", choices=["DLT", "SSQ"], required=True)
    parser.add_argument("--target-issue")
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec = DLT if args.game == "DLT" else SSQ
    history = load_history(args.game)
    cutoff = str(history[-1]["issue"])
    target = args.target_issue or next_issue(cutoff)
    plan = generate_multiregime_scarcity_combo_plan(history, spec, budget=args.budget, history_cutoff_issue=cutoff)
    digest = build_v27_prediction_digest(plan, target_issue=target)
    payload = {
        "schema_version": "ceway.v27.prospective-freeze.v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "game": args.game,
        "target_issue": str(target),
        "history_cutoff_issue": cutoff,
        "immutable_after_target_draw": True,
        "plan": plan,
        "digest_markdown": digest["markdown"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
