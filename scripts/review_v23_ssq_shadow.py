from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import load_ssq_history  # noqa: E402
from freeze_v2 import verify_freeze_manifest  # noqa: E402
from review import review_ssq_plan  # noqa: E402


DEFAULT_SHADOW = ROOT_DIR / "research" / "shadow" / "ssq" / "2026094-v23-coverage-shadow.json"
DEFAULT_CONTROLS = ROOT_DIR / "research" / "shadow" / "ssq" / "2026094-v23-matched-random-controls.json"


def canonical_tickets(tickets: list[dict]) -> list[dict]:
    rows = [
        {
            "front": sorted(int(number) for number in row.get("front", [])),
            "back": sorted(int(number) for number in row.get("back", [])),
        }
        for row in tickets
    ]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))


def verify_frozen_row(manifest: dict, tickets: list[dict]) -> dict:
    digest = verify_freeze_manifest(manifest)
    if digest.get("valid") is not True:
        return digest
    match = canonical_tickets(tickets) == canonical_tickets(manifest.get("tickets", []))
    return {
        **digest,
        "ticket_match": match,
        "valid": bool(match),
        "status": "valid" if match else "invalid",
        "reason": "manifest digest and stored ticket rows match" if match else "stored ticket rows differ from manifest",
    }


def review_metrics(tickets: list[dict], budget: int, draw: dict) -> dict:
    plan = {
        "mode": "single",
        "strategy": "frozen_shadow_review",
        "cost": int(budget),
        "tickets": len(tickets),
        "items": tickets,
    }
    reviewed = review_ssq_plan(plan, draw)
    details = reviewed.get("details") or []
    mean_hits = mean(
        float(row.get("front_hits", 0) + row.get("back_hits", 0))
        for row in details
    ) if details else 0.0
    best = reviewed.get("best") or {}
    return {
        "best_hit": best.get("hit_label", "-"),
        "best_hit_units": float(best.get("front_hits", 0) + best.get("back_hits", 0)),
        "best_prize_label": best.get("prize_label", "-"),
        "mean_ticket_hit_units": round(mean_hits, 4),
        "hit_tickets": int(reviewed.get("hit_tickets", 0)),
        "record_hit": 1 if reviewed.get("hit_tickets", 0) > 0 else 0,
        "prize_distribution": reviewed.get("prize_distribution", {}),
        "details": details,
    }


def build_report(shadow_path: Path, controls_path: Path) -> dict:
    shadow = json.loads(shadow_path.read_text(encoding="utf-8"))
    controls = json.loads(controls_path.read_text(encoding="utf-8"))
    shadow_manifest = shadow.get("freeze_manifest") or {}
    shadow_tickets = shadow.get("plan", {}).get("items", [])
    shadow_integrity = verify_frozen_row(shadow_manifest, shadow_tickets)

    control_integrities = []
    for control in controls.get("controls", []):
        control_integrities.append(
            {
                "control_index": control.get("control_index"),
                **verify_frozen_row(control.get("freeze_manifest") or {}, control.get("tickets", [])),
            }
        )

    target_issue = str(shadow_manifest.get("target_issue"))
    reference_sha = str(shadow_manifest.get("sha256"))
    link_valid = (
        str(controls.get("target_issue")) == target_issue
        and str(controls.get("history_cutoff_issue")) == str(shadow_manifest.get("history_cutoff_issue"))
        and str(controls.get("reference_shadow_sha256")) == reference_sha
    )
    all_integrity_valid = (
        shadow_integrity.get("valid") is True
        and all(row.get("valid") is True for row in control_integrities)
        and link_valid
    )

    history = load_ssq_history()
    latest_issue = str(history[-1]["issue"]) if history else None
    target_draw = next((row for row in history if str(row.get("issue")) == target_issue), None)
    base = {
        "schema_version": "ceway.v2.3.shadow-review.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "game": "SSQ",
        "target_issue": target_issue,
        "history_latest_issue": latest_issue,
        "shadow_sha256": reference_sha,
        "integrity": {
            "shadow": shadow_integrity,
            "controls": control_integrities,
            "reference_link_valid": link_valid,
            "all_valid": all_integrity_valid,
        },
    }
    if not all_integrity_valid:
        return {
            **base,
            "status": "INVALID",
            "reason": "frozen shadow/control integrity failed; refusing outcome review",
        }
    if target_draw is None:
        return {
            **base,
            "status": "PENDING",
            "reason": f"target issue {target_issue} is not present in SSQ history yet",
        }

    shadow_result = review_metrics(shadow_tickets, int(shadow_manifest.get("budget", 0)), target_draw)
    control_results = []
    for control in controls.get("controls", []):
        manifest = control["freeze_manifest"]
        result = review_metrics(control["tickets"], int(manifest.get("budget", 0)), target_draw)
        control_results.append({"control_index": control["control_index"], **result})

    control_mean_best = mean(row["best_hit_units"] for row in control_results)
    control_mean_ticket = mean(row["mean_ticket_hit_units"] for row in control_results)
    control_mean_record = mean(row["record_hit"] for row in control_results)
    return {
        **base,
        "status": "REVIEWED",
        "actual": {
            "issue": target_draw["issue"],
            "date": target_draw.get("date"),
            "front": target_draw["front"],
            "back": target_draw["back"],
        },
        "shadow": shadow_result,
        "controls": control_results,
        "pre_registered_control_mean": {
            "best_hit_units": round(control_mean_best, 4),
            "mean_ticket_hit_units": round(control_mean_ticket, 4),
            "record_hit": round(control_mean_record, 4),
        },
        "shadow_minus_control_mean": {
            "best_hit_units": round(shadow_result["best_hit_units"] - control_mean_best, 4),
            "mean_ticket_hit_units": round(shadow_result["mean_ticket_hit_units"] - control_mean_ticket, 4),
            "record_hit": round(shadow_result["record_hit"] - control_mean_record, 4),
        },
        "interpretation": (
            "This is one prospective shadow draw against three pre-registered matched-random controls. "
            "Record it as evidence only; one draw cannot establish predictive advantage or expected return."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and review frozen CEWAY V2.3 SSQ prospective shadow")
    parser.add_argument("--shadow", type=Path, default=DEFAULT_SHADOW)
    parser.add_argument("--controls", type=Path, default=DEFAULT_CONTROLS)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v23_ssq_shadow_review.json",
    )
    args = parser.parse_args()
    report = build_report(args.shadow, args.controls)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "target_issue": report["target_issue"],
        "history_latest_issue": report.get("history_latest_issue"),
        "all_integrity_valid": report["integrity"]["all_valid"],
        "shadow_sha256": report["shadow_sha256"],
    }, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0 if report["status"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
