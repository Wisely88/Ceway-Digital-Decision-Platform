from __future__ import annotations

import unittest

from multiregime_v25 import DLT
from multiregime_v28 import (
    MULTIREGIME_V28_VERSION,
    _fusion_number_key,
    generate_multiregime_cross_fusion_plan,
    review_fusion_ranking,
)
from tests.test_multiregime_v27 import make_history


class MultiRegimeV28Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.history = make_history(80)
        cls.plan = generate_multiregime_cross_fusion_plan(cls.history, DLT, budget=20)

    def test_version_and_fixed_fusion_shadow_quota(self) -> None:
        self.assertEqual(self.plan["generator_version"], MULTIREGIME_V28_VERSION)
        self.assertFalse(self.plan["production_enabled"])
        self.assertEqual(self.plan["track_diagnostics"]["selected_counts"], {"evidence": 4, "scarcity": 2, "neutral": 2, "fusion": 2})
        self.assertEqual(len(self.plan["items"]), 10)
        self.assertEqual(self.plan["regime_parameters"]["fusion_share"], 0.20)

    def test_fusion_pool_is_deterministic_and_has_provenance(self) -> None:
        pool = self.plan["fusion_analysis"]["front"]["pool"]
        self.assertEqual(len(pool), 14)
        self.assertEqual([row["fusion_pool_rank"] for row in pool], list(range(1, 15)))
        self.assertEqual(pool, sorted(pool, key=_fusion_number_key))
        self.assertTrue(all("fusion_support_tracks" in row for row in pool))
        self.assertFalse(self.plan["fusion_analysis"]["front"]["number_ordering"]["manual_selection"])

    def test_fusion_full_combination_ranking_is_complete(self) -> None:
        section = self.plan["fusion_analysis"]["front"]
        ranking = section["full_combination_ranking"]
        pool_numbers = {int(row["number"]) for row in section["pool"]}
        self.assertGreater(len(ranking), 0)
        self.assertEqual(len(ranking), section["combination_count_after_constraints"])
        self.assertEqual([row["track_rank"] for row in ranking], list(range(1, len(ranking) + 1)))
        for row in ranking:
            self.assertTrue(set(row["numbers"]).issubset(pool_numbers))
            self.assertEqual(sum(row["collision"]["profile"].values()), len(self.history))
            self.assertIn("provenance_coverage", row["fusion_quality"])
            self.assertIn("consensus_strength", row["fusion_quality"])

    def test_review_replays_frozen_fusion_ranking(self) -> None:
        front_top = self.plan["fusion_analysis"]["front"]["full_combination_ranking"][0]
        back_top = self.plan["fusion_analysis"]["back"]["full_combination_ranking"][0]
        review = review_fusion_ranking(self.plan, front_top["numbers"], back_top["numbers"])
        self.assertEqual(review["front"]["exact_actual_combination_rank"], 1)
        self.assertEqual(review["back"]["exact_actual_combination_rank"], 1)
        self.assertEqual(review["front"]["best_matching_hits"], DLT.main_pick)
        self.assertIn("portfolio", review)
        self.assertIn("all_front_union_hit_count", review["portfolio"])

    def test_cutoff_blocks_future_data_including_fusion_ranking(self) -> None:
        cutoff = self.history[59]["issue"]
        base = generate_multiregime_cross_fusion_plan(self.history[:60], DLT, budget=20, history_cutoff_issue=cutoff)
        future = generate_multiregime_cross_fusion_plan(self.history, DLT, budget=20, history_cutoff_issue=cutoff)
        self.assertEqual(base["items"], future["items"])
        self.assertEqual(base["fusion_analysis"], future["fusion_analysis"])
        self.assertEqual(base["scarcity_analysis"], future["scarcity_analysis"])


if __name__ == "__main__":
    unittest.main()
