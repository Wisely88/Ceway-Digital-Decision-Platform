#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from multiregime_v28 import MULTIREGIME_V28_VERSION, review_fusion_ranking  # noqa: E402


def load_actual(game: str, issue: str) -> tuple[list[int], list[int]]:
    path = BACKEND / "data" / f"{game.lower()}_history.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if str(raw["issue"]) != str(issue):
                continue
            if game == "DLT":
                return [int(raw[f"f{i}"]) for i in range(1, 6)], [int(raw[f"b{i}"]) for i in range(1, 3)]
            return [int(raw[f"f{i}"]) for i in range(1, 7)], [int(raw["b1"])]
    raise ValueError(f"Target issue {issue} not found in {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a frozen V2.8 Fusion ranking without regeneration")
    parser.add_argument("--game", choices=["DLT", "SSQ"], required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    frozen = json.loads(args.freeze.read_text(encoding="utf-8"))
    plan = frozen.get("plan", frozen)
    if plan.get("generator_version") != MULTIREGIME_V28_VERSION:
        raise ValueError("Review only accepts a frozen V2.8 plan")
    actual_front, actual_back = load_actual(args.game, args.issue)
    result = review_fusion_ranking(plan, actual_front, actual_back)
    result.update({"game": args.game, "target_issue": str(args.issue), "actual_front": actual_front, "actual_back": actual_back})
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
