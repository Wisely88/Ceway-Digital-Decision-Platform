from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from research_v2 import (  # noqa: E402
    DLT,
    SSQ,
    TicketConstraints,
    bootstrap_mean_ci,
    build_freeze_manifest,
    collision_profile,
    combination_collision_audit,
    conditional_random_tickets,
    diversity_summary,
    expand_plan_tickets,
    history_through_issue,
    joint_collision_profile,
    odd_count,
    passes_constraints,
    structure_matched_random_plan,
    theoretical_collision_distribution,
    zone_counts,
)


class ResearchV2Tests(unittest.TestCase):
    def test_theoretical_collision_distributions_sum_to_one(self) -> None:
        for spec in (SSQ, DLT):
            probs = theoretical_collision_distribution(spec.main_pool, spec.main_pick)
            self.assertTrue(math.isclose(sum(probs.values()), 1.0, rel_tol=1e-12, abs_tol=1e-12))

    def test_history_cutoff_excludes_future_rows(self) -> None:
        history = [
            {"issue": "26090"},
            {"issue": "26091"},
            {"issue": "26092"},
        ]
        rows = history_through_issue(history, "26091")
        self.assertEqual([row["issue"] for row in rows], ["26090", "26091"])

    def test_collision_profiles_are_combination_level(self) -> None:
        candidate = [1, 2, 3, 4, 5, 6]
        history = [
            [1, 2, 7, 8, 9, 10],
            [1, 2, 3, 7, 8, 9],
            [7, 8, 9, 10, 11, 12],
        ]
        profile = collision_profile(candidate, history)
        self.assertEqual(profile[0], 1)
        self.assertEqual(profile[2], 1)
        self.assertEqual(profile[3], 1)

    def test_joint_collision_profile_tracks_main_and_bonus(self) -> None:
        history = [
            {"front": [1, 2, 10, 11, 12], "back": [1, 9]},
            {"front": [3, 4, 5, 20, 21], "back": [2, 8]},
        ]
        profile = joint_collision_profile([1, 2, 3, 4, 5], [1, 2], history)
        self.assertEqual(profile[(2, 1)], 1)
        self.assertEqual(profile[(3, 1)], 1)

    def test_combination_collision_audit_counts_all_ticket_draw_pairs(self) -> None:
        tickets = [
            {"front": [1, 2, 3, 4, 5], "back": [1, 2]},
            {"front": [6, 7, 8, 9, 10], "back": [3, 4]},
        ]
        history = [
            {"front": [1, 2, 10, 11, 12], "back": [1, 9]},
            {"front": [3, 4, 5, 20, 21], "back": [2, 8]},
            {"front": [6, 7, 8, 30, 31], "back": [3, 4]},
        ]
        audit = combination_collision_audit(tickets, history, DLT)
        self.assertEqual(audit["ticket_count"], 2)
        self.assertEqual(audit["history_count"], 3)
        self.assertEqual(audit["pair_count"], 6)
        self.assertEqual(sum(audit["front"]["observed"].values()), 6)
        self.assertEqual(sum(audit["back"]["observed"].values()), 6)
        self.assertEqual(sum(audit["joint_observed"].values()), 6)

    def test_conditional_random_respects_structure(self) -> None:
        constraints = TicketConstraints(
            zones=((1, 11), (12, 22), (23, 33)),
            allowed_zone_counts=((2, 2, 2),),
            allowed_odd_counts=(3,),
            sum_min=70,
            sum_max=130,
            max_consecutive_groups=1,
        )
        tickets = conditional_random_tickets(
            pool_size=33,
            pick_size=6,
            ticket_count=20,
            constraints=constraints,
            seed="ssq-2026094-v2",
        )
        self.assertEqual(len(tickets), 20)
        self.assertTrue(all(passes_constraints(ticket, constraints) for ticket in tickets))

    def test_expand_dantuo_plan_to_complete_tickets(self) -> None:
        plan = {
            "mode": "dantuo",
            "front_dan": [1, 2],
            "front_tuo": [3, 4, 5, 6],
            "back": [1, 2, 3],
        }
        tickets = expand_plan_tickets(plan, DLT)
        self.assertEqual(len(tickets), 12)
        self.assertTrue(all(len(ticket["front"]) == 5 for ticket in tickets))
        self.assertTrue(all(len(ticket["back"]) == 2 for ticket in tickets))

    def test_structure_matched_random_plan_matches_reference_shape(self) -> None:
        reference = {
            "mode": "single",
            "items": [
                {"front": [3, 8, 14, 24, 31], "back": [2, 9]},
                {"front": [5, 11, 17, 22, 34], "back": [5, 12]},
            ],
        }
        baseline = structure_matched_random_plan(
            reference,
            DLT,
            seed="shape-test",
            main_zones=((1, 12), (13, 24), (25, 35)),
            bonus_zones=((1, 6), (7, 12)),
            main_sum_tolerance=5,
            bonus_sum_tolerance=2,
        )
        self.assertEqual(baseline["baseline_type"], "conditional_random_v2")
        self.assertEqual(baseline["tickets"], 2)
        for source, generated in zip(reference["items"], baseline["items"]):
            self.assertEqual(
                zone_counts(source["front"], ((1, 12), (13, 24), (25, 35))),
                zone_counts(generated["front"], ((1, 12), (13, 24), (25, 35))),
            )
            self.assertEqual(odd_count(source["front"]), odd_count(generated["front"]))
            self.assertLessEqual(abs(sum(source["front"]) - sum(generated["front"])), 5)
            self.assertEqual(
                zone_counts(source["back"], ((1, 6), (7, 12))),
                zone_counts(generated["back"], ((1, 6), (7, 12))),
            )
            self.assertEqual(odd_count(source["back"]), odd_count(generated["back"]))
            self.assertLessEqual(abs(sum(source["back"]) - sum(generated["back"])), 2)

    def test_diversity_summary_reports_pair_count(self) -> None:
        tickets = [(1, 2, 3, 4, 5, 6), (1, 2, 7, 8, 9, 10), (11, 12, 13, 14, 15, 16)]
        summary = diversity_summary(tickets)
        self.assertEqual(summary["pair_count"], 3)
        self.assertGreaterEqual(summary["max_jaccard"], summary["mean_jaccard"])

    def test_bootstrap_interval_contains_sample_mean(self) -> None:
        result = bootstrap_mean_ci([1, 2, 3, 4, 5], samples=1000, seed=1)
        self.assertLessEqual(result["low"], result["mean"])
        self.assertGreaterEqual(result["high"], result["mean"])

    def test_freeze_manifest_is_deterministic_and_sensitive_to_tickets(self) -> None:
        common = dict(
            game="ssq",
            target_issue="2026094",
            history_cutoff_issue="2026093",
            algorithm_version="CEWAY-FWD-V2.0-dev2",
            parameters={"budget": 40, "strategy": "balanced"},
            budget=40,
            seed="2026094",
        )
        first = build_freeze_manifest(
            **common,
            tickets=[{"front": [5, 9, 13, 18, 24, 30], "back": [5]}],
        )
        second = build_freeze_manifest(
            **common,
            tickets=[{"front": [30, 24, 18, 13, 9, 5], "back": [5]}],
        )
        changed = build_freeze_manifest(
            **common,
            tickets=[{"front": [5, 9, 13, 18, 24, 31], "back": [5]}],
        )
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertNotEqual(first["sha256"], changed["sha256"])
        self.assertEqual(first["schema_version"], "ceway.freeze.v2")


if __name__ == "__main__":
    unittest.main()
