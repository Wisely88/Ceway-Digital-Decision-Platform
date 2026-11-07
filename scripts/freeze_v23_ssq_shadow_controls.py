from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import load_ssq_history  # noqa: E402
from freeze_v2 import verify_freeze_manifest  # noqa: E402
from random_control_v2 import robust_structure_matched_random_plan  # noqa: E402
from research_v2 import SSQ, build_freeze_manifest, diversity_summary, expand_plan_tickets  # noqa: E402


SSQ_MAIN_ZONES = ((1, 11), (12, 22), (23, 33))
SSQ_BACK_ZONES = ((1, 8), (9, 16))
CONTROL_VERSION = "pre-registered-structure-matched-random-v1"
DEFAULT_REFERENCE = ROOT_DIR / "research" / "shadow" / "ssq" / "2026094-v23-coverage-shadow.json"


def load_reference(path: Path) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    manifest = snapshot.get("freeze_manifest") or {}
    integrity = verify_freeze_manifest(manifest)
    if integrity.get("valid") is not True:
        raise ValueError(f"reference shadow integrity failed: {integrity.get('reason')}")
    if snapshot.get("production_enabled") is not False:
        raise ValueError("reference is not marked as non-production shadow")
    if manifest.get("game") != "SSQ":
        raise ValueError("reference manifest is not SSQ")
    return snapshot


def build_controls(reference: dict, count: int) -> dict:
    history = load_ssq_history()
    manifest = reference["freeze_manifest"]
    target_issue = str(manifest["target_issue"])
    cutoff_issue = str(manifest["history_cutoff_issue"])
    shadow_sha = str(manifest["sha256"])
    if any(str(row["issue"]) == target_issue for row in history):
        raise ValueError(f"target issue {target_issue} is already present; refusing post-draw control freeze")
    if str(history[-1]["issue"]) != cutoff_issue:
        raise ValueError(
            f"history moved beyond reference cutoff {cutoff_issue}; controls must be frozen against the same pre-draw state"
        )

    reference_plan = {
        "mode": "single",
        "strategy": "shadow_reference",
        "cost": int(manifest["budget"]),
        "tickets": len(manifest["tickets"]),
        "items": manifest["tickets"],
    }
    controls = []
    for index in range(count):
        seed = f"{shadow_sha}:matched-random-control:{index + 1}"
        plan = robust_structure_matched_random_plan(
            reference_plan,
            SSQ,
            seed=seed,
            main_zones=SSQ_MAIN_ZONES,
            bonus_zones=SSQ_BACK_ZONES,
            main_sum_tolerance=5,
            bonus_sum_tolerance=None,
        )
        tickets = expand_plan_tickets(plan, SSQ)
        control_manifest = build_freeze_manifest(
            game="SSQ",
            target_issue=target_issue,
            history_cutoff_issue=cutoff_issue,
            algorithm_version=CONTROL_VERSION,
            parameters={
                "baseline_type": "conditional_random_v2_robust",
                "reference_shadow_sha256": shadow_sha,
                "matched_on": ["zone_counts", "odd_even_count", "sum_band", "consecutive_groups"],
                "main_sum_tolerance": 5,
                "bonus_sum_tolerance": None,
                "control_index": index + 1,
            },
            tickets=tickets,
            budget=int(manifest["budget"]),
            seed=seed,
        )
        controls.append(
            {
                "control_index": index + 1,
                "seed": seed,
                "tickets": tickets,
                "front_diversity": diversity_summary(ticket["front"] for ticket in tickets),
                "back_diversity": diversity_summary(ticket["back"] for ticket in tickets),
                "freeze_manifest": control_manifest,
            }
        )

    return {
        "schema_version": "ceway.v2.3.shadow-controls.1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_PRE_REGISTERED_CONTROLS",
        "production_enabled": False,
        "game": "SSQ",
        "target_issue": target_issue,
        "history_cutoff_issue": cutoff_issue,
        "reference_shadow_sha256": shadow_sha,
        "control_version": CONTROL_VERSION,
        "control_count": count,
        "controls": controls,
        "guardrail": (
            "Controls were frozen before the target draw and must not be regenerated, cherry-picked, or replaced after results."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze matched-random controls for a frozen SSQ prospective shadow")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v23_ssq_shadow_controls.json",
    )
    args = parser.parse_args()
    if args.count <= 0:
        raise ValueError("count must be positive")
    report = build_controls(load_reference(args.reference), args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "target_issue": report["target_issue"],
        "reference_shadow_sha256": report["reference_shadow_sha256"],
        "controls": [
            {"index": row["control_index"], "sha256": row["freeze_manifest"]["sha256"]}
            for row in report["controls"]
        ],
    }, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
