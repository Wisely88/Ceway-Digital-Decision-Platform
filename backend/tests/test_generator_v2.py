from __future__ import annotations

import sys
import unittest
from pathlib import Path
from statistics import mean


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from generator import generate_single, generate_ssq_single  # noqa: E402
from generator_v2 import (  # noqa: E402
    GENERATOR_EXPOSURE_VERSION,
    generate_dlt_coverage_single,
    generate_dlt_exposure_single,
    generate_ssq_coverage_single,
    generate_ssq_exposure_single,
)
from research_v2 import diversity_summary  # noqa: E402


def score_rows(max_number: int) -> list[dict]:
    return [
        {"number": number, "total_score": float(max_number - number + 1), "explanation": "test"}
        for number in range(1, max_number + 1)
    ]


def mean_selected_number(plan: dict) -> float:
    return mean(number for item in plan["items"] for number in item["front"])


class GeneratorV2Tests(unittest.TestCase):
    def test_dlt_coverage_generator_reduces_front_clustering(self) -> None:
        legacy = generate_single(20, score_rows(35), score_rows(12), "balanced")
        v2 = generate_dlt_coverage_single(20, score_rows(35), score_rows(12), "balanced")
        legacy_diversity = diversity_summary(item["front"] for item in legacy["items"])
        v2_diversity = diversity_summary(item["front"] for item in v2["items"])
        self.assertEqual(v2["tickets"], 10)
        self.assertEqual(v2["cost"], 20)
        self.assertLess(v2_diversity["mean_jaccard"], legacy_diversity["mean_jaccard"])
        self.assertLess(v2_diversity["max_jaccard"], legacy_diversity["max_jaccard"])
        self.assertEqual(len({tuple(item["front"]) for item in v2["items"]}), 10)

    def test_ssq_coverage_generator_reduces_front_clustering(self) -> None:
        legacy = generate_ssq_single(20, score_rows(33), score_rows(16), "balanced")
        v2 = generate_ssq_coverage_single(20, score_rows(33), score_rows(16), "balanced")
        legacy_diversity = diversity_summary(item["front"] for item in legacy["items"])
        v2_diversity = diversity_summary(item["front"] for item in v2["items"])
        self.assertEqual(v2["tickets"], 10)
        self.assertEqual(v2["cost"], 20)
        self.assertLess(v2_diversity["mean_jaccard"], legacy_diversity["mean_jaccard"])
        self.assertLess(v2_diversity["max_jaccard"], legacy_diversity["max_jaccard"])
        self.assertEqual(len({tuple(item["front"]) for item in v2["items"]}), 10)

    def test_dlt_exposure_generator_hits_structural_diversity_target_without_losing_score_bias(self) -> None:
        v1 = generate_dlt_coverage_single(20, score_rows(35), score_rows(12), "balanced")
        v21 = generate_dlt_exposure_single(20, score_rows(35), score_rows(12), "balanced")
        v1_diversity = diversity_summary(item["front"] for item in v1["items"])
        v21_diversity = diversity_summary(item["front"] for item in v21["items"])
        self.assertEqual(v21["generator_version"], GENERATOR_EXPOSURE_VERSION)
        self.assertEqual(v21["tickets"], 10)
        self.assertEqual(v21["cost"], 20)
        self.assertLess(v21_diversity["mean_jaccard"], v1_diversity["mean_jaccard"])
        self.assertLessEqual(v21_diversity["mean_jaccard"], 0.15)
        self.assertEqual(len({tuple(item["front"]) for item in v21["items"]}), 10)
        # On a monotonic synthetic scorer, the selected pool must remain clearly
        # biased toward the high-ranked half rather than becoming uniform-only.
        self.assertLess(mean_selected_number(v21), 15.0)

    def test_ssq_exposure_generator_hits_structural_diversity_target_without_losing_score_bias(self) -> None:
        v1 = generate_ssq_coverage_single(20, score_rows(33), score_rows(16), "balanced")
        v21 = generate_ssq_exposure_single(20, score_rows(33), score_rows(16), "balanced")
        v1_diversity = diversity_summary(item["front"] for item in v1["items"])
        v21_diversity = diversity_summary(item["front"] for item in v21["items"])
        self.assertEqual(v21["generator_version"], GENERATOR_EXPOSURE_VERSION)
        self.assertEqual(v21["tickets"], 10)
        self.assertEqual(v21["cost"], 20)
        self.assertLess(v21_diversity["mean_jaccard"], v1_diversity["mean_jaccard"])
        self.assertLessEqual(v21_diversity["mean_jaccard"], 0.18)
        self.assertEqual(len({tuple(item["front"]) for item in v21["items"]}), 10)
        self.assertLess(mean_selected_number(v21), 15.0)


if __name__ == "__main__":
    unittest.main()
