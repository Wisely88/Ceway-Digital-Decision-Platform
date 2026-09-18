from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fixed_window_v24 import (  # noqa: E402
    FIXED_WINDOW_V24,
    FIXED_WINDOW_V24_VERSION,
    generate_dlt_fixed100_single,
    generate_ssq_fixed100_single,
)
from generator_v2 import generate_dlt_exposure_single, generate_ssq_exposure_single  # noqa: E402


def score_rows(max_number: int) -> list[dict]:
    return [
        {"number": number, "total_score": float(max_number - number + 1), "explanation": "test"}
        for number in range(1, max_number + 1)
    ]


def ticket_signature(plan: dict) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    return [
        (tuple(item["front"]), tuple(item["back"]))
        for item in plan.get("items", [])
    ]


class FixedWindowV24Tests(unittest.TestCase):
    def test_dlt_wrapper_changes_metadata_not_ticket_construction(self) -> None:
        front = score_rows(35)
        back = score_rows(12)
        v21 = generate_dlt_exposure_single(20, copy.deepcopy(front), copy.deepcopy(back), "balanced")
        v24 = generate_dlt_fixed100_single(20, copy.deepcopy(front), copy.deepcopy(back), "balanced")
        self.assertEqual(ticket_signature(v24), ticket_signature(v21))
        self.assertEqual(v24["score"], v21["score"])
        self.assertEqual(v24["generator_version"], FIXED_WINDOW_V24_VERSION)
        self.assertEqual(v24["scoring_window_diagnostics"]["fixed_window"], FIXED_WINDOW_V24)

    def test_ssq_wrapper_changes_metadata_not_ticket_construction(self) -> None:
        front = score_rows(33)
        back = score_rows(16)
        v21 = generate_ssq_exposure_single(20, copy.deepcopy(front), copy.deepcopy(back), "balanced")
        v24 = generate_ssq_fixed100_single(20, copy.deepcopy(front), copy.deepcopy(back), "balanced")
        self.assertEqual(ticket_signature(v24), ticket_signature(v21))
        self.assertEqual(v24["score"], v21["score"])
        self.assertEqual(v24["generator_version"], FIXED_WINDOW_V24_VERSION)
        self.assertEqual(v24["scoring_window_diagnostics"]["fixed_window"], FIXED_WINDOW_V24)


if __name__ == "__main__":
    unittest.main()
