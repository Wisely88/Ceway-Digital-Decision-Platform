#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine import sync_history_databases_from_csv  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(sync_history_databases_from_csv(), ensure_ascii=False, indent=2))
