from __future__ import annotations

import unittest

from multiregime_v25 import DLT
from multiregime_v28 import MULTIREGIME_V28_VERSION, generate_multiregime_cross_fusion_plan
from pushplus_v28 import build_pushplus_payload, build_v28_prediction_digest
from tests.test_multiregime_v27 import make_history


class PushPlusV28Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = generate_multiregime_cross_fusion_plan(make_history(80), DLT, budget=20)
        cls.digest = build_v28_prediction_digest(cls.plan, target_issue="26081")

    def test_digest_contains_fusion_pool_and_top10(self) -> None:
        self.assertEqual(self.digest["generator_version"], MULTIREGIME_V28_VERSION)
        self.assertEqual(len(self.digest["fusion_pool"]), 14)
        self.assertEqual(len(self.digest["fusion_top10"]), 10)
        self.assertIn("Fusion 完整组合 Top10", self.digest["markdown"])
        self.assertIn("Evidence 4 / Scarcity 2 / Neutral 2 / Fusion 2", self.digest["markdown"])

    def test_pushplus_content_is_exact_digest_markdown(self) -> None:
        payload = build_pushplus_payload(self.digest, token="test-token")
        self.assertEqual(payload["content"], self.digest["markdown"])
        self.assertEqual(payload["template"], "markdown")
        self.assertNotIn("test-token", self.digest["markdown"])

    def test_renderer_rejects_non_v28_plan(self) -> None:
        invalid = dict(self.plan)
        invalid["generator_version"] = "multi-regime-scarcity-combo-v2.7"
        with self.assertRaises(ValueError):
            build_v28_prediction_digest(invalid, target_issue="26081")


if __name__ == "__main__":
    unittest.main()
