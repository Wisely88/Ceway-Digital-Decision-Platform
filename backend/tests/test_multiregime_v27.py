from __future__ import annotations

import unittest

from multiregime_v25 import DLT
from multiregime_v27 import (
    COMBINATION_TRACK_WEIGHTS,
    MULTIREGIME_V27_VERSION,
    _scarcity_number_key,
    generate_multiregime_scarcity_combo_plan,
    review_scarcity_ranking,
)


def _fill_unique(values: list[int], target: int, pool: int, start: int) -> list[int]:
    result = list(dict.fromkeys(values))
    candidate = start
    while len(result) < target:
        number = ((candidate - 1) % pool) + 1
        if number not in result:
            result.append(number)
        candidate += 1
    return sorted(result)


def make_history(count: int = 80) -> list[dict]:
    rows = []
    for index in range(1, count + 1):
        front = _fill_unique([
            ((index * 3 + 0) % 35) + 1,
            ((index * 5 + 7) % 35) + 1,
            ((index * 7 + 11) % 35) + 1,
            ((index * 9 + 17) % 35) + 1,
            ((index * 11 + 23) % 35) + 1,
        ], 5, 35, index)
        back = _fill_unique([
            ((index * 2) % 12) + 1,
            ((index * 5 + 3) % 12) + 1,
        ], 2, 12, index + 7)
        rows.append({"issue": f"26{index:03d}", "front": front, "back": back})
    return rows


class MultiRegimeV27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.history = make_history(80)
        cls.plan = generate_multiregime_scarcity_combo_plan(cls.history, DLT, budget=20)

    def test_version_and_complete_track_quotas(self) -> None:
        self.assertEqual(self.plan["generator_version"], MULTIREGIME_V27_VERSION)
        self.assertFalse(self.plan["production_enabled"])
        self.assertEqual(self.plan["regime_parameters"]["combination_track_weights"], COMBINATION_TRACK_WEIGHTS)
        self.assertEqual(self.plan["track_diagnostics"]["selected_counts"], {"evidence": 5, "scarcity": 3, "neutral": 2})
        self.assertEqual(len(self.plan["items"]), 10)

    def test_scarcity_pool_has_frozen_deterministic_order(self) -> None:
        pool = self.plan["scarcity_analysis"]["front"]["pool"]
        self.assertEqual(len(pool), 12)
        self.assertEqual([row["track_pool_rank"] for row in pool], list(range(1, 13)))
        self.assertEqual(pool, sorted(pool, key=_scarcity_number_key))
        self.assertFalse(self.plan["scarcity_analysis"]["front"]["number_ordering"]["manual_selection"])

    def test_scarcity_full_combination_ranking_is_complete_and_ranked(self) -> None:
        section = self.plan["scarcity_analysis"]["front"]
        ranking = section["full_combination_ranking"]
        pool_numbers = {int(row["number"]) for row in section["pool"]}
        self.assertGreater(len(ranking), 0)
        self.assertEqual(len(ranking), section["combination_count_after_constraints"])
        self.assertEqual([row["track_rank"] for row in ranking], list(range(1, len(ranking) + 1)))
        self.assertEqual(ranking, sorted(ranking, key=lambda row: row["track_rank"]))
        for row in ranking:
            self.assertTrue(set(row["numbers"]).issubset(pool_numbers))
            self.assertEqual(sum(row["collision"]["profile"].values()), len(self.history))
            self.assertIn("average", row["track_quality"])
            self.assertIn("minimum", row["track_quality"])

    def test_review_replays_frozen_scarcity_ranking(self) -> None:
        top = self.plan["scarcity_analysis"]["front"]["full_combination_ranking"][0]
        back_top = self.plan["scarcity_analysis"]["back"]["full_combination_ranking"][0]
        review = review_scarcity_ranking(self.plan, top["numbers"], back_top["numbers"])
        self.assertEqual(review["front"]["exact_actual_combination_rank"], 1)
        self.assertEqual(review["back"]["exact_actual_combination_rank"], 1)
        self.assertEqual(review["front"]["best_matching_hits"], DLT.main_pick)
        self.assertIn("top10", review["front"]["rank_buckets"])
        self.assertIn("all", review["front"]["rank_buckets"])

    def test_cutoff_blocks_future_data_including_full_scarcity_ranking(self) -> None:
        cutoff = self.history[59]["issue"]
        base = generate_multiregime_scarcity_combo_plan(self.history[:60], DLT, budget=20, history_cutoff_issue=cutoff)
        future = generate_multiregime_scarcity_combo_plan(self.history, DLT, budget=20, history_cutoff_issue=cutoff)
        self.assertEqual(base["items"], future["items"])
        self.assertEqual(base["scarcity_analysis"], future["scarcity_analysis"])


if __name__ == "__main__":
    unittest.main()
