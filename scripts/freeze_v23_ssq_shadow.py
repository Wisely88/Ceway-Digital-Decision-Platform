from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from engine import calculate_ssq_trends, load_ssq_history  # noqa: E402
from generator_v2 import GENERATOR_EXPOSURE_VERSION, generate_ssq_exposure_single  # noqa: E402
from research_v2 import SSQ, build_freeze_manifest, diversity_summary, expand_plan_tickets  # noqa: E402
from scorer import score_ssq_back_numbers, score_ssq_front_numbers  # noqa: E402
from scorer_v23 import SCORER_V23_VERSION, score_ssq_back_v23, score_ssq_front_v23  # noqa: E402


SHADOW_VERSION = "ssq-coverage-only-shadow-v2.3.1"
DEFAULT_BUDGET = 20


def next_numeric_issue(issue: str) -> str:
    """Return the immediate numeric successor, preserving width.

    CEWAY's current SSQ 2026 issue IDs are monotonic numeric strings. The CLI
    accepts --target-issue so year-boundary freezes can be explicit rather than
    silently guessing a rollover convention.
    """
    text = str(issue).strip()
    if not text.isdigit():
        raise ValueError("latest SSQ issue is not numeric; pass --target-issue explicitly")
    return str(int(text) + 1).zfill(len(text))


def build_shadow_snapshot(*, target_issue: str | None, budget: int) -> dict:
    history = load_ssq_history()
    if not history:
        raise ValueError("SSQ history is empty")

    latest = history[-1]
    cutoff_issue = str(latest["issue"])
    target = str(target_issue or next_numeric_issue(cutoff_issue))
    if any(str(row["issue"]) == target for row in history):
        raise ValueError(f"target issue {target} is already present in history; refusing post-draw freeze")

    # V2.3 SSQ explicitly makes no ranking claim. We still derive the ordinary
    # score-table schema at the cutoff, then shrink every score to neutral before
    # the frozen V2.1 exposure engine allocates coverage.
    trends = calculate_ssq_trends(history, window=min(100, len(history)))
    raw_front = score_ssq_front_numbers(trends)
    raw_back = score_ssq_back_numbers(trends)
    neutral_front = score_ssq_front_v23(raw_front)
    neutral_back = score_ssq_back_v23(raw_back)
    plan = generate_ssq_exposure_single(
        budget=budget,
        score_table=neutral_front,
        back_scores=neutral_back,
        strategy="balanced",
    )
    tickets = expand_plan_tickets(plan, SSQ)

    algorithm_version = "+".join(
        [SCORER_V23_VERSION, GENERATOR_EXPOSURE_VERSION, SHADOW_VERSION]
    )
    parameters = {
        "mode": "coverage_only_shadow",
        "scorer": {
            "front": "neutral_shrink",
            "back": "neutral_shrink",
            "predictive_ranking_claim": False,
        },
        "generator": GENERATOR_EXPOSURE_VERSION,
        "strategy": "balanced",
        "ticket_price": 2,
        "budget": budget,
        "research_gate": "V2.3 SSQ ADVANCE_COVERAGE_ONLY_SHADOW on exclude=200 holdout",
        "immutability_rule": "supersede_with_new_manifest_never_edit_in_place",
    }
    manifest = build_freeze_manifest(
        game="SSQ",
        target_issue=target,
        history_cutoff_issue=cutoff_issue,
        algorithm_version=algorithm_version,
        parameters=parameters,
        tickets=tickets,
        budget=budget,
        seed=None,
    )

    return {
        "schema_version": "ceway.v2.3.shadow-snapshot.1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_PROSPECTIVE_SHADOW",
        "production_enabled": False,
        "game": "SSQ",
        "history_cutoff": {
            "issue": cutoff_issue,
            "date": latest.get("date"),
            "history_count": len(history),
        },
        "target_issue": target,
        "budget": budget,
        "plan": {
            "mode": plan.get("mode"),
            "strategy": plan.get("strategy"),
            "generator_version": plan.get("generator_version"),
            "tickets": len(tickets),
            "items": tickets,
            "front_diversity": diversity_summary(ticket["front"] for ticket in tickets),
            "back_diversity": diversity_summary(ticket["back"] for ticket in tickets),
        },
        "freeze_manifest": manifest,
        "guardrail": (
            "This is a coverage-only prospective shadow. It is not a production recommendation, "
            "does not claim predictive ranking signal, and must not be edited after freeze."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze CEWAY V2.3 SSQ coverage-only prospective shadow")
    parser.add_argument("--target-issue", type=str, default=None)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "artifacts" / "ceway_v23_ssq_shadow.json",
    )
    args = parser.parse_args()

    if args.budget <= 0 or args.budget % 2:
        raise ValueError("budget must be a positive even integer")
    snapshot = build_shadow_snapshot(target_issue=args.target_issue, budget=args.budget)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": snapshot["status"],
        "cutoff_issue": snapshot["history_cutoff"]["issue"],
        "target_issue": snapshot["target_issue"],
        "tickets": snapshot["plan"]["tickets"],
        "sha256": snapshot["freeze_manifest"]["sha256"],
    }, ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
