from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from freeze_v2 import attach_plan_v2_metadata, ensure_plan_v2_metadata, verify_plan_freeze  # noqa: E402
from research_v2 import DLT, SSQ  # noqa: E402


class FreezeV2Tests(unittest.TestCase):
    def test_attach_and_verify_dlt_plan(self) -> None:
        history = [
            {"issue": "26090", "date": "2026-08-10", "front": [3, 7, 12, 14, 26], "back": [5, 11]},
            {"issue": "26091", "date": "2026-08-12", "front": [5, 8, 17, 22, 31], "back": [2, 9]},
        ]
        plan = {
            "mode": "single",
            "cost": 4,
            "items": [
                {"front": [3, 11, 14, 24, 26], "back": [2, 5]},
                {"front": [5, 8, 17, 22, 31], "back": [2, 9]},
            ],
        }
        attach_plan_v2_metadata(
            plan,
            game="dlt",
            spec=DLT,
            history=history,
            history_cutoff_issue="26091",
            target_issue="26092",
            parameters={"budget": 4, "strategy": "balanced", "window": 100},
        )
        research = plan["v2_research"]
        self.assertEqual(research["status"], "frozen")
        self.assertEqual(research["history_cutoff_issue"], "26091")
        self.assertEqual(research["target_issue"], "26092")
        self.assertEqual(len(research["freeze_sha256"]), 64)
        self.assertGreater(research["collision_audit"]["pair_count"], 0)
        self.assertTrue(verify_plan_freeze(plan, DLT)["valid"])

    def test_ticket_mutation_breaks_integrity(self) -> None:
        history = [
            {"issue": "2026093", "date": "2026-08-13", "front": [5, 9, 13, 18, 24, 30], "back": [5]},
        ]
        plan = {
            "mode": "single",
            "cost": 2,
            "items": [{"front": [5, 9, 13, 18, 24, 30], "back": [5]}],
        }
        attach_plan_v2_metadata(
            plan,
            game="ssq",
            spec=SSQ,
            history=history,
            history_cutoff_issue="2026093",
            target_issue="2026094",
            parameters={"budget": 2, "strategy": "balanced"},
        )
        plan["items"][0]["front"][-1] = 31
        integrity = verify_plan_freeze(plan, SSQ)
        self.assertFalse(integrity["valid"])
        self.assertIn("tickets", integrity["reason"])

    def test_existing_invalid_manifest_is_rejected_instead_of_refrozen(self) -> None:
        history = [
            {"issue": "26091", "date": "2026-08-12", "front": [5, 8, 17, 22, 31], "back": [2, 9]},
        ]
        plan = {
            "mode": "single",
            "cost": 2,
            "items": [{"front": [3, 11, 14, 24, 26], "back": [2, 5]}],
        }
        attach_plan_v2_metadata(
            plan,
            game="dlt",
            spec=DLT,
            history=history,
            history_cutoff_issue="26091",
            target_issue="26092",
            parameters={"budget": 2, "strategy": "balanced"},
        )
        plan["v2_research"]["freeze_manifest"]["parameters"]["budget"] = 999
        with self.assertRaises(ValueError):
            ensure_plan_v2_metadata(
                plan,
                game="dlt",
                spec=DLT,
                history=history,
                history_cutoff_issue="26091",
                target_issue="26092",
                parameters={"budget": 2, "strategy": "balanced"},
            )


if __name__ == "__main__":
    unittest.main()
