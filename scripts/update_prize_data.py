#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from prizes import DLT_PRIZE_PATH, SSQ_PRIZE_PATH  # noqa: E402


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def fetch_json(url: str, referer: str, timeout: int = 12) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*", "Referer": referer})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace"))


def integer(value) -> int | None:
    text = re.sub(r"[^0-9-]", "", str(value or ""))
    if not text or text == "-":
        return None
    return int(text)


def normalize_dlt_prize(item: dict) -> tuple[str, dict] | None:
    issue = str(item.get("lotteryDrawNum") or "").strip()
    if not issue:
        return None
    prizes = {}
    for row in item.get("prizeLevelList") or []:
        label = str(row.get("prizeLevel") or "").strip()
        amount = integer(row.get("stakeAmountFormat") or row.get("stakeAmount"))
        if label and "追加" not in label and amount is not None and amount >= 0:
            prizes[label] = amount
    return issue, {
        "date": str(item.get("lotteryDrawTime") or "")[:10],
        "prizes": prizes,
        "sales": integer(item.get("totalSaleAmount")),
        "pool": integer(item.get("poolBalanceAfterdraw") or item.get("poolBalance")),
        "source": "中国体育彩票官方开奖接口",
    }


def dlt_page(page_no: int, page_size: int = 100) -> dict:
    params = urlencode({"gameNo": "85", "provinceId": "0", "pageSize": page_size, "isVerify": "1", "pageNo": page_no})
    return fetch_json(
        f"https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?{params}",
        "https://www.lottery.gov.cn/",
    )


def fetch_dlt(full: bool) -> dict[str, dict]:
    first = dlt_page(1)
    value = first.get("value") or {}
    pages = int(value.get("pages") or 1) if full else 1
    payloads = [first]
    if pages > 1:
        with ThreadPoolExecutor(max_workers=6) as executor:
            payloads.extend(executor.map(dlt_page, range(2, pages + 1)))
    issues = {}
    for payload in payloads:
        for item in (payload.get("value") or {}).get("list") or []:
            normalized = normalize_dlt_prize(item)
            if normalized:
                issues[normalized[0]] = normalized[1]
    return issues


def normalize_ssq_prize(item: dict) -> tuple[str, dict] | None:
    issue = str(item.get("code") or "").strip()
    if not issue:
        return None
    prizes = {}
    for row in item.get("prizegrades") or []:
        level = integer(row.get("type"))
        amount = integer(row.get("typemoney"))
        if level and 1 <= level <= 6 and amount is not None:
            prizes[f"{'一二三四五六'[level - 1]}等奖"] = amount
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", str(item.get("date") or ""))
    return issue, {
        "date": date_match.group(0) if date_match else "",
        "prizes": prizes,
        "sales": integer(item.get("sales")),
        "pool": integer(item.get("poolmoney")),
        "source": "中国福利彩票官方开奖接口",
    }


def ssq_page(page_no: int, page_size: int = 100) -> dict:
    params = urlencode(
        {
            "name": "ssq", "issueCount": "", "issueStart": "", "issueEnd": "", "dayStart": "", "dayEnd": "",
            "pageNo": page_no, "pageSize": page_size, "week": "", "systemType": "PC",
        }
    )
    return fetch_json(
        f"https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?{params}",
        "https://www.cwl.gov.cn/",
    )


def fetch_ssq(full: bool) -> dict[str, dict]:
    first = ssq_page(1)
    pages = int(first.get("pageNum") or 1) if full else 1
    payloads = [first]
    if pages > 1:
        with ThreadPoolExecutor(max_workers=6) as executor:
            payloads.extend(executor.map(ssq_page, range(2, pages + 1)))
    issues = {}
    for payload in payloads:
        for item in payload.get("result") or []:
            normalized = normalize_ssq_prize(item)
            if normalized:
                issues[normalized[0]] = normalized[1]
    return issues


def save_snapshot(path: Path, source: str, incoming: dict[str, dict]) -> int:
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8")).get("issues", {})
        except (OSError, json.JSONDecodeError):
            existing = {}
    issues = {**existing, **incoming}
    payload = {
        "source": source,
        "synced_at": datetime.now(SHANGHAI_TZ).isoformat(),
        "issues": dict(sorted(issues.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)
    return len(issues)


def main() -> int:
    parser = argparse.ArgumentParser(description="同步大乐透与双色球每期官方实际奖金")
    parser.add_argument("--game", choices=["dlt", "ssq", "all"], default="all")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    if args.game in {"dlt", "all"}:
        print(f"DLT 奖金数据：{save_snapshot(DLT_PRIZE_PATH, '中国体育彩票官方开奖接口', fetch_dlt(args.full))} 期")
    if args.game in {"ssq", "all"}:
        print(f"SSQ 奖金数据：{save_snapshot(SSQ_PRIZE_PATH, '中国福利彩票官方开奖接口', fetch_ssq(args.full))} 期")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
