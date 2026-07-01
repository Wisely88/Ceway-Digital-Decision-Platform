#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import save_ssq_sync_run, ssq_data_status  # noqa: E402
from engine import parse_ssq_csv, save_ssq_history  # noqa: E402


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CSV_HEADER = ["issue", "date", "f1", "f2", "f3", "f4", "f5", "f6", "b1"]


def fetch_78500(timeout: int = 8) -> list[dict]:
    url = "https://www.78500.cn/tool/ssqdb.html"
    request = Request(
        url,
        data=b"r1=1",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": url,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode(response.headers.get_content_charset() or "gb2312", errors="replace")
    payload = json.loads(text)
    rows = []
    for item in payload:
        front = [int(number) for number in str(item[0]).split(",")]
        back = [int(item[1])]
        issue = str(item[2]).strip()
        if len(front) == 6 and len(set(front)) == 6 and all(1 <= number <= 33 for number in front) and 1 <= back[0] <= 16:
            rows.append({"issue": issue, "date": "", "front": sorted(front), "back": back})
    return sorted(rows, key=lambda row: row["issue"])


def read_csv_file(path: Path) -> list[dict]:
    return parse_ssq_csv(path.read_text(encoding="utf-8-sig")) if path.exists() else []


def merge_rows(current_rows: list[dict], incoming_rows: list[dict]) -> list[dict]:
    current = {row["issue"]: row for row in current_rows}
    merged = dict(current)
    for row in incoming_rows:
        previous = current.get(row["issue"])
        merged[row["issue"]] = {
            **row,
            "date": previous.get("date", "") if previous and previous.get("date") else row.get("date", ""),
        }
    return sorted(merged.values(), key=lambda row: row["issue"])


def rows_to_csv(rows: list[dict]) -> str:
    lines = [",".join(CSV_HEADER)]
    for row in sorted(rows, key=lambda item: item["issue"]):
        lines.append(",".join([row["issue"], row.get("date", ""), *[str(number) for number in row["front"]], str(row["back"][0])]))
    return "\n".join(lines) + "\n"


def write_csv_file(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        for row in sorted(rows, key=lambda item: item["issue"]):
            writer.writerow([row["issue"], row.get("date", ""), *row["front"], row["back"][0]])


def main() -> int:
    parser = argparse.ArgumentParser(description="更新双色球历史开奖数据到 SQLite")
    parser.add_argument("--source", choices=["78500", "csv"], default="78500")
    parser.add_argument("--csv", type=Path, help="本地 CSV 路径，source=csv 时必填")
    parser.add_argument("--mode", choices=["append", "replace"], default="append")
    parser.add_argument("--export-csv", type=Path, default=BACKEND_DIR / "data" / "ssq_history.csv")
    args = parser.parse_args()

    try:
        if args.source == "csv":
            if not args.csv:
                raise ValueError("source=csv 时必须传入 --csv")
            incoming_rows = read_csv_file(args.csv)
        else:
            incoming_rows = fetch_78500()

        current_rows = [] if args.mode == "replace" else read_csv_file(args.export_csv)
        final_rows = incoming_rows if args.mode == "replace" else merge_rows(current_rows, incoming_rows)
        csv_text = rows_to_csv(final_rows)
        save_ssq_history(csv_text, mode="replace")
        write_csv_file(args.export_csv, final_rows)
        save_ssq_sync_run(args.source, "ok", len(incoming_rows), len(final_rows), "同步完成")
        status = ssq_data_status()
        print(
            json.dumps(
                {
                    "status": "ok",
                    "source": args.source,
                    "fetched_rows": len(incoming_rows),
                    "imported_rows": len(final_rows),
                    "latest_issue": status["latest_issue"],
                    "quality": status["quality"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        save_ssq_sync_run(args.source, "failed", 0, 0, str(exc))
        print(json.dumps({"status": "failed", "source": args.source, "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
