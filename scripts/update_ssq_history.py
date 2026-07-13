#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


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
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
SSQ_DRAW_WEEKDAYS = {1, 3, 6}


def fetch_text(url: str, timeout: int = 8, referer: str = "https://www.cwl.gov.cn/") -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Referer": referer,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return content.decode(charset, errors="replace")


def fetch_cwl_recent(limit: int = 50, timeout: int = 8) -> list[dict]:
    params = urlencode(
        {
            "name": "ssq",
            "issueCount": str(limit),
            "issueStart": "",
            "issueEnd": "",
            "dayStart": "",
            "dayEnd": "",
            "pageNo": "1",
            "pageSize": str(limit),
            "week": "",
            "systemType": "PC",
        }
    )
    url = f"https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?{params}"
    payload = json.loads(fetch_text(url, timeout=timeout))
    items = payload.get("result") or payload.get("data") or []
    rows = [normalize_cwl_row(item) for item in items]
    rows = [row for row in rows if row]
    if not rows:
        raise ValueError("中国福彩官方接口未返回可用的双色球开奖数据")
    return sorted(rows, key=lambda row: row["issue"])


def normalize_cwl_row(item: dict) -> dict | None:
    issue = str(item.get("code") or item.get("issue") or item.get("lotteryDrawNum") or "").strip()
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", str(item.get("date") or item.get("lotteryDrawTime") or ""))
    front = [int(number) for number in re.findall(r"\d+", str(item.get("red") or item.get("front") or ""))]
    back = [int(number) for number in re.findall(r"\d+", str(item.get("blue") or item.get("back") or ""))]
    if (
        not issue.isdigit()
        or len(front) != 6
        or len(set(front)) != 6
        or not all(1 <= number <= 33 for number in front)
        or len(back) != 1
        or not 1 <= back[0] <= 16
    ):
        return None
    return {
        "issue": issue,
        "date": date_match.group(0) if date_match else "",
        "front": sorted(front),
        "back": back,
    }


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


def expected_draw_date(now: datetime | None = None) -> str:
    local_now = now.astimezone(SHANGHAI_TZ) if now else datetime.now(SHANGHAI_TZ)
    candidate = local_now.date()
    if local_now.hour < 2:
        candidate -= timedelta(days=1)
    return candidate.isoformat() if candidate.weekday() in SSQ_DRAW_WEEKDAYS else ""


def fill_latest_new_draw_date(
    incoming_rows: list[dict],
    current_rows: list[dict],
    now: datetime | None = None,
) -> list[dict]:
    draw_date = expected_draw_date(now)
    if not draw_date:
        return incoming_rows
    current_issues = {row["issue"] for row in current_rows}
    new_rows = [row for row in incoming_rows if row["issue"] not in current_issues]
    if not new_rows:
        return incoming_rows
    latest_new_issue = max(row["issue"] for row in new_rows)
    return [
        {**row, "date": row.get("date") or draw_date}
        if row["issue"] == latest_new_issue
        else row
        for row in incoming_rows
    ]


def fetch_source(source: str) -> tuple[list[dict], str]:
    if source == "cwl":
        return fetch_cwl_recent(), "cwl"
    if source == "78500":
        return fetch_78500(), "78500"
    if source == "auto":
        errors = []
        for name, fetcher in (("cwl", fetch_cwl_recent), ("78500", fetch_78500)):
            try:
                return fetcher(), name
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{name}: {exc}")
        raise ValueError("双色球主数据源和备用数据源均更新失败；" + " | ".join(errors))
    raise ValueError(f"未知数据源：{source}")


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
    parser.add_argument("--source", choices=["auto", "cwl", "78500", "csv"], default="auto")
    parser.add_argument("--csv", type=Path, help="本地 CSV 路径，source=csv 时必填")
    parser.add_argument("--mode", choices=["append", "replace"], default="append")
    parser.add_argument("--export-csv", type=Path, default=BACKEND_DIR / "data" / "ssq_history.csv")
    args = parser.parse_args()

    try:
        actual_source = args.source
        if args.source == "csv":
            if not args.csv:
                raise ValueError("source=csv 时必须传入 --csv")
            incoming_rows = read_csv_file(args.csv)
        else:
            incoming_rows, actual_source = fetch_source(args.source)

        current_rows = [] if args.mode == "replace" else read_csv_file(args.export_csv)
        incoming_rows = fill_latest_new_draw_date(incoming_rows, current_rows)
        final_rows = incoming_rows if args.mode == "replace" else merge_rows(current_rows, incoming_rows)
        csv_text = rows_to_csv(final_rows)
        save_ssq_history(csv_text, mode="replace")
        write_csv_file(args.export_csv, final_rows)
        save_ssq_sync_run(actual_source, "ok", len(incoming_rows), len(final_rows), "同步完成")
        status = ssq_data_status()
        print(
            json.dumps(
                {
                    "status": "ok",
                    "source": actual_source,
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
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        save_ssq_sync_run(args.source, "failed", 0, 0, str(exc))
        print(json.dumps({"status": "failed", "source": args.source, "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
