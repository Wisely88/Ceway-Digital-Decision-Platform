from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from freeze_v2 import verify_freeze_manifest  # noqa: E402


LEDGER = ROOT_DIR / "research" / "evidence-ledger-v2.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_track(name: str, track: dict) -> dict:
    registry_path = ROOT_DIR / track["frozen_registry"]
    registry = read_json(registry_path)
    manifest = registry.get("freeze_manifest") or {}
    digest = verify_freeze_manifest(manifest)
    errors: list[str] = []

    if digest.get("valid") is not True:
        errors.append(f"freeze manifest invalid: {digest.get('reason')}")
    if str(manifest.get("target_issue")) != str(track.get("target_issue")):
        errors.append("target_issue mismatch")
    if str(manifest.get("history_cutoff_issue")) != str(track.get("history_cutoff_issue")):
        errors.append("history_cutoff_issue mismatch")
    if str(manifest.get("sha256")) != str(track.get("freeze_sha256")):
        errors.append("freeze_sha256 mismatch")

    if name == "SSQ":
        controls_path = ROOT_DIR / track["matched_random_controls"]
        controls = read_json(controls_path)
        if int(controls.get("control_count", 0)) != int(track.get("control_count", 0)):
            errors.append("control_count mismatch")
        if str(controls.get("reference_shadow_sha256")) != str(track.get("freeze_sha256")):
            errors.append("controls do not reference frozen shadow SHA")
        if str(controls.get("target_issue")) != str(track.get("target_issue")):
            errors.append("controls target_issue mismatch")
        for control in controls.get("controls", []):
            control_digest = verify_freeze_manifest(control.get("freeze_manifest") or {})
            if control_digest.get("valid") is not True:
                errors.append(f"control {control.get('control_index')} manifest invalid")

    return {
        "track": name,
        "valid": not errors,
        "errors": errors,
        "target_issue": track.get("target_issue"),
        "history_cutoff_issue": track.get("history_cutoff_issue"),
        "freeze_sha256": track.get("freeze_sha256"),
    }


def main() -> int:
    ledger = read_json(LEDGER)
    tracks = ledger.get("prospective_tracks") or {}
    results = [validate_track(name, track) for name, track in tracks.items()]

    policy = ledger.get("policy") or {}
    errors: list[str] = []
    if int(policy.get("next_untouched_historical_block_min_excluded_recent_points", 0)) < 250:
        errors.append("historical holdout boundary regressed below excluded_recent_points=250")
    if not policy.get("frozen_objects_are_immutable"):
        errors.append("frozen_objects_are_immutable must remain true")
    if not policy.get("historical_blocks_are_single_use_for_promotion_evidence"):
        errors.append("historical blocks must remain single-use")

    all_valid = all(row["valid"] for row in results) and not errors
    report = {
        "schema_version": "ceway.research-evidence-ledger-validation.v1",
        "valid": all_valid,
        "tracks": results,
        "policy_errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
