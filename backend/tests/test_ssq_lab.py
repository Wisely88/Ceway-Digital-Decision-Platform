from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from ssq_lab import analyze_tickets, generate_model, generate_random  # noqa: E402


HISTORY = [
    {"issue": "2026001", "date": "2026-01-01", "front": [1, 2, 3, 4, 5, 6], "back": [1]},
    {"issue": "2026002", "date": "2026-01-03", "front": [2, 4, 6, 8, 10, 12], "back": [2]},
    {"issue": "2026003", "date": "2026-01-05", "front": [3, 6, 9, 12, 15, 18], "back": [3]},
    {"issue": "2026004", "date": "2026-01-07", "front": [4, 8, 12, 16, 20, 24], "back": [4]},
]


class SsqLabTests(unittest.TestCase):
    def test_ssq_collision_counts_all_seven_positions(self) -> None:
        result = analyze_tickets(HISTORY, "2026004", {"mode": "all_history"}, [{"front": [1, 2, 3, 4, 5, 6], "back": [1]}])
        profile = result["tickets"][0]["collision"]
        self.assertEqual(profile["n_total_hits"][7], 1)
        self.assertEqual(sum(profile["n_total_hits"]), 4)
        self.assertEqual(profile["n_front_back"][6][1], 1)

    def test_ssq_random_is_valid_distinct_and_repeatable_with_seed(self) -> None:
        first = generate_random(HISTORY, target_issue="2026005", cutoff="2026004", count=5, seed=7)
        second = generate_random(HISTORY, target_issue="2026005", cutoff="2026004", count=5, seed=7)
        self.assertEqual(first["tickets"], second["tickets"])
        self.assertEqual(len({(tuple(ticket["front"]), tuple(ticket["back"])) for ticket in first["tickets"]}), 5)
        self.assertTrue(all(len(ticket["front"]) == 6 and len(ticket["back"]) == 1 for ticket in first["tickets"]))

    def test_ssq_model_uses_cutoff_and_returns_ranked_candidates(self) -> None:
        result = generate_model(
            HISTORY,
            target_issue="2026005",
            cutoff="2026004",
            window={"mode": "last_N", "count": 4},
            front_pool_size=8,
            back_pool_size=3,
            output_count=4,
        )
        self.assertEqual(result["history_cutoff_issue"], "2026004")
        self.assertEqual(result["total_bets"], 4)
        self.assertGreaterEqual(result["candidate_count"], 4)
        self.assertTrue(all(ticket["collision"]["history_draw_count"] == 4 for ticket in result["tickets"]))
