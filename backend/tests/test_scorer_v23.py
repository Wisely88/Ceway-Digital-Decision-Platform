from __future__ import annotations

import unittest

from scorer_v23 import (
    NEUTRAL_SCORE,
    SCORER_V23_VERSION,
    score_dlt_back_v23,
    score_dlt_front_v23,
    score_ssq_back_v23,
    score_ssq_front_v23,
)


def sample_rows(count: int) -> list[dict]:
    rows = []
    for number in range(1, count + 1):
        rows.append(
            {
                "number": number,
                "heat_score": float(number),
                "missing_score": float(100 - number),
                "balance_score": float((number % 5) * 10 + 50),
                "total_score": float(number * 2),
                "explanation": "legacy",
            }
        )
    return rows


class ScorerV23Tests(unittest.TestCase):
    def test_dlt_front_uses_balance_only(self):
        source = sample_rows(35)
        result = score_dlt_front_v23(source)
        by_number = {row["number"]: row for row in result}
        self.assertEqual(by_number[7]["total_score"], by_number[7]["balance_score"])
        self.assertEqual(by_number[7]["legacy_total_score"], 14.0)
        self.assertEqual(by_number[7]["scorer_version"], SCORER_V23_VERSION)

    def test_dlt_back_prunes_missing_and_uses_equal_heat_balance(self):
        source = sample_rows(12)
        result = score_dlt_back_v23(source)
        by_number = {row["number"]: row for row in result}
        expected = (by_number[4]["heat_score"] + by_number[4]["balance_score"]) / 2
        self.assertEqual(by_number[4]["total_score"], expected)
        source[3]["missing_score"] = 9999.0
        rerun = score_dlt_back_v23(source)
        self.assertEqual(
            {row["number"]: row["total_score"] for row in result},
            {row["number"]: row["total_score"] for row in rerun},
        )

    def test_ssq_front_is_fully_neutral(self):
        result = score_ssq_front_v23(sample_rows(33))
        self.assertEqual({row["total_score"] for row in result}, {NEUTRAL_SCORE})
        self.assertEqual([row["number"] for row in result], list(range(1, 34)))

    def test_ssq_back_is_fully_neutral(self):
        result = score_ssq_back_v23(sample_rows(16))
        self.assertEqual({row["total_score"] for row in result}, {NEUTRAL_SCORE})
        self.assertEqual([row["number"] for row in result], list(range(1, 17)))


if __name__ == "__main__":
    unittest.main()
