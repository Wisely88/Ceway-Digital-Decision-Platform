from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import calculate_trends, load_dlt_history  # noqa: E402
from fixed_window_v24 import FIXED_WINDOW_V24, FIXED_WINDOW_V24_VERSION, generate_dlt_fixed100_single  # noqa: E402
from freeze_v2 import attach_plan_v2_metadata, verify_plan_freeze  # noqa: E402
from research_v2 import DLT  # noqa: E402
from scorer import score_back_numbers, score_front_numbers  # noqa: E402


def next_numeric_issue(issue: str) -> str:
    text = str(issue)
    if not text.isdigit():
        raise ValueError(f"cannot infer next issue from non-numeric issue: {issue}")
    return str(int(text) + 1).zfill(len(text))


def build_forward_freeze(*, target_issue: str | None, budget: int, strategy: str) -> dict:
    history = load_dlt_history()
    if not history:
        raise ValueError("DLT history is empty")
    cutoff_issue = str(history[-1]["issue"])
    target_issue = str(target_issue or next_numeric_issue(cutoff_issue))
    if target_issue <= cutoff_issue:
        raise ValueError("target issue must be after the history cutoff")

    trends = calculate_trends(history, window=min(FIXED_WINDOW_V24, len(history)))
    score_table = score_front_numbers(trends)
    back_scores = score_back_numbers(trends)
    plan = generate_dlt_fixed100_single(budget, score_table, back_scores, strategy)

    algorithm_version = f"CEWAY-FWD-DLT-{FIXED_WINDOW_V24_VERSION}"
    parameters = {
        "research_role": "prospective_forward_shadow",
        "fixed_window": FIXED_WINDOW_V24,
        "budget": budget,
        "strategy": strategy,
        "combination_engine": "score-exposure-balanced-v2.1",
        "candidate_version": FIXED_WINDOW_V24_VERSION,
        "promotion_evidence_run": "31857644342",
        "frozen_before_outcome": True,
    }
    attach_plan_v2_metadata(
        plan,
        game="dlt",
        spec=DLT,
        history=history,
        history_cutoff_issue=cutoff_issue,
        target_issue=target_issue,
        parameters=parameters,
        algorithm_version=algorithm_version,
    )
    integrity = verify_plan_freeze(plan, DLT)
    if integrity.get("valid") is not True:
        raise RuntimeError(f"forward freeze failed integrity check: {integrity}")

    return {
        "schema_version": "ceway.forward-shadow.v2.4.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game": "DLT",
        "status": "FROZEN_FORWARD_SHADOW",
        "target_issue": target_issue,
        "history_cutoff_issue": cutoff_issue,
        "candidate_version": FIXED_WINDOW_V24_VERSION,
        "algorithm_version": algorithm_version,
        "promotion_evidence_run": "31857644342",
        "production_enabled": False,
        "mutation_policy": "No scorer, window, combination, budget, or ticket changes before target draw outcome.",
        "plan": plan,
        "integrity": integrity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the promoted DLT V2.4 candidate for the next forward draw")
    parser.add_argument("--target-issue", type=str, default=None)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "dlt_v24_forward_freeze.json")
    args = parser.parse_args()

    payload = build_forward_freeze(target_issue=args.target_issue, budget=args.budget, strategy=args.strategy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    plan = payload["plan"]
    research = plan["v2_research"]
    print(
        f"FORWARD_FREEZE target={payload['target_issue']} cutoff={payload['history_cutoff_issue']} "
        f"sha256={research['freeze_sha256']} tickets={plan.get('tickets')} cost={plan.get('cost')}",
        flush=True,
    )
    print("FORWARD_TICKETS=" + json.dumps(
        [{"front": item["front"], "back": item["back"]} for item in plan.get("items", [])],
        ensure_ascii=False,
        separators=(",", ":"),
    ), flush=True)
    print("FORWARD_FREEZE_JSON=" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
