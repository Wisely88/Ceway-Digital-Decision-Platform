from __future__ import annotations

import csv
import json
from io import StringIO
from collections import Counter
from pathlib import Path

from db import (
    dlt_draw_count,
    latest_dlt_draws,
    load_dlt_draws,
    load_dlt_records_db,
    replace_dlt_draws,
    save_dlt_record_db,
    upsert_dlt_draws,
    ssq_draw_count,
    latest_ssq_draws,
    load_ssq_draws,
    load_ssq_records_db,
    replace_ssq_draws,
    save_ssq_record_db,
    upsert_ssq_draws,
)


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_PATH = BASE_DIR / "data" / "dlt_history.csv"
SSQ_DATA_PATH = BASE_DIR / "data" / "ssq_history.csv"
RECORDS_PATH = BASE_DIR / "data" / "dlt_records.json"
SCENES_PATH = ROOT_DIR / "config" / "scenes.json"
DLT_REQUIRED_COLUMNS = ["issue", "date", "f1", "f2", "f3", "f4", "f5", "b1", "b2"]
SSQ_REQUIRED_COLUMNS = ["issue", "date", "f1", "f2", "f3", "f4", "f5", "f6", "b1"]


def load_scenes() -> dict:
    with SCENES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_dlt_history() -> list[dict]:
    if dlt_draw_count() > 0:
        return load_dlt_draws()
    with DATA_PATH.open("r", encoding="utf-8") as file:
        rows = parse_dlt_csv(file.read())
    upsert_dlt_draws(rows)
    return rows


def parse_dlt_csv(csv_text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(csv_text.strip()))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")

    missing_columns = [column for column in DLT_REQUIRED_COLUMNS if column not in reader.fieldnames]
    if missing_columns:
        raise ValueError(f"CSV 缺少字段：{', '.join(missing_columns)}")

    rows = []
    seen_issues = set()
    for index, row in enumerate(reader, start=2):
        issue = row["issue"].strip()
        if not issue:
            raise ValueError(f"第 {index} 行 issue 为空")
        if issue in seen_issues:
            raise ValueError(f"第 {index} 行 issue 重复：{issue}")
        seen_issues.add(issue)

        front = [int(row[f"f{i}"]) for i in range(1, 6)]
        back = [int(row[f"b{i}"]) for i in range(1, 3)]
        if len(set(front)) != 5 or any(number < 1 or number > 35 for number in front):
            raise ValueError(f"第 {index} 行前区号码必须为 1-35 且不重复")
        if len(set(back)) != 2 or any(number < 1 or number > 12 for number in back):
            raise ValueError(f"第 {index} 行后区号码必须为 1-12 且不重复")

        rows.append(
            {
                "issue": issue,
                "date": row["date"].strip(),
                "front": sorted(front),
                "back": sorted(back),
            }
        )

    if not rows:
        raise ValueError("CSV 没有开奖数据")
    return rows


def save_dlt_history(csv_text: str, mode: str = "replace") -> int:
    rows = parse_dlt_csv(csv_text)
    if mode == "append":
        upsert_dlt_draws(rows)
    else:
        replace_dlt_draws(rows)
        DATA_PATH.write_text(csv_text.strip() + "\n", encoding="utf-8")
    return len(rows)


def load_dlt_records() -> list[dict]:
    try:
        records = load_dlt_records_db()
        if records:
            return records
    except Exception:
        return []
    if not RECORDS_PATH.exists():
        return []
    try:
        with RECORDS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return payload


def save_dlt_record(record: dict) -> list[dict]:
    return save_dlt_record_db(record)


def load_latest_dlt_draws(limit: int = 20) -> list[dict]:
    load_dlt_history()
    return latest_dlt_draws(limit=limit)


def ratio_label(left: int, total: int) -> str:
    return f"{left}:{total - left}"


def calculate_trends(history: list[dict], window: int = 100) -> dict:
    recent = history[-window:]
    front_numbers = range(1, 36)
    back_numbers = range(1, 13)
    front_flat = [number for row in recent for number in row["front"]]
    back_flat = [number for row in recent for number in row["back"]]
    front_counts = Counter(front_flat)
    back_counts = Counter(back_flat)

    omissions = {}
    for number in front_numbers:
        omissions[number] = len(history)
        for index, row in enumerate(reversed(history)):
            if number in row["front"]:
                omissions[number] = index
                break

    odd_even = Counter()
    big_small = Counter()
    sum_values = []
    for row in history:
        front = row["front"]
        odd_count = sum(1 for number in front if number % 2 == 1)
        small_count = sum(1 for number in front if number <= 17)
        odd_even[ratio_label(odd_count, 5)] += 1
        big_small[ratio_label(small_count, 5)] += 1
        sum_values.append(sum(front))

    hot_front = [
        {"number": number, "count": front_counts[number]}
        for number in sorted(front_numbers, key=lambda item: (-front_counts[item], item))
    ]
    hot_back = [
        {"number": number, "count": back_counts[number]}
        for number in sorted(back_numbers, key=lambda item: (-back_counts[item], item))
    ]

    return {
        "window": min(window, len(history)),
        "hot_front": hot_front,
        "hot_back": hot_back,
        "omissions": [{"number": number, "missing": omissions[number]} for number in front_numbers],
        "odd_even": [{"ratio": key, "count": odd_even[key]} for key in sorted(odd_even)],
        "big_small": [{"ratio": key, "count": big_small[key]} for key in sorted(big_small)],
        "sum_values": [
            {"issue": row["issue"], "value": sum(row["front"])} for row in history[-30:]
        ],
        "sum_range": {
            "min": min(sum_values) if sum_values else 0,
            "max": max(sum_values) if sum_values else 0,
            "avg": round(sum(sum_values) / len(sum_values), 2) if sum_values else 0,
        },
    }


def parse_ssq_csv(csv_text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(csv_text.strip()))
    if not reader.fieldnames:
        raise ValueError("SSQ CSV 缺少表头")

    missing_columns = [column for column in SSQ_REQUIRED_COLUMNS if column not in reader.fieldnames]
    if missing_columns:
        raise ValueError(f"SSQ CSV 缺少字段：{', '.join(missing_columns)}")

    rows = []
    seen_issues = set()
    for index, row in enumerate(reader, start=2):
        issue = row["issue"].strip()
        if not issue:
            raise ValueError(f"SSQ CSV 第 {index} 行 issue 为空")
        if issue in seen_issues:
            raise ValueError(f"SSQ CSV 第 {index} 行 issue 重复：{issue}")
        seen_issues.add(issue)

        front = [int(row[f"f{i}"]) for i in range(1, 7)]
        back = [int(row["b1"])]
        if len(set(front)) != 6 or any(number < 1 or number > 33 for number in front):
            raise ValueError(f"SSQ CSV 第 {index} 行红球必须为 1-33 且不重复")
        if back[0] < 1 or back[0] > 16:
            raise ValueError(f"SSQ CSV 第 {index} 行蓝球必须为 1-16")

        rows.append(
            {
                "issue": issue,
                "date": row["date"].strip(),
                "front": sorted(front),
                "back": sorted(back),
            }
        )

    if not rows:
        raise ValueError("SSQ CSV 没有开奖数据")
    return rows


def save_ssq_history(csv_text: str, mode: str = "replace") -> int:
    rows = parse_ssq_csv(csv_text)
    if mode == "append":
        upsert_ssq_draws(rows)
    else:
        replace_ssq_draws(rows)
        SSQ_DATA_PATH.write_text(csv_text.strip() + "\n", encoding="utf-8")
    return len(rows)


def load_ssq_history() -> list[dict]:
    if ssq_draw_count() > 0:
        return load_ssq_draws()
    if not SSQ_DATA_PATH.exists():
        return []
    with SSQ_DATA_PATH.open("r", encoding="utf-8") as file:
        rows = parse_ssq_csv(file.read())
    upsert_ssq_draws(rows)
    return rows


def load_ssq_records() -> list[dict]:
    try:
        records = load_ssq_records_db()
        if records:
            return records
    except Exception:
        return []
    return []


def save_ssq_record(record: dict) -> list[dict]:
    return save_ssq_record_db(record)


def load_latest_ssq_draws(limit: int = 20) -> list[dict]:
    load_ssq_history()
    return latest_ssq_draws(limit=limit)


def calculate_ssq_trends(history: list[dict], window: int = 100) -> dict:
    recent = history[-window:] if len(history) >= window else history
    front_numbers = range(1, 34)
    back_numbers = range(1, 17)
    front_flat = [number for row in recent for number in row["front"]]
    back_flat = [number for row in recent for number in row["back"]]
    front_counts = Counter(front_flat)
    back_counts = Counter(back_flat)

    omissions = {}
    for number in front_numbers:
        omissions[number] = len(history)
        for index, row in enumerate(reversed(history)):
            if number in row["front"]:
                omissions[number] = index
                break

    odd_even = Counter()
    big_small = Counter()
    sum_values = []
    for row in history:
        front = row["front"]
        odd_count = sum(1 for number in front if number % 2 == 1)
        small_count = sum(1 for number in front if number <= 16)
        odd_even[ratio_label(odd_count, 6)] += 1
        big_small[ratio_label(small_count, 6)] += 1
        sum_values.append(sum(front))

    hot_front = [
        {"number": number, "count": front_counts[number]}
        for number in sorted(front_numbers, key=lambda item: (-front_counts[item], item))
    ]
    hot_back = [
        {"number": number, "count": back_counts[number]}
        for number in sorted(back_numbers, key=lambda item: (-back_counts[item], item))
    ]

    return {
        "window": min(window, len(history)),
        "hot_front": hot_front,
        "hot_back": hot_back,
        "omissions": [{"number": number, "missing": omissions[number]} for number in front_numbers],
        "odd_even": [{"ratio": key, "count": odd_even[key]} for key in sorted(odd_even)],
        "big_small": [{"ratio": key, "count": big_small[key]} for key in sorted(big_small)],
        "sum_values": [
            {"issue": row["issue"], "value": sum(row["front"])} for row in history[-30:]
        ],
        "sum_range": {
            "min": min(sum_values) if sum_values else 0,
            "max": max(sum_values) if sum_values else 0,
            "avg": round(sum(sum_values) / len(sum_values), 2) if sum_values else 0,
        },
    }
