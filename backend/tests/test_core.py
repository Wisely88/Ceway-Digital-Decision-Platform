from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from capital import capital_state  # noqa: E402
from engine import calculate_trends, calculate_ssq_trends  # noqa: E402
from generator import generate_plans, generate_ssq_plans  # noqa: E402
from review import prize_label, review_plan, review_ssq_plan, ssq_prize_label  # noqa: E402
from prizes import prize_financials  # noqa: E402
from scorer import score_back_numbers, score_ssq_back_numbers  # noqa: E402


def score_rows(max_number: int) -> list[dict]:
    return [
        {
            "number": number,
            "total_score": float(max_number - number + 1),
            "explanation": f"号码 {number} 测试解释",
        }
        for number in range(1, max_number + 1)
    ]


class GeneratorTests(unittest.TestCase):
    def test_dlt_plans_respect_budget_and_ticket_cost(self) -> None:
        plans = generate_plans(20, "balanced", score_rows(35), score_rows(12))
        self.assertTrue(plans)
        for plan in plans:
            self.assertLessEqual(plan["cost"], 20)
            self.assertEqual(plan["cost"], plan["tickets"] * 2)

    def test_ssq_plans_respect_budget_and_ticket_cost(self) -> None:
        plans = generate_ssq_plans(30, "balanced", score_rows(33), score_rows(16))
        self.assertTrue(plans)
        for plan in plans:
            self.assertLessEqual(plan["cost"], 30)
            self.assertEqual(plan["cost"], plan["tickets"] * 2)

    def test_variants_change_recommended_numbers(self) -> None:
        first = generate_plans(20, "balanced", score_rows(35), score_rows(12), variant=0)[0]
        second = generate_plans(20, "balanced", score_rows(35), score_rows(12), variant=1)[0]
        first_numbers = first.get("front_dan", first.get("items", [{}])[0].get("front"))
        second_numbers = second.get("front_dan", second.get("items", [{}])[0].get("front"))
        self.assertNotEqual(first_numbers, second_numbers)

    def test_dlt_back_numbers_avoid_front_overlap_and_consecutive_pairs(self) -> None:
        plans = generate_plans(40, "balanced", score_rows(35), score_rows(12), variant=0)
        for plan in plans:
            if plan["mode"] == "dantuo":
                front_numbers = set(plan["front_dan"])
                backs = plan["back"]
                self.assertTrue(front_numbers.isdisjoint(backs))
                self.assertFalse(any(right - left == 1 for left, right in zip(backs, backs[1:])))
            else:
                for ticket in plan["items"]:
                    self.assertTrue(set(ticket["front"]).isdisjoint(ticket["back"]))
                    self.assertFalse(ticket["back"][1] - ticket["back"][0] == 1)


class BackScoreTests(unittest.TestCase):
    def test_dlt_back_scores_include_heat_missing_and_balance_formula(self) -> None:
        history = [
            {"issue": "26001", "date": "2026-01-01", "front": [1, 2, 3, 4, 5], "back": [1, 2]},
            {"issue": "26002", "date": "2026-01-03", "front": [6, 7, 8, 9, 10], "back": [2, 3]},
            {"issue": "26003", "date": "2026-01-05", "front": [11, 12, 13, 14, 15], "back": [3, 4]},
        ]
        trends = calculate_trends(history, window=3)
        rows = score_back_numbers(trends)

        self.assertEqual(len(trends["back_omissions"]), 12)
        self.assertEqual(len(rows), 12)
        self.assertTrue(all("heat_score" in row and "missing_score" in row and "balance_score" in row for row in rows))
        self.assertEqual(rows, sorted(rows, key=lambda row: (-row["total_score"], row["number"])))

    def test_ssq_blue_scores_use_the_same_explainable_formula(self) -> None:
        history = [
            {"issue": "2026001", "date": "2026-01-01", "front": [1, 2, 3, 4, 5, 6], "back": [1]},
            {"issue": "2026002", "date": "2026-01-03", "front": [7, 8, 9, 10, 11, 12], "back": [2]},
        ]
        trends = calculate_ssq_trends(history, window=2)
        rows = score_ssq_back_numbers(trends)

        self.assertEqual(len(trends["back_omissions"]), 16)
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(row["total_score"] == row["score"] for row in rows))


class CapitalTests(unittest.TestCase):
    def test_profit_allows_step_up(self) -> None:
        state = capital_state(last_prize=10, principal=1000, balance=1000, level_units=1)
        self.assertEqual(state["round_profit"], 8)
        self.assertEqual(state["next_level_units"], 2)

    def test_loss_resets_to_base_level(self) -> None:
        state = capital_state(last_prize=0, principal=1000, balance=1010, level_units=4)
        self.assertEqual(state["round_profit"], -8)
        self.assertEqual(state["next_level_units"], 1)


class ReviewTests(unittest.TestCase):
    def test_dlt_prize_level_boundaries(self) -> None:
        cases = {
            (5, 2): "一等奖",
            (5, 1): "二等奖",
            (5, 0): "三等奖",
            (4, 2): "四等奖",
            (4, 1): "五等奖",
            (3, 2): "六等奖",
            (4, 0): "七等奖",
            (3, 1): "八等奖",
            (2, 2): "八等奖",
            (3, 0): "九等奖",
            (2, 1): "九等奖",
            (1, 2): "九等奖",
            (0, 2): "九等奖",
            (2, 0): "未命中固定奖级",
        }
        for hits, expected in cases.items():
            with self.subTest(hits=hits):
                self.assertEqual(prize_label(*hits), expected)

    def test_ssq_prize_level_boundaries(self) -> None:
        cases = {
            (6, 1): "一等奖",
            (6, 0): "二等奖",
            (5, 1): "三等奖",
            (5, 0): "四等奖",
            (4, 1): "四等奖",
            (4, 0): "五等奖",
            (3, 1): "五等奖",
            (2, 1): "六等奖",
            (1, 1): "六等奖",
            (0, 1): "六等奖",
            (3, 0): "未命中固定奖级",
        }
        for hits, expected in cases.items():
            with self.subTest(hits=hits):
                self.assertEqual(ssq_prize_label(*hits), expected)

    def test_dlt_uses_seven_prize_levels_from_issue_26014(self) -> None:
        cases = {
            (5, 0): "三等奖",
            (4, 2): "三等奖",
            (4, 1): "四等奖",
            (4, 0): "五等奖",
            (3, 2): "五等奖",
            (3, 1): "六等奖",
            (2, 2): "六等奖",
            (0, 2): "七等奖",
        }
        for hits, expected in cases.items():
            with self.subTest(hits=hits):
                self.assertEqual(prize_label(*hits, issue="26014"), expected)

    def test_actual_prize_amount_produces_net_profit_and_roi(self) -> None:
        result = prize_financials(
            {"五等奖": 2, "七等奖": 1},
            {"prizes": {"五等奖": 150, "七等奖": 5}, "source": "官方接口"},
            20,
        )
        self.assertEqual(result["prize_amount"], 305)
        self.assertEqual(result["net_profit"], 285)
        self.assertEqual(result["roi"], 1425.0)
        self.assertTrue(result["prize_amount_complete"])

    def test_dlt_appended_prize_adds_official_additional_amount(self) -> None:
        result = prize_financials(
            {"五等奖": 2},
            {"prizes": {"五等奖": 200}, "additional_prizes": {"五等奖": 100}, "source": "官方接口"},
            6,
            appended=True,
        )
        self.assertEqual(result["prize_amount"], 600)
        self.assertEqual(result["net_profit"], 594)
        self.assertTrue(result["prize_amount_complete"])

    def test_dlt_dantuo_counts_every_expanded_winning_ticket(self) -> None:
        plan = {
            "mode": "dantuo",
            "front_dan": [1],
            "front_tuo": [2, 3, 4, 5, 6],
            "back": [1, 2],
            "tickets": 5,
            "cost": 10,
        }
        draw = {"issue": "26001", "date": "2026-01-01", "front": [1, 2, 3, 4, 5], "back": [1, 2]}

        result = review_plan(plan, draw)

        self.assertEqual(result["hit_tickets"], 5)
        self.assertEqual(result["prize_distribution"], {"一等奖": 1, "四等奖": 4})
        self.assertEqual(result["best"]["prize_label"], "一等奖")

    def test_ssq_dantuo_counts_every_expanded_winning_ticket(self) -> None:
        plan = {
            "mode": "dantuo",
            "front_dan": [1],
            "front_tuo": [2, 3, 4, 5, 6, 7],
            "back": [1, 2],
            "tickets": 12,
            "cost": 24,
        }
        draw = {"issue": "2026001", "date": "2026-01-01", "front": [1, 2, 3, 4, 5, 6], "back": [1]}

        result = review_ssq_plan(plan, draw)

        self.assertEqual(result["hit_tickets"], 12)
        self.assertEqual(
            result["prize_distribution"],
            {"一等奖": 1, "二等奖": 1, "三等奖": 5, "四等奖": 5},
        )
        self.assertEqual(result["best"]["prize_label"], "一等奖")


if __name__ == "__main__":
    unittest.main()
