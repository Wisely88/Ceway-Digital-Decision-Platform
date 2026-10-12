from __future__ import annotations

import unittest

from multiregime_v25 import DLT
from multiregime_v26 import generate_multiregime_collision_plan
from pushplus_v26 import build_pushplus_payload, build_v26_prediction_digest
from tests.test_multiregime_v26 import make_history


class PushPlusV26Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = generate_multiregime_collision_plan(make_history(80), DLT, budget=20)
        cls.digest = build_v26_prediction_digest(cls.plan, target_issue="26081")

    def test_pushplus_content_is_exact_shared_v26_markdown(self) -> None:
        payload = build_pushplus_payload(self.digest, token="test-token")
        self.assertEqual(payload["content"], self.digest["markdown"])
        self.assertEqual(payload["template"], "markdown")
        self.assertEqual(payload["title"], "CEWAY V2.6 DLT 26081")

    def test_digest_uses_model_core_pool_and_core_reference(self) -> None:
        self.assertEqual(self.digest["core_pool"], self.plan["core_pool"])
        self.assertEqual(self.digest["core_reference"], self.plan["core_reference"])
        self.assertIn("核心线历史碰撞", self.digest["markdown"])
        self.assertIn("N0=", self.digest["markdown"])

    def test_token_is_not_embedded_in_digest_and_topic_is_optional(self) -> None:
        self.assertNotIn("test-token", self.digest["markdown"])
        payload = build_pushplus_payload(self.digest, token="test-token", topic="research")
        self.assertEqual(payload["topic"], "research")

    def test_v25_plan_is_rejected(self) -> None:
        invalid = dict(self.plan)
        invalid["generator_version"] = "multi-regime-exposure-v2.5"
        with self.assertRaises(ValueError):
            build_v26_prediction_digest(invalid, target_issue="26081")


if __name__ == "__main__":
    unittest.main()
