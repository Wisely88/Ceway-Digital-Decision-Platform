from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import db  # noqa: E402
import engine  # noqa: E402


class CsvSqliteSyncTests(unittest.TestCase):
    def test_rebuilds_draw_tables_without_removing_saved_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original_db_path = db.DB_PATH
            original_dlt_path = engine.DATA_PATH
            original_ssq_path = engine.SSQ_DATA_PATH
            try:
                db.DB_PATH = root / "ceway.sqlite3"
                engine.DATA_PATH = root / "dlt.csv"
                engine.SSQ_DATA_PATH = root / "ssq.csv"
                engine.DATA_PATH.write_text(
                    "issue,date,f1,f2,f3,f4,f5,b1,b2\n"
                    "26001,2026-01-03,1,2,3,4,5,1,2\n",
                    encoding="utf-8",
                )
                engine.SSQ_DATA_PATH.write_text(
                    "issue,date,f1,f2,f3,f4,f5,f6,b1\n"
                    "2026001,2026-01-01,1,2,3,4,5,6,1\n",
                    encoding="utf-8",
                )
                db.save_dlt_record_db(
                    {
                        "id": "saved",
                        "saved_at": "2026-01-01T00:00:00Z",
                        "budget": 2,
                        "strategy": "balanced",
                        "latest_issue": "26001",
                        "plan": {"mode": "single"},
                    }
                )

                result = engine.sync_history_databases_from_csv()

                self.assertEqual(result["dlt"]["latest_issue"], "26001")
                self.assertEqual(result["ssq"]["latest_issue"], "2026001")
                with sqlite3.connect(db.DB_PATH) as connection:
                    self.assertEqual(connection.execute("select count(*) from dlt_draws").fetchone()[0], 1)
                    self.assertEqual(connection.execute("select count(*) from ssq_draws").fetchone()[0], 1)
                    self.assertEqual(connection.execute("select count(*) from dlt_recommendation_records").fetchone()[0], 1)
            finally:
                db.DB_PATH = original_db_path
                engine.DATA_PATH = original_dlt_path
                engine.SSQ_DATA_PATH = original_ssq_path


if __name__ == "__main__":
    unittest.main()
