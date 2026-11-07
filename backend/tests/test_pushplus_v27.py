from __future__ import annotations

import unittest

from multiregime_v25 import DLT
from multiregime_v27 import MULTIREGIME_V27_VERSION, generate_multiregime_scarcity_combo_plan
from pushplus_v27 import build_pushplus_payload, build_v27_prediction_digest
from tests.test_multiregime_v27 import make_history


class PushPlusV27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = generate_multiregime_scarcity_combo_plan(make_history(80), DLT, budget=20)
        cls.digest = build_v27_prediction_digest(cls.plan, target_issue="26081")

    def test_digest_contains_scarcity_pool_and_top10(self) -> None:
        self.assertEqual(self.digest["generator_version"], MULTIREGIME_V27_VERSION)
        self.assertEqual(len(self.digest["scarcity_pool"]), 12)
        self.assertEqual(len(self.digest["scarcity_top10"]), 10)
        self.assertIn("稀缺组合 Top10", self.digest["markdown"])
        self.assertIn("Evidence 5 / Scarcity 3 / Neutral 2", self.digest["markdown"])

    def test_pushplus_content_is_exact_digest_markdown(self) -> None:
        payload = build_pushplus_payload(self.digest, token="test-token")
        self.assertEqual(payload["content"], self.digest["markdown"])
        self.assertEqual(payload["template"], "markdown")
        self.assertNotIn("test-token", self.digest["markdown"])

    def test_renderer_rejects_non_v27_plan(self) -> None:
        invalid = dict(self.plan)
        invalid["generator_version"] = "multi-regime-collision-v2.6"
        with self.assertRaises(ValueError):
            build_v27_prediction_digest(invalid, target_issue="26081")


if __name__ == "__main__":
    unittest.main()
