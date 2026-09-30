from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import load_dlt_history  # noqa: E402
from freeze_v2 import verify_freeze_manifest, verify_plan_freeze  # noqa: E402
from research_v2 import DLT  # noqa: E402
from review import review_plan  # noqa: E402


def load_registry(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("game") != "DLT":
        raise ValueError("forward registry is not DLT")
    manifest = payload.get("freeze_manifest")
    integrity = verify_freeze_manifest(manifest)
    if integrity.get("valid") is not True:
        raise ValueError(f"registry manifest integrity failed: {integrity.get('reason')}")
    if str(payload.get("target_issue")) != str(manifest.get("target_issue")):
        raise ValueError("registry target issue differs from freeze manifest")
    if str(payload.get("history_cutoff_issue")) != str(manifest.get("history_cutoff_issue")):
        raise ValueError("registry history cutoff differs from freeze manifest")
    return payload


def frozen_plan(registry: dict) -> dict:
    manifest = registry["freeze_manifest"]
    tickets = manifest.get("tickets", [])
    plan = {
        "mode": "single",
        "strategy": manifest.get("parameters", {}).get("strategy", "balanced"),
        "cost": int(manifest.get("budget", 0)),
        "tickets": len(tickets),
        "items": [
            {
                "front": list(ticket.get("front", [])),
                "back": list(ticket.get("back", [])),
                "score": 0,
                "explanation": ["Forward shadow review replays the immutable frozen ticket only."],
            }
            for ticket in tickets
        ],
        "v2_research": {
            "schema_version": "ceway.plan.research.v2",
            "status": "frozen",
            "algorithm_version": manifest.get("algorithm_version"),
            "history_cutoff_issue": str(manifest.get("history_cutoff_issue")),
            "target_issue": str(manifest.get("target_issue")),
            "freeze_sha256": manifest.get("sha256"),
            "freeze_manifest": manifest,
        },
    }
    integrity = verify_plan_freeze(plan, DLT)
    if integrity.get("valid") is not True:
        raise ValueError(f"reconstructed frozen plan integrity failed: {integrity.get('reason')}")
    return plan


def find_target_draw(history: list[dict], target_issue: str) -> dict | None:
    for row in history:
        if str(row.get("issue")) == str(target_issue):
            return row
    return None


def evaluate_registry(registry: dict, history: list[dict]) -> dict:
    target_issue = str(registry["target_issue"])
    cutoff_issue = str(registry["history_cutoff_issue"])
    manifest = registry["freeze_manifest"]
    current_latest = str(history[-1]["issue"]) if history else None
    target_draw = find_target_draw(history, target_issue)

    base = {
        "schema_version": "ceway.forward-shadow.review.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game": "DLT",
        "candidate_version": registry.get("candidate_version"),
        "target_issue": target_issue,
        "history_cutoff_issue": cutoff_issue,
        "current_latest_issue": current_latest,
        "freeze_sha256": manifest.get("sha256"),
        "source_registry": f"research/forward/dlt/{target_issue}-v24.json",
        "production_enabled": False,
    }

    if target_draw is None:
        return {
            **base,
            "status": "PENDING",
            "message": "Target draw is not present in DLT history. Frozen tickets were not regenerated or modified.",
        }

    plan = frozen_plan(registry)
    review = review_plan(plan, target_draw)
    return {
        **base,
        "status": "REVIEWED",
        "message": "Reviewed the original frozen forward-shadow tickets against the target draw; no regeneration occurred.",
        "actual": review.get("actual"),
        "freeze_integrity": review.get("freeze_integrity"),
        "best": review.get("best"),
        "details": review.get("details"),
        "hit_tickets": review.get("hit_tickets"),
        "hit_rate": review.get("hit_rate"),
        "prize_distribution": review.get("prize_distribution"),
        "cost": review.get("cost"),
        "tickets": review.get("tickets"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review an immutable DLT V2.4 forward-shadow registry entry")
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT_DIR / "research" / "forward" / "dlt" / "26092-v24.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "dlt_v24_forward_review.json",
    )
    args = parser.parse_args()

    registry = load_registry(args.registry)
    history = load_dlt_history()
    result = evaluate_registry(registry, history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"FORWARD_REVIEW status={result['status']} target={result['target_issue']} "
        f"cutoff={result['history_cutoff_issue']} latest={result.get('current_latest_issue')} "
        f"sha256={result['freeze_sha256']}",
        flush=True,
    )
    if result["status"] == "REVIEWED":
        print("FORWARD_REVIEW_RESULT=" + json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
