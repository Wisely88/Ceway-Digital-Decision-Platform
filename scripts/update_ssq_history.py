#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from html import unescape
import json
import re
import sys
import time
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


def fetch_cwl_page(page_no: int, page_size: int, issue_count: str, timeout: int = 8) -> dict:
    params = urlencode(
        {
            "name": "ssq",
            "issueCount": issue_count,
            "issueStart": "",
            "issueEnd": "",
            "dayStart": "",
            "dayEnd": "",
            "pageNo": str(page_no),
            "pageSize": str(page_size),
            "week": "",
            "systemType": "PC",
        }
    )
    url = f"https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?{params}"
    return json.loads(fetch_text(url, timeout=timeout))


def fetch_cwl_recent(
    limit: int = 100,
    timeout: int = 8,
    all_pages: bool = False,
    max_pages: int | None = None,
) -> list[dict]:
    page_no = 1
    pages = 1
    rows = []
    issue_count = "" if all_pages else str(limit)
    while page_no <= pages:
        payload = fetch_cwl_page(page_no, limit, issue_count, timeout=timeout)
        items = payload.get("result") or payload.get("data") or []
        rows.extend(normalize_cwl_row(item) for item in items)
        pages = int(payload.get("pageNum") or 1) if all_pages else 1
        if max_pages and page_no >= max_pages:
            break
        page_no += 1
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


def parse_78500_year_html(text: str) -> list[dict]:
    rows = []
    pattern = re.compile(
        r"<tr[^>]*>.*?<td[^>]*>\s*(\d{7})\s*</td>\s*"
        r"<td[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</td>(.*?)</tr>",
        re.IGNORECASE | re.DOTALL,
    )
    for issue, draw_date, body in pattern.findall(unescape(text)):
        front = [int(number) for number in re.findall(r'class=["\']red["\'][^>]*>\s*(\d+)', body, re.IGNORECASE)]
        back = [int(number) for number in re.findall(r'class=["\']blue["\'][^>]*>\s*(\d+)', body, re.IGNORECASE)]
        if len(front) == 6 and len(set(front)) == 6 and len(back) == 1:
            rows.append({"issue": issue, "date": draw_date, "front": sorted(front), "back": back})
    return sorted(rows, key=lambda row: row["issue"])


def fetch_78500_year(year: int, timeout: int = 12) -> list[dict]:
    url = "https://kaijiang.78500.cn/ssq/"
    rows = []
    for start, end in ((1, 80), (81, 199)):
        form = urlencode(
            {
                "year": str(year),
                "action": "range",
                "startqi": f"{year}{start:03d}",
                "endqi": f"{year}{end:03d}",
            }
        ).encode()
        request = Request(
            url,
            data=form,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": url,
            },
        )
        with urlopen(request, timeout=timeout) as response:
            content = response.read()
            charset = response.headers.get_content_charset() or "gb18030"
            text = content.decode(charset, errors="replace")
        rows.extend(parse_78500_year_html(text))
    rows = sorted({row["issue"]: row for row in rows}.values(), key=lambda row: row["issue"])
    if not rows or any(not row["issue"].startswith(str(year)) for row in rows):
        raise ValueError(f"彩宝贝未返回 {year} 年可用的双色球归档数据")
    return rows


def parse_78500_issue_html(issue: str, text: str) -> dict:
    date_match = re.search(
        r'id=["\']endTime["\'][^>]*>\s*(\d{4})年(\d{2})月(\d{2})日',
        text,
        re.IGNORECASE,
    )
    if not date_match:
        date_match = re.search(
            r'class=["\']phase["\'][^>]*>\s*(\d{4})-(\d{2})-(\d{2})',
            text,
            re.IGNORECASE,
        )
    front = [
        int(number)
        for number in re.findall(
            r'class=["\'](?:rb_kj|c-red)["\'][^>]*>\s*(\d+)',
            text,
            re.IGNORECASE,
        )
    ]
    back = [
        int(number)
        for number in re.findall(
            r'class=["\'](?:b_kj|c-blue)["\'][^>]*>\s*(\d+)',
            text,
            re.IGNORECASE,
        )
    ]
    if not date_match or len(front) != 6 or len(set(front)) != 6 or not back:
        raise ValueError(f"彩宝贝双色球第 {issue} 期详情页格式不完整")
    year, month, day = date_match.groups()
    return {
        "issue": issue,
        "date": f"{year}-{month}-{day}",
        "front": sorted(front),
        "back": [back[0]],
    }


def fetch_78500_issue(issue: str, timeout: int = 10) -> dict:
    url = f"https://m.78500.cn/kaijiang/ssq/{issue}.html"
    for attempt in range(3):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": "https://m.78500.cn/kaijiang/ssq/",
                },
            )
            with urlopen(request, timeout=timeout) as response:
                content = response.read()
                charset = response.headers.get_content_charset() or "gb18030"
                text = content.decode(charset, errors="replace")
            break
        except HTTPError as exc:
            if exc.code != 403 or attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))
    return parse_78500_issue_html(issue, text)


def fetch_78500_issues(issues: list[str]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(fetch_78500_issue, issues))


def merge_verified_archive_dates(current_rows: list[dict], archive_rows: list[dict]) -> list[dict]:
    archive = {row["issue"]: row for row in archive_rows}
    merged = []
    for row in current_rows:
        archived = archive.get(row["issue"])
        if not archived:
            merged.append(row)
            continue
        if row["front"] != archived["front"] or row["back"] != archived["back"]:
            raise ValueError(f"双色球第 {row['issue']} 期归档号码与现有历史不一致")
        merged.append({**row, "date": row.get("date") or archived["date"]})
    return merged


def fill_bounded_schedule_dates(rows: list[dict]) -> list[dict]:
    filled = [dict(row) for row in rows]
    dated_indexes = [index for index, row in enumerate(filled) if row.get("date")]
    for left_index, right_index in zip(dated_indexes, dated_indexes[1:]):
        missing_count = right_index - left_index - 1
        if missing_count <= 0:
            continue
        left_date = datetime.fromisoformat(filled[left_index]["date"]).date()
        right_date = datetime.fromisoformat(filled[right_index]["date"]).date()
        candidate = left_date + timedelta(days=1)
        candidates = []
        while candidate < right_date:
            if candidate.weekday() in SSQ_DRAW_WEEKDAYS:
                candidates.append(candidate.isoformat())
            candidate += timedelta(days=1)
        if len(candidates) != missing_count:
            continue
        for offset, draw_date in enumerate(candidates, start=1):
            if not filled[left_index + offset].get("date"):
                filled[left_index + offset]["date"] = draw_date
    return filled


def fetch_78500_archive(start_year: int = 2003, end_year: int = 2012) -> list[dict]:
    rows = []
    for year in range(start_year, end_year + 1):
        rows.extend(fetch_78500_year(year))
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
    current_by_issue = {row["issue"]: row for row in current_rows}
    latest_current_issue = max(current_by_issue, default="")
    new_rows = sorted(
        [
            row
            for row in incoming_rows
            if row["issue"] not in current_by_issue
            or (row["issue"] == latest_current_issue and not current_by_issue[row["issue"]].get("date"))
        ],
        key=lambda row: row["issue"],
    )
    if not new_rows:
        return incoming_rows
    dated_current = [row for row in current_rows if row.get("date")]
    previous_date = (
        datetime.fromisoformat(max(dated_current, key=lambda row: row["issue"])["date"]).date()
        if dated_current
        else None
    )
    inferred_dates = {}
    for row in new_rows:
        if row.get("date"):
            previous_date = datetime.fromisoformat(row["date"]).date()
        elif previous_date:
            candidate = previous_date + timedelta(days=1)
            while candidate.weekday() not in SSQ_DRAW_WEEKDAYS:
                candidate += timedelta(days=1)
            inferred_dates[row["issue"]] = candidate.isoformat()
            previous_date = candidate
    if draw_date and len(new_rows) == 1 and new_rows[0]["issue"] not in inferred_dates:
        inferred_dates[new_rows[0]["issue"]] = draw_date
    return [
        {**row, "date": row.get("date") or inferred_dates.get(row["issue"], "")}
        for row in incoming_rows
    ]


def fetch_source(
    source: str,
    *,
    all_pages: bool = False,
    max_pages: int | None = None,
) -> tuple[list[dict], str]:
    if source == "cwl":
        return fetch_cwl_recent(all_pages=all_pages, max_pages=max_pages), "cwl"
    if source == "78500":
        return fetch_78500(), "78500"
    if source == "auto":
        errors = []
        for name, fetcher in (("cwl", lambda: fetch_cwl_recent(all_pages=all_pages, max_pages=max_pages)), ("78500", fetch_78500)):
            try:
                rows = fetcher()
                if name == "cwl" and all_pages:
                    rows = [*fetch_78500_archive(), *rows]
                    name = "cwl+78500-archive"
                elif name == "78500" and all_pages:
                    rows = [*fetch_78500_archive(), *rows]
                    name = "78500+archive"
                return rows, name
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
            "date": row.get("date", "") or (previous.get("date", "") if previous else ""),
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
        writer = csv.writer(file, lineterminator="\r\n")
        writer.writerow(CSV_HEADER)
        for row in sorted(rows, key=lambda item: item["issue"]):
            writer.writerow([row["issue"], row.get("date", ""), *row["front"], row["back"][0]])


def main() -> int:
    parser = argparse.ArgumentParser(description="更新双色球历史开奖数据到 SQLite")
    parser.add_argument("--source", choices=["auto", "cwl", "78500", "csv"], default="auto")
    parser.add_argument("--csv", type=Path, help="本地 CSV 路径，source=csv 时必填")
    parser.add_argument("--mode", choices=["append", "replace"], default="append")
    parser.add_argument("--all", action="store_true", help="从官方接口分页补齐可用的全部历史日期")
    parser.add_argument("--max-pages", type=int, help="调试用：限制官方接口最多抓取页数")
    parser.add_argument("--export-csv", type=Path, default=BACKEND_DIR / "data" / "ssq_history.csv")
    args = parser.parse_args()

    try:
        actual_source = args.source
        if args.source == "csv":
            if not args.csv:
                raise ValueError("source=csv 时必须传入 --csv")
            incoming_rows = read_csv_file(args.csv)
        else:
            incoming_rows, actual_source = fetch_source(
                args.source,
                all_pages=args.all,
                max_pages=args.max_pages,
            )

        current_rows = [] if args.mode == "replace" else read_csv_file(args.export_csv)
        if args.source == "auto" and args.all:
            verified_current = merge_verified_archive_dates(current_rows, incoming_rows)
            verified_current = fill_bounded_schedule_dates(verified_current)
            unresolved = [
                row["issue"]
                for row in verified_current
                if not row.get("date") and row["issue"] < "2013001"
            ]
            if unresolved:
                verified_current = merge_verified_archive_dates(
                    verified_current,
                    fetch_78500_issues(unresolved),
                )
            if any(not row.get("date") for row in verified_current):
                raise ValueError("双色球全量日期回填后仍存在空日期")
            incoming_rows = merge_rows(verified_current, incoming_rows)
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
