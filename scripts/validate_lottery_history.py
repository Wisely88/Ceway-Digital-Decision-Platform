#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "backend" / "data"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def validate_file(
    path: Path,
    *,
    front_count: int,
    front_max: int,
    back_count: int,
    back_max: int,
    minimum_rows: int,
) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    if len(rows) < minimum_rows:
        raise ValueError(f"{path.name} 仅有 {len(rows)} 期，低于安全下限 {minimum_rows} 期")

    issues = [str(row.get("issue", "")).strip() for row in rows]
    if any(not issue.isdigit() for issue in issues):
        raise ValueError(f"{path.name} 存在非数字期号")
    if len(issues) != len(set(issues)):
        raise ValueError(f"{path.name} 存在重复期号")
    if issues != sorted(issues):
        raise ValueError(f"{path.name} 期号未按升序排列")

    for row in rows:
        front = [int(row[f"f{index}"]) for index in range(1, front_count + 1)]
        back = [int(row[f"b{index}"]) for index in range(1, back_count + 1)]
        if len(set(front)) != front_count or not all(1 <= number <= front_max for number in front):
            raise ValueError(f"{path.name} 第 {row['issue']} 期前区号码不合法")
        if len(set(back)) != back_count or not all(1 <= number <= back_max for number in back):
            raise ValueError(f"{path.name} 第 {row['issue']} 期后区号码不合法")

    latest = rows[-1]
    latest_date = str(latest.get("date", "")).strip()
    if not latest_date:
        raise ValueError(f"{path.name} 最新期号 {latest['issue']} 缺少开奖日期")
    parsed_latest_date = date.fromisoformat(latest_date)
    if parsed_latest_date > datetime.now(SHANGHAI_TZ).date():
        raise ValueError(f"{path.name} 最新开奖日期晚于当前日期")

    return {
        "file": path.name,
        "rows": len(rows),
        "first_issue": rows[0]["issue"],
        "latest_issue": latest["issue"],
        "latest_date": latest_date,
    }


def main() -> int:
    results = [
        validate_file(
            DATA_DIR / "dlt_history.csv",
            front_count=5,
            front_max=35,
            back_count=2,
            back_max=12,
            minimum_rows=2800,
        ),
        validate_file(
            DATA_DIR / "ssq_history.csv",
            front_count=6,
            front_max=33,
            back_count=1,
            back_max=16,
            minimum_rows=3400,
        ),
    ]
    print(json.dumps({"status": "ok", "datasets": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
