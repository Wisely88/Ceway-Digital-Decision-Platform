#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from multiregime_v25 import DLT, SSQ  # noqa: E402
from multiregime_v26 import generate_multiregime_collision_plan  # noqa: E402
from pushplus_v26 import build_v26_prediction_digest, send_pushplus  # noqa: E402


def load_history(game: str) -> list[dict]:
    path = BACKEND / "data" / f"{game.lower()}_history.csv"
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if game == "DLT":
                front = [int(raw[f"f{i}"]) for i in range(1, 6)]
                back = [int(raw[f"b{i}"]) for i in range(1, 3)]
            else:
                front = [int(raw[f"f{i}"]) for i in range(1, 7)]
                back = [int(raw["b1"])]
            rows.append({"issue": str(raw["issue"]), "front": front, "back": back})
    return rows


def next_issue(issue: str) -> str:
    if not issue.isdigit():
        raise ValueError(f"Cannot infer next issue from {issue!r}; pass --target-issue")
    return str(int(issue) + 1).zfill(len(issue))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render/send CEWAY V2.6 collision-aware prediction using one shared PushPlus digest")
    parser.add_argument("--game", choices=["DLT", "SSQ"], required=True)
    parser.add_argument("--target-issue")
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--send", action="store_true", help="Actually send via PushPlus; default is dry-run")
    args = parser.parse_args()

    spec = DLT if args.game == "DLT" else SSQ
    history = load_history(args.game)
    cutoff = str(history[-1]["issue"])
    target = args.target_issue or next_issue(cutoff)
    plan = generate_multiregime_collision_plan(history, spec, budget=args.budget, history_cutoff_issue=cutoff)
    digest = build_v26_prediction_digest(plan, target_issue=target)

    print(digest["markdown"])
    if args.send:
        result = send_pushplus(digest)
        print(f"\nPushPlus: code={result.get('code')} msg={result.get('msg')}")
    else:
        print("\n[DRY-RUN] PushPlus not sent. Set PUSHPLUS_TOKEN and add --send to deliver this exact V2.6 content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
