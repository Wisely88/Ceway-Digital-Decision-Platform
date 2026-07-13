from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from scripts.update_dlt_history import (
    expected_draw_date as expected_dlt_draw_date,
    merge_rows as merge_dlt_rows,
    parse_78500_payload,
)
from scripts.update_ssq_history import (
    expected_draw_date,
    fill_latest_new_draw_date,
    normalize_cwl_row,
)


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class DltSyncScheduleTests(unittest.TestCase):
    def test_parses_78500_post_payload_and_normalizes_issue(self):
        rows = parse_78500_payload(
            [["04,14,19,24,27", "06,07", "2026077"]]
        )
        self.assertEqual(rows[0]["issue"], "26077")
        self.assertEqual(rows[0]["front"], [4, 14, 19, 24, 27])
        self.assertEqual(rows[0]["back"], [6, 7])

    def test_preserves_existing_date_when_78500_has_no_date(self):
        current = [{"issue": "26077", "date": "2026-07-11", "front": [4, 14, 19, 24, 27], "back": [6, 7]}]
        incoming = [{"issue": "26077", "date": "", "front": [4, 14, 19, 24, 27], "back": [6, 7]}]
        self.assertEqual(merge_dlt_rows(current, incoming)[0]["date"], "2026-07-11")

    def test_uses_previous_dlt_draw_day_for_after_midnight_retry(self):
        now = datetime(2026, 7, 12, 0, 30, tzinfo=SHANGHAI_TZ)
        self.assertEqual(expected_dlt_draw_date(now), "2026-07-11")


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
