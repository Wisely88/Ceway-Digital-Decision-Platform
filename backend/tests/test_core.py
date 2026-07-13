from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from capital import capital_state  # noqa: E402
from generator import generate_plans, generate_ssq_plans  # noqa: E402


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


class CapitalTests(unittest.TestCase):
    def test_profit_allows_step_up(self) -> None:
        state = capital_state(last_prize=10, principal=1000, balance=1000, level_units=1)
        self.assertEqual(state["round_profit"], 8)
        self.assertEqual(state["next_level_units"], 2)

    def test_loss_resets_to_base_level(self) -> None:
        state = capital_state(last_prize=0, principal=1000, balance=1010, level_units=4)
        self.assertEqual(state["round_profit"], -8)
        self.assertEqual(state["next_level_units"], 1)


if __name__ == "__main__":
    unittest.main()
