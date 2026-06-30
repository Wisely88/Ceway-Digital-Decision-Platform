#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import data_status, save_sync_run  # noqa: E402
from engine import parse_dlt_csv, save_dlt_history  # noqa: E402


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CSV_HEADER = ["issue", "date", "f1", "f2", "f3", "f4", "f5", "b1", "b2"]


def fetch_text(url: str, timeout: int = 12, encoding: str | None = None) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json,text/javascript,*/*",
            "Referer": "https://www.lottery.gov.cn/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read()
        charset = encoding or response.headers.get_content_charset() or "utf-8"
        return content.decode(charset, errors="replace")


def fetch_sporttery_recent(page_size: int = 100, all_pages: bool = False, max_pages: int | None = None) -> list[dict]:
    rows = []
    page_no = 1
    pages = 1
    while page_no <= pages:
        payload = fetch_sporttery_page(page_no=page_no, page_size=page_size)
        value = payload.get("value") or {}
        items = value.get("list") or value.get("rows") or []
        rows.extend(normalize_sporttery_row(item) for item in items)
        pages = int(value.get("pages") or 1)
        if not all_pages:
            break
        if max_pages and page_no >= max_pages:
            break
        page_no += 1
    return sorted(dedupe_rows(rows), key=lambda row: row["issue"])


def fetch_sporttery_page(page_no: int, page_size: int) -> dict:
    params = urlencode(
        {
            "gameNo": "85",
            "provinceId": "0",
            "pageSize": str(page_size),
            "isVerify": "1",
            "pageNo": str(page_no),
        }
    )
    url = f"https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?{params}"
    return json.loads(fetch_text(url))


def normalize_sporttery_row(item: dict) -> dict:
    issue = str(
        item.get("lotteryDrawNum")
        or item.get("drawNum")
        or item.get("term")
        or item.get("issue")
        or ""
    ).strip()
    date = str(
        item.get("lotteryDrawTime")
        or item.get("drawTime")
        or item.get("date")
        or ""
    ).strip()[:10]
    result = str(
        item.get("lotteryDrawResult")
        or item.get("drawResult")
        or item.get("result")
        or ""
    )
    numbers = [int(number) for number in re.findall(r"\d+", result)]
    if len(numbers) < 7:
        raise ValueError(f"无法解析官方接口开奖号码：{item}")
    return {
        "issue": issue,
        "date": date,
        "front": sorted(numbers[:5]),
        "back": sorted(numbers[5:7]),
    }


def fetch_78500_js() -> list[dict]:
    text = fetch_text("https://img.78500.cn/78500/tools/dlt/dltdb.js", timeout=12, encoding="gb2312")
    rows = []
    patterns = [
        re.compile(
            r"(?P<issue>\d{5,7})[^\d]{1,20}(?P<date>20\d{2}[-/]\d{1,2}[-/]\d{1,2})"
            r".{0,120}?(?P<n1>\d{1,2})[^\d]+(?P<n2>\d{1,2})[^\d]+(?P<n3>\d{1,2})"
            r"[^\d]+(?P<n4>\d{1,2})[^\d]+(?P<n5>\d{1,2})[^\d]+(?P<n6>\d{1,2})"
            r"[^\d]+(?P<n7>\d{1,2})",
            re.S,
        ),
        re.compile(
            r"(?P<issue>\d{5,7}).{0,80}?(?P<n1>\d{2})\s+(?P<n2>\d{2})\s+(?P<n3>\d{2})"
            r"\s+(?P<n4>\d{2})\s+(?P<n5>\d{2})\s*[+|,]\s*(?P<n6>\d{2})\s+(?P<n7>\d{2})",
            re.S,
        ),
    ]
    seen = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            issue = match.group("issue")
            if issue in seen:
                continue
            numbers = [int(match.group(f"n{index}")) for index in range(1, 8)]
            front = numbers[:5]
            back = numbers[5:7]
            if is_valid_dlt_numbers(front, back):
                rows.append(
                    {
                        "issue": issue,
                        "date": match.groupdict().get("date", ""),
                        "front": sorted(front),
                        "back": sorted(back),
                    }
                )
                seen.add(issue)
    if not rows:
        raise ValueError("78500 数据文件可访问，但未识别到稳定的开奖数据结构")
    return sorted(rows, key=lambda row: row["issue"])


def is_valid_dlt_numbers(front: list[int], back: list[int]) -> bool:
    return (
        len(front) == 5
        and len(back) == 2
        and len(set(front)) == 5
        and len(set(back)) == 2
        and all(1 <= number <= 35 for number in front)
        and all(1 <= number <= 12 for number in back)
    )


def rows_to_csv(rows: list[dict]) -> str:
    lines = [",".join(CSV_HEADER)]
    for row in sorted(rows, key=lambda item: item["issue"]):
        values = [
            row["issue"],
            row["date"],
            *[str(number) for number in row["front"]],
            *[str(number) for number in row["back"]],
        ]
        lines.append(",".join(values))
    return "\n".join(lines) + "\n"


def read_csv_file(path: Path) -> list[dict]:
    return parse_dlt_csv(path.read_text(encoding="utf-8-sig"))


def write_csv_file(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        for row in sorted(rows, key=lambda item: item["issue"]):
            writer.writerow([row["issue"], row["date"], *row["front"], *row["back"]])


def merge_rows(current_rows: list[dict], incoming_rows: list[dict]) -> list[dict]:
    merged = {row["issue"]: row for row in current_rows}
    for row in incoming_rows:
        merged[row["issue"]] = row
    return sorted(merged.values(), key=lambda row: row["issue"])


def dedupe_rows(rows: list[dict]) -> list[dict]:
    merged = {row["issue"]: row for row in rows}
    return list(merged.values())


def fetch_source(source: str, limit: int, all_pages: bool, max_pages: int | None) -> list[dict]:
    if source == "sporttery":
        return fetch_sporttery_recent(page_size=limit, all_pages=all_pages, max_pages=max_pages)
    if source == "78500":
        return fetch_78500_js()
    raise ValueError(f"未知数据源：{source}")


def main() -> int:
    parser = argparse.ArgumentParser(description="更新大乐透历史开奖数据到 SQLite")
    parser.add_argument("--source", choices=["sporttery", "78500", "csv"], default="sporttery")
    parser.add_argument("--csv", type=Path, help="本地 CSV 路径，source=csv 时必填")
    parser.add_argument("--mode", choices=["append", "replace"], default="append")
    parser.add_argument("--limit", type=int, default=100, help="官方接口最近多少期")
    parser.add_argument("--all", action="store_true", help="官方接口分页抓取全部历史数据")
    parser.add_argument("--max-pages", type=int, help="调试用：限制官方接口最多抓取页数")
    parser.add_argument("--export-csv", type=Path, default=BACKEND_DIR / "data" / "dlt_history.csv")
    args = parser.parse_args()

    source = args.source
    try:
        if source == "csv":
            if not args.csv:
                raise ValueError("source=csv 时必须传入 --csv")
            incoming_rows = read_csv_file(args.csv)
        else:
            incoming_rows = fetch_source(source, args.limit, args.all, args.max_pages)

        if args.mode == "replace":
            final_rows = incoming_rows
        else:
            current_rows = read_csv_file(args.export_csv) if args.export_csv.exists() else []
            final_rows = merge_rows(current_rows, incoming_rows)

        csv_text = rows_to_csv(final_rows)
        save_dlt_history(csv_text, mode="replace")
        write_csv_file(args.export_csv, final_rows)
        save_sync_run(source, "ok", len(incoming_rows), len(final_rows), "同步完成")
        status = data_status()
        print(
            json.dumps(
                {
                    "status": "ok",
                    "source": source,
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
        save_sync_run(source, "failed", 0, 0, str(exc))
        print(
            json.dumps(
                {
                    "status": "failed",
                    "source": source,
                    "message": str(exc),
                    "next_step": "改用 --source csv 导入可信历史开奖 CSV，或稍后重试网络数据源。",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
