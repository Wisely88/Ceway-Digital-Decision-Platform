from __future__ import annotations

import unittest

from pushplus_v25 import build_pushplus_payload, build_v25_prediction_digest


def make_plan() -> dict:
    table = []
    for number in range(1, 13):
        table.append({
            "number": number,
            "evidence_rank": number,
            "scarcity_rank": 13 - number,
            "neutral_rank": ((number + 5) % 12) + 1,
        })
    return {
        "generator_version": "multi-regime-exposure-v2.5",
        "algorithm_version": "CEWAY-FWD-DLT-multi-regime-exposure-v2.5",
        "history_cutoff_issue": "26098",
        "front_regime_table": table,
        "back_regime_table": table,
        "items": [
            {"front": [1, 3, 5, 7, 9], "back": [2, 11], "score": 50.0},
            {"front": [2, 4, 6, 8, 10], "back": [1, 12], "score": 49.0},
        ],
    }


class PushPlusV25Tests(unittest.TestCase):
    def test_pushplus_content_is_exact_shared_v25_markdown(self) -> None:
        digest = build_v25_prediction_digest(make_plan(), target_issue="26099")
        payload = build_pushplus_payload(digest, token="test-token")
        self.assertEqual(payload["content"], digest["markdown"])
        self.assertEqual(payload["template"], "markdown")
        self.assertEqual(payload["title"], "CEWAY V2.5 DLT 26099")
        self.assertIn("历史截止期：**26098**", payload["content"])
        self.assertIn("Evidence / Scarcity / Neutral = 50/30/20", payload["content"])
        self.assertIn("核心参考线：**01 03 05 07 09 + 02 11**", payload["content"])

    def test_topic_is_optional_and_token_is_not_embedded_in_digest(self) -> None:
        digest = build_v25_prediction_digest(make_plan(), target_issue="26099")
        self.assertNotIn("token", digest)
        payload = build_pushplus_payload(digest, token="test-token", topic="ceway")
        self.assertEqual(payload["topic"], "ceway")

    def test_non_v25_plan_is_rejected(self) -> None:
        plan = make_plan()
        plan["generator_version"] = "legacy"
        with self.assertRaises(ValueError):
            build_v25_prediction_digest(plan, target_issue="26099")


if __name__ == "__main__":
    unittest.main()
