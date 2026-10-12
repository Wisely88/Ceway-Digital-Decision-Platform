from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from research_v2 import build_freeze_manifest  # noqa: E402
from scripts.review_dlt_forward_shadow import evaluate_registry, frozen_plan  # noqa: E402


class ForwardShadowReviewTests(unittest.TestCase):
    def registry(self) -> dict:
        tickets = [
            {"front": [1, 2, 3, 4, 5], "back": [1, 2]},
            {"front": [6, 7, 8, 9, 10], "back": [3, 4]},
        ]
        manifest = build_freeze_manifest(
            game="dlt",
            target_issue="26092",
            history_cutoff_issue="26091",
            algorithm_version="CEWAY-FWD-DLT-fixed-window-100-exposure-v2.4",
            parameters={"budget": 4, "strategy": "balanced"},
            tickets=tickets,
            budget=4,
        )
        return {
            "game": "DLT",
            "candidate_version": "fixed-window-100-exposure-v2.4",
            "target_issue": "26092",
            "history_cutoff_issue": "26091",
            "freeze_manifest": manifest,
        }

    def test_pending_does_not_require_target_draw(self) -> None:
        result = evaluate_registry(
            self.registry(),
            [{"issue": "26091", "date": "2026-08-12", "front": [11, 12, 13, 14, 15], "back": [5, 6]}],
        )
        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(result["target_issue"], "26092")
        self.assertNotIn("best", result)

    def test_review_uses_frozen_ticket_and_keeps_integrity_valid(self) -> None:
        registry = self.registry()
        result = evaluate_registry(
            registry,
            [
                {"issue": "26091", "date": "2026-08-12", "front": [11, 12, 13, 14, 15], "back": [5, 6]},
                {"issue": "26092", "date": "2026-08-15", "front": [1, 2, 3, 20, 21], "back": [1, 8]},
            ],
        )
        self.assertEqual(result["status"], "REVIEWED")
        self.assertTrue(result["freeze_integrity"]["valid"])
        self.assertEqual(result["best"]["front_hits"], 3)
        self.assertEqual(result["best"]["back_hits"], 1)
        self.assertEqual(result["best"]["front"], [1, 2, 3, 4, 5])

    def test_reconstructed_plan_is_content_addressed(self) -> None:
        plan = frozen_plan(self.registry())
        self.assertEqual(plan["tickets"], 2)
        self.assertEqual(plan["items"][0]["front"], [1, 2, 3, 4, 5])
        self.assertTrue(plan["v2_research"]["freeze_manifest"]["sha256"])


if __name__ == "__main__":
    unittest.main()
