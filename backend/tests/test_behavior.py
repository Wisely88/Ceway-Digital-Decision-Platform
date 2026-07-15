from datetime import datetime, timezone
import unittest

from behavior import build_behavior_profile


class BehaviorProfileTests(unittest.TestCase):
    def test_detects_escalation_and_market_warming(self) -> None:
        records = [
            {"saved_at": f"2026-07-0{index}T00:00:00+00:00", "plan": {"cost": cost, "mode": "dantuo"}}
            for index, cost in enumerate([10, 20, 40], start=1)
        ]
        snapshot = {
            "source": "官方接口",
            "issues": {
                str(index): {"sales": sales, "source": "官方接口"}
                for index, sales in enumerate([100, 100, 100, 100, 100, 120, 125, 130, 135, 140], start=1)
            },
        }
        result = build_behavior_profile(records, {"summary": {}}, snapshot, datetime(2026, 7, 10, tzinfo=timezone.utc))
        self.assertEqual(result["risk_level"], "中")
        self.assertEqual(result["metrics"]["escalation_count"], 1)
        self.assertEqual(result["market"]["label"], "参与升温")

    def test_empty_history_is_low_risk_and_explains_missing_market(self) -> None:
        result = build_behavior_profile([], {"summary": {}}, {"issues": {}})
        self.assertEqual(result["risk_level"], "低")
        self.assertFalse(result["market"]["available"])


if __name__ == "__main__":
    unittest.main()
