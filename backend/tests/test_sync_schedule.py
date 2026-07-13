from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from scripts.update_ssq_history import (
    expected_draw_date,
    fill_latest_new_draw_date,
    normalize_cwl_row,
)


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class SsqSyncScheduleTests(unittest.TestCase):
    def test_normalizes_official_cwl_result(self):
        row = normalize_cwl_row(
            {
                "code": "2026080",
                "date": "2026-07-14(二)",
                "red": "01,05,08,17,24,31",
                "blue": "09",
            }
        )
        self.assertEqual(row["issue"], "2026080")
        self.assertEqual(row["date"], "2026-07-14")
        self.assertEqual(row["front"], [1, 5, 8, 17, 24, 31])
        self.assertEqual(row["back"], [9])

    def test_uses_draw_day_for_late_evening_update(self):
        now = datetime(2026, 7, 14, 23, 30, tzinfo=SHANGHAI_TZ)
        self.assertEqual(expected_draw_date(now), "2026-07-14")

    def test_uses_previous_draw_day_for_after_midnight_retry(self):
        now = datetime(2026, 7, 15, 0, 30, tzinfo=SHANGHAI_TZ)
        self.assertEqual(expected_draw_date(now), "2026-07-14")

    def test_only_fills_the_latest_new_issue(self):
        current = [{"issue": "2026079", "date": "2026-07-12", "front": [], "back": []}]
        incoming = [
            {"issue": "2026079", "date": "", "front": [], "back": []},
            {"issue": "2026080", "date": "", "front": [], "back": []},
        ]
        now = datetime(2026, 7, 14, 23, 30, tzinfo=SHANGHAI_TZ)
        rows = fill_latest_new_draw_date(incoming, current, now)
        self.assertEqual(rows[-1]["date"], "2026-07-14")
        self.assertEqual(rows[0]["date"], "")


if __name__ == "__main__":
    unittest.main()
