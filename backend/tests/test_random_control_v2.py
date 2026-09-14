from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from random_control_v2 import robust_conditional_random_ticket, robust_structure_matched_random_plan  # noqa: E402
from research_v2 import SSQ, constraints_like_ticket, passes_constraints  # noqa: E402


class RobustRandomControlTests(unittest.TestCase):
    def test_enumeration_fallback_handles_narrow_ssq_structure(self) -> None:
        reference = [12, 23, 25, 27, 29, 31]
        zones = ((1, 11), (12, 22), (23, 33))
        constraints = constraints_like_ticket(reference, zones, sum_tolerance=0)
        ticket = robust_conditional_random_ticket(
            33,
            6,
            constraints,
            seed="narrow-ssq",
            rejection_attempts=1,
        )
        self.assertTrue(passes_constraints(ticket, constraints))

    def test_robust_structure_plan_keeps_ticket_count(self) -> None:
        reference_plan = {
            "mode": "single",
            "items": [
                {"front": [12, 23, 25, 27, 29, 31], "back": [15]},
                {"front": [1, 8, 14, 20, 26, 33], "back": [3]},
            ],
        }
        baseline = robust_structure_matched_random_plan(
            reference_plan,
            SSQ,
            seed="robust-plan",
            main_zones=((1, 11), (12, 22), (23, 33)),
            bonus_zones=((1, 8), (9, 16)),
            main_sum_tolerance=0,
            bonus_sum_tolerance=None,
        )
        self.assertEqual(baseline["tickets"], 2)
        self.assertEqual(baseline["baseline_type"], "conditional_random_v2_robust")


if __name__ == "__main__":
    unittest.main()
