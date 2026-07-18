from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from scripts.update_dlt_history import (
    expected_draw_date as expected_dlt_draw_date,
    fill_latest_new_draw_date as fill_latest_new_dlt_draw_date,
    merge_rows as merge_dlt_rows,
    parse_78500_payload,
)
from scripts.run_draw_update import scheduled_game, write_run_status
from scripts.update_prize_data import normalize_dlt_prize, normalize_ssq_prize
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

    def test_infers_delayed_dlt_date_from_previous_draw(self):
        current = [{"issue": "26079", "date": "2026-07-15", "front": [], "back": []}]
        incoming = [{"issue": "26080", "date": "", "front": [], "back": []}]
        now = datetime(2026, 7, 19, 12, 0, tzinfo=SHANGHAI_TZ)
        rows = fill_latest_new_dlt_draw_date(incoming, current, now)
        self.assertEqual(rows[0]["date"], "2026-07-18")


class LocalAutomationScheduleTests(unittest.TestCase):
    def test_selects_dlt_on_monday_evening(self):
        now = datetime(2026, 7, 13, 22, 30, tzinfo=SHANGHAI_TZ)
        self.assertEqual(scheduled_game(now), "dlt")

    def test_after_midnight_retry_uses_previous_ssq_draw_day(self):
        now = datetime(2026, 7, 15, 0, 30, tzinfo=SHANGHAI_TZ)
        self.assertEqual(scheduled_game(now), "ssq")

    def test_skips_when_previous_day_has_no_supported_draw(self):
        now = datetime(2026, 7, 18, 0, 30, tzinfo=SHANGHAI_TZ)
        self.assertIsNone(scheduled_game(now))

    def test_persists_latest_automation_status_outside_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "status" / "latest.json"
            written = write_run_status("failed", "ssq", "测试失败通知", status_file=target)
            payload = json.loads(written.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["game"], "ssq")
        self.assertEqual(payload["message"], "测试失败通知")
        self.assertIn("updated_at", payload)
        self.assertEqual(payload["last_failure_message"], "测试失败通知")

    def test_skipped_run_does_not_hide_previous_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "status" / "latest.json"
            write_run_status("failed", "ssq", "数据源暂时不可用", status_file=target)
            written = write_run_status("skipped", "auto", "当前不是开奖检查时段", status_file=target)
            payload = json.loads(written.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["last_failure_message"], "数据源暂时不可用")
        self.assertIsNotNone(payload["last_failure_at"])

    def test_success_timestamp_survives_later_skipped_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "status" / "latest.json"
            write_run_status("ok", "dlt", "自动更新任务完成", status_file=target)
            written = write_run_status("skipped", "auto", "当前不是开奖检查时段", status_file=target)
            payload = json.loads(written.read_text(encoding="utf-8"))

        self.assertIsNotNone(payload["last_success_at"])


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

    def test_infers_delayed_ssq_date_from_previous_draw(self):
        current = [{"issue": "2026080", "date": "2026-07-14", "front": [], "back": []}]
        incoming = [{"issue": "2026081", "date": "", "front": [], "back": []}]
        now = datetime(2026, 7, 18, 12, 0, tzinfo=SHANGHAI_TZ)
        rows = fill_latest_new_draw_date(incoming, current, now)
        self.assertEqual(rows[0]["date"], "2026-07-16")


class PrizeSyncTests(unittest.TestCase):
    def test_normalizes_dlt_actual_prize_amounts(self):
        issue, row = normalize_dlt_prize(
            {
                "lotteryDrawNum": "26078",
                "lotteryDrawTime": "2026-07-13",
                "prizeLevelList": [
                    {"prizeLevel": "一等奖", "stakeAmountFormat": "8216073"},
                    {"prizeLevel": "一等奖(追加)", "stakeAmountFormat": "6572858"},
                    {"prizeLevel": "七等奖", "stakeAmountFormat": "5"},
                ],
            }
        )
        self.assertEqual(issue, "26078")
        self.assertEqual(row["prizes"], {"一等奖": 8216073, "七等奖": 5})
        self.assertEqual(row["additional_prizes"], {"一等奖": 6572858})

    def test_normalizes_ssq_actual_prize_amounts(self):
        issue, row = normalize_ssq_prize(
            {
                "code": "2026080",
                "date": "2026-07-14(二)",
                "prizegrades": [
                    {"type": 1, "typemoney": "7579965"},
                    {"type": 6, "typemoney": "5"},
                ],
            }
        )
        self.assertEqual(issue, "2026080")
        self.assertEqual(row["prizes"], {"一等奖": 7579965, "六等奖": 5})


if __name__ == "__main__":
    unittest.main()
