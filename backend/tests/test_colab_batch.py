from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_colab_batch.py"


class ColabBatchTests(unittest.TestCase):
    def test_writes_deterministic_backtest_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dlt.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--game",
                    "dlt",
                    "--periods",
                    "2",
                    "--window",
                    "30",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["game"], "dlt")
            self.assertEqual(payload["result"]["config"]["periods"], 2)
            self.assertIn(str(output), result.stdout)


if __name__ == "__main__":
    unittest.main()
