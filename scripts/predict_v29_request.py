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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from multiregime_v25 import DLT, SSQ  # noqa: E402
from multiregime_v29 import MULTIREGIME_V29_VERSION, generate_multiregime_protected_fusion_plan  # noqa: E402
from push_v27_prediction import load_history  # noqa: E402


def _fmt(numbers: list[int]) -> str:
    return " ".join(f"{int(n):02d}" for n in numbers)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a frozen CEWAY V2.9 prospective request")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    request = json.loads(args.request.read_text(encoding="utf-8"))
    game = str(request["game"]).upper()
    spec = DLT if game == "DLT" else SSQ
    history = load_history(game)
    supplemental = list(request.get("supplemental_history", []))
    existing = {str(row["issue"]) for row in history}
    for row in supplemental:
        issue = str(row["issue"])
        normalized = {"issue": issue, "front": [int(n) for n in row["front"]], "back": [int(n) for n in row["back"]]}
        if issue in existing:
            continue
        history.append(normalized)
        existing.add(issue)
    history.sort(key=lambda row: int(str(row["issue"])))

    cutoff = str(request["required_history_cutoff"])
    if str(history[-1]["issue"]) != cutoff:
        raise ValueError(f"history cutoff mismatch: expected {cutoff}, got {history[-1]['issue']}")
    target = str(request["target_issue"])
    plan = generate_multiregime_protected_fusion_plan(history, spec, budget=int(request.get("budget", 20)), history_cutoff_issue=cutoff)
    payload = {
        "schema_version": "ceway.v29.prospective-freeze.v1",
        "game": game,
        "target_issue": target,
        "history_cutoff_issue": cutoff,
        "generator_version": MULTIREGIME_V29_VERSION,
        "production_enabled": False,
        "request_source": str(args.request),
        "plan": plan,
    }

    print(f"# CEWAY V2.9 {game} {target}")
    print(f"- 历史截止期：**{cutoff}**")
    print(f"- 模型：**{MULTIREGIME_V29_VERSION}**")
    print(f"- 最终轨道计数：**{plan['track_diagnostics']['selected_counts_v29']}**")
    print(f"- 核心参考：**{_fmt(plan['core_reference']['front'])} + {_fmt(plan['core_reference']['back'])}**（{plan['core_reference']['origin_track']}）")
    print("\n## 最终10注")
    for idx, item in enumerate(plan["items"], 1):
        extra = ""
        if item.get("v29_replaced_track"):
            extra = f" | replaced={item['v29_replaced_track']} gain={item['v29_replacement_gain']:.4f}"
        print(f"{idx}. [{item['origin_track']}] {_fmt(item['front'])} + {_fmt(item['back'])} | score={float(item['rank_score']):.4f} | rank={item['front_track_rank']}{extra}")
    print("\n## Fusion 替换决策")
    for row in plan["v29_replacement_decisions"]:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nFREEZE={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
