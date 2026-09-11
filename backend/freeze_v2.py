from __future__ import annotations

import hashlib
import json
from typing import Sequence

from research_v2 import (
    GameSpec,
    build_freeze_manifest,
    combination_collision_audit,
    diversity_summary,
    expand_plan_tickets,
    history_through_issue,
)


CEWAY_V2_ALGORITHM_VERSION = "CEWAY-FWD-V2.0-dev2"
V2_PLAN_SCHEMA_VERSION = "ceway.plan.research.v2"


def _canonical_ticket_rows(tickets: Sequence[dict]) -> list[dict]:
    rows = [
        {
            "front": sorted(int(number) for number in ticket.get("front", [])),
            "back": sorted(int(number) for number in ticket.get("back", [])),
        }
        for ticket in tickets
    ]
    return sorted(rows, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))


def verify_freeze_manifest(manifest: dict | None) -> dict:
    if not isinstance(manifest, dict):
        return {"status": "not_available", "valid": None, "reason": "freeze manifest missing"}
    expected = manifest.get("sha256")
    if not expected:
        return {"status": "invalid", "valid": False, "reason": "freeze sha256 missing"}
    payload = {key: value for key, value in manifest.items() if key != "sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    computed = hashlib.sha256(encoded).hexdigest()
    valid = computed == expected
    return {
        "status": "valid" if valid else "invalid",
        "valid": valid,
        "expected_sha256": expected,
        "computed_sha256": computed,
        "reason": "manifest digest matches" if valid else "manifest digest mismatch",
    }


def verify_plan_freeze(plan: dict, spec: GameSpec) -> dict:
    research = plan.get("v2_research") if isinstance(plan, dict) else None
    if not isinstance(research, dict):
        return {"status": "legacy", "valid": None, "reason": "legacy plan has no V2 freeze metadata"}

    manifest = research.get("freeze_manifest")
    digest_check = verify_freeze_manifest(manifest)
    if digest_check.get("valid") is not True:
        return digest_check

    current_tickets = _canonical_ticket_rows(expand_plan_tickets(plan, spec))
    frozen_tickets = _canonical_ticket_rows((manifest or {}).get("tickets", []))
    if current_tickets != frozen_tickets:
        return {
            "status": "invalid",
            "valid": False,
            "reason": "current plan tickets do not match frozen manifest tickets",
            "expected_sha256": manifest.get("sha256"),
            "computed_sha256": digest_check.get("computed_sha256"),
        }

    if str(research.get("history_cutoff_issue")) != str(manifest.get("history_cutoff_issue")):
        return {
            "status": "invalid",
            "valid": False,
            "reason": "history cutoff differs from frozen manifest",
            "expected_sha256": manifest.get("sha256"),
            "computed_sha256": digest_check.get("computed_sha256"),
        }
    if str(research.get("target_issue")) != str(manifest.get("target_issue")):
        return {
            "status": "invalid",
            "valid": False,
            "reason": "target issue differs from frozen manifest",
            "expected_sha256": manifest.get("sha256"),
            "computed_sha256": digest_check.get("computed_sha256"),
        }

    return {
        "status": "valid",
        "valid": True,
        "reason": "manifest digest and current plan tickets match",
        "sha256": manifest.get("sha256"),
        "history_cutoff_issue": manifest.get("history_cutoff_issue"),
        "target_issue": manifest.get("target_issue"),
        "algorithm_version": manifest.get("algorithm_version"),
    }


def attach_plan_v2_metadata(
    plan: dict,
    *,
    game: str,
    spec: GameSpec,
    history: Sequence[dict],
    history_cutoff_issue: str | None,
    target_issue: str | None,
    parameters: dict,
    algorithm_version: str = CEWAY_V2_ALGORITHM_VERSION,
) -> dict:
    if not history_cutoff_issue or not target_issue:
        plan["v2_research"] = {
            "schema_version": V2_PLAN_SCHEMA_VERSION,
            "status": "not_frozen",
            "algorithm_version": algorithm_version,
            "history_cutoff_issue": history_cutoff_issue,
            "target_issue": target_issue,
            "reason": "history cutoff or target issue unavailable",
        }
        return plan

    cutoff_history = history_through_issue(history, history_cutoff_issue)
    tickets = expand_plan_tickets(plan, spec)
    if not cutoff_history or not tickets:
        plan["v2_research"] = {
            "schema_version": V2_PLAN_SCHEMA_VERSION,
            "status": "not_frozen",
            "algorithm_version": algorithm_version,
            "history_cutoff_issue": history_cutoff_issue,
            "target_issue": target_issue,
            "reason": "cutoff history or complete ticket set unavailable",
        }
        return plan

    manifest = build_freeze_manifest(
        game=game,
        target_issue=target_issue,
        history_cutoff_issue=history_cutoff_issue,
        algorithm_version=algorithm_version,
        parameters=parameters,
        tickets=tickets,
        budget=int(plan.get("cost", parameters.get("budget", 0)) or 0),
        seed=parameters.get("seed"),
    )
    plan["v2_research"] = {
        "schema_version": V2_PLAN_SCHEMA_VERSION,
        "status": "frozen",
        "algorithm_version": algorithm_version,
        "history_cutoff_issue": str(history_cutoff_issue),
        "target_issue": str(target_issue),
        "freeze_sha256": manifest["sha256"],
        "freeze_manifest": manifest,
        "collision_audit": combination_collision_audit(tickets, cutoff_history, spec),
        "diversity": {
            "front": diversity_summary(ticket["front"] for ticket in tickets),
            "back": diversity_summary(ticket["back"] for ticket in tickets),
        },
    }
    return plan


def ensure_plan_v2_metadata(
    plan: dict,
    *,
    game: str,
    spec: GameSpec,
    history: Sequence[dict],
    history_cutoff_issue: str | None,
    target_issue: str | None,
    parameters: dict,
) -> dict:
    research = plan.get("v2_research")
    if isinstance(research, dict) and research.get("freeze_manifest"):
        integrity = verify_plan_freeze(plan, spec)
        if integrity.get("valid") is not True:
            raise ValueError(f"V2 freeze integrity check failed: {integrity.get('reason')}")
        return plan
    return attach_plan_v2_metadata(
        plan,
        game=game,
        spec=spec,
        history=history,
        history_cutoff_issue=history_cutoff_issue,
        target_issue=target_issue,
        parameters=parameters,
    )
