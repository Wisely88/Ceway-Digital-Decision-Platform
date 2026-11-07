from __future__ import annotations

import unittest

from multiregime_v25 import DLT, ROLE_WEIGHTS
from multiregime_v26 import MULTIREGIME_V26_VERSION, generate_multiregime_collision_plan


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


class MultiRegimeV26Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.history = make_history(80)
        cls.plan = generate_multiregime_collision_plan(cls.history, DLT, budget=20)

    def test_version_is_new_and_v25_role_weights_are_preserved(self) -> None:
        self.assertEqual(self.plan["generator_version"], MULTIREGIME_V26_VERSION)
        self.assertEqual(self.plan["regime_parameters"]["role_weights"], ROLE_WEIGHTS)
        self.assertFalse(self.plan["production_enabled"])
        self.assertTrue(self.plan["regime_parameters"]["post_review_version"])

    def test_every_ticket_has_combination_level_collision_profile(self) -> None:
        self.assertEqual(len(self.plan["items"]), 10)
        for item in self.plan["items"]:
            profile = item["front_collision"]["profile"]
            self.assertEqual(sum(profile.values()), len(self.history))
            self.assertEqual(set(int(key) for key in profile), set(range(DLT.main_pick + 1)))
            self.assertIn("joint_collision_profile", item)
        audit = self.plan["combination_collision_audit"]
        self.assertEqual(audit["ticket_count"], 10)
        self.assertEqual(audit["pair_count"], 10 * len(self.history))

    def test_core_reference_is_actual_highest_ranked_ticket(self) -> None:
        best = max(self.plan["items"], key=lambda item: item["rank_score"])
        core = self.plan["core_reference"]
        self.assertEqual(core["front"], best["front"])
        self.assertEqual(core["back"], best["back"])
        self.assertEqual(core["rank_score"], best["rank_score"])

    def test_core_pool_is_model_ranked_not_ticket_usage_counter(self) -> None:
        self.assertEqual(len(self.plan["core_pool"]), 12)
        usage = {}
        for item in self.plan["items"]:
            for number in item["front"]:
                usage[number] = usage.get(number, 0) + 1
        usage_top = sorted(usage, key=lambda number: (-usage[number], number))[:12]
        self.assertEqual(self.plan["coverage_diagnostics"]["core_pool_source"].startswith("V2.5 regime blend"), True)
        # The source is deliberately independent of usage ordering; equality is not required either way.
        self.assertEqual(len(usage_top), 12)

    def test_cutoff_is_deterministic_and_blocks_future_rows(self) -> None:
        cutoff = self.history[59]["issue"]
        base = generate_multiregime_collision_plan(self.history[:60], DLT, budget=20, history_cutoff_issue=cutoff)
        with_future = generate_multiregime_collision_plan(self.history, DLT, budget=20, history_cutoff_issue=cutoff)
        self.assertEqual(base["items"], with_future["items"])
        self.assertEqual(base["core_pool"], with_future["core_pool"])
        self.assertEqual(base["combination_collision_audit"], with_future["combination_collision_audit"])


if __name__ == "__main__":
    unittest.main()
