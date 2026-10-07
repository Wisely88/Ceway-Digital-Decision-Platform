from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from consensus_v22 import (  # noqa: E402
    CONSENSUS_V22_VERSION,
    equal_rank_consensus,
    generate_dlt_consensus_exposure_single,
    generate_ssq_consensus_exposure_single,
)
from research_v2 import diversity_summary  # noqa: E402


def rows(scores: list[float]) -> list[dict]:
    return [
        {"number": index + 1, "total_score": float(score), "explanation": "test"}
        for index, score in enumerate(scores)
    ]


def monotonic_rows(max_number: int, offset: float = 0.0, scale: float = 1.0) -> list[dict]:
    return [
        {
            "number": number,
            "total_score": offset + scale * float(max_number - number + 1),
            "explanation": "test",
        }
        for number in range(1, max_number + 1)
    ]


class ConsensusV22Tests(unittest.TestCase):
    def test_rank_consensus_is_invariant_to_raw_score_scale(self) -> None:
        base = monotonic_rows(8)
        scaled = monotonic_rows(8, offset=1000.0, scale=37.0)
        compressed = monotonic_rows(8, offset=-5.0, scale=0.01)
        consensus = equal_rank_consensus([base, scaled, compressed])
        self.assertEqual([row["number"] for row in consensus], list(range(1, 9)))
        self.assertEqual(consensus[0]["source_ranks"], {"50": 1, "100": 1, "200": 1})

    def test_rank_consensus_rewards_cross_window_agreement(self) -> None:
        # Number 1 ranks 1st, 2nd, 1st; number 2 ranks 2nd, 1st, 2nd.
        # Equal-rank consensus should keep number 1 ahead without using raw-scale magnitude.
        t50 = rows([40, 30, 20, 10])
        t100 = rows([30, 40, 20, 10])
        t200 = rows([4000, 3000, 20, 10])
        consensus = equal_rank_consensus([t50, t100, t200])
        self.assertEqual(consensus[0]["number"], 1)
        self.assertEqual(consensus[1]["number"], 2)
        self.assertLessEqual(consensus[0]["rank_stddev"], consensus[1]["rank_stddev"])

    def test_dlt_consensus_wrapper_keeps_v21_structural_diversity(self) -> None:
        front = equal_rank_consensus([
            monotonic_rows(35),
            monotonic_rows(35, scale=3.0),
            monotonic_rows(35, offset=50.0, scale=0.5),
        ])
        back = equal_rank_consensus([
            monotonic_rows(12),
            monotonic_rows(12, scale=2.0),
            monotonic_rows(12, offset=7.0, scale=0.2),
        ])
        plan = generate_dlt_consensus_exposure_single(20, front, back, "balanced")
        diversity = diversity_summary(item["front"] for item in plan["items"])
        self.assertEqual(plan["generator_version"], CONSENSUS_V22_VERSION)
        self.assertEqual(plan["tickets"], 10)
        self.assertLessEqual(diversity["mean_jaccard"], 0.15)

    def test_ssq_consensus_wrapper_keeps_v21_structural_diversity(self) -> None:
        front = equal_rank_consensus([
            monotonic_rows(33),
            monotonic_rows(33, scale=3.0),
            monotonic_rows(33, offset=50.0, scale=0.5),
        ])
        back = equal_rank_consensus([
            monotonic_rows(16),
            monotonic_rows(16, scale=2.0),
            monotonic_rows(16, offset=7.0, scale=0.2),
        ])
        plan = generate_ssq_consensus_exposure_single(20, front, back, "balanced")
        diversity = diversity_summary(item["front"] for item in plan["items"])
        self.assertEqual(plan["generator_version"], CONSENSUS_V22_VERSION)
        self.assertEqual(plan["tickets"], 10)
        self.assertLessEqual(diversity["mean_jaccard"], 0.18)

    def test_consensus_rejects_mismatched_number_sets(self) -> None:
        with self.assertRaises(ValueError):
            equal_rank_consensus([rows([3, 2, 1]), rows([3, 2]), rows([3, 2, 1])])


if __name__ == "__main__":
    unittest.main()
