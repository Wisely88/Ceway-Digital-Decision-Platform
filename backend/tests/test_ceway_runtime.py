from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import ceway_runtime  # noqa: E402
from ceway_runtime import get_runtime_recommendation, select_budget_dantuo  # noqa: E402


class CewayRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        ceway_runtime._PREVIEW_CACHE.clear()

    def test_dlt_budget_pick_is_valid_and_covers_top_candidate(self) -> None:
        payload = {
            "game": "dlt",
            "recommendations": [
                {"primary": [3, 10, 18, 24, 27], "secondary": [2, 5], "final_score": 0.90},
                {"primary": [3, 10, 22, 24, 27], "secondary": [2, 5], "final_score": 0.88},
                {"primary": [3, 10, 13, 23, 26], "secondary": [2, 5], "final_score": 0.86},
            ],
        }
        ticket = select_budget_dantuo(payload, 18, 24)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["cost"], 20)
        self.assertEqual(ticket["notes"], 10)
        self.assertIn(1, ticket["covered_indexes"])
        self.assertEqual(len(ticket["primary_dan"]), 2)
        self.assertEqual(len(ticket["primary_tuo"]), 5)

    def test_ssq_budget_pick_is_valid(self) -> None:
        payload = {
            "game": "ssq",
            "recommendations": [
                {"primary": [1, 3, 8, 12, 22, 31], "secondary": [9], "final_score": 0.91},
                {"primary": [1, 3, 8, 15, 24, 30], "secondary": [9], "final_score": 0.87},
            ],
        }
        ticket = select_budget_dantuo(payload, 18, 24)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["cost"], 20)
        self.assertEqual(ticket["notes"], 10)
        self.assertEqual(len(ticket["primary_dan"]), 3)
        self.assertEqual(len(ticket["primary_tuo"]), 5)

    def test_preview_is_cached_until_refresh(self) -> None:
        class FakeDb:
            def latest_draw(self, game):
                return SimpleNamespace(issue="2026094", draw_date="2026-08-11")

            def get_freeze(self, game, target_issue):
                return None

        class FakeApp:
            recommend_calls = 0

            def __init__(self, project_root):
                self.db = FakeDb()

            def recommend(self, game, target_issue, persist=False):
                FakeApp.recommend_calls += 1
                return {
                    "game": game,
                    "game_name": "双色球",
                    "target_issue": target_issue,
                    "recommendations": [],
                }

            def close(self):
                return None

        runtime = (
            FakeApp,
            {"ssq": SimpleNamespace(name="双色球")},
            lambda game, issue: "2026095",
        )
        with patch("ceway_runtime._load_runtime", return_value=runtime):
            first = get_runtime_recommendation("ssq")
            second = get_runtime_recommendation("ssq")
            refreshed = get_runtime_recommendation("ssq", refresh=True)

        self.assertEqual(FakeApp.recommend_calls, 2)
        self.assertEqual(first["runtime"]["mode"], "preview")
        self.assertFalse(second["runtime"]["refresh_requested"])
        self.assertTrue(refreshed["runtime"]["refresh_requested"])


if __name__ == "__main__":
    unittest.main()
