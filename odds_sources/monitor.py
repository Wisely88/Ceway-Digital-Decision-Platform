#!/usr/bin/env python3
"""Conservative registry health checks + optional authorized live odds feed.

Never treat HTTP 200, a cached match date, or inferred timestamps as verified live SP.
All unknown/blocking cases fail closed; nothing here bypasses access restrictions.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CST = ZoneInfo("Asia/Shanghai")
MARKET_KEYS = {
    "football_1x2": {"home", "draw", "away"},
    "football_handicap_1x2": {"home", "draw", "away"},
    "basketball_moneyline": {"home", "away"},
    "basketball_spread": {"home", "away"},
    "basketball_total": {"over", "under"},
}
LINE_REQUIRED = {"football_handicap_1x2", "basketball_spread", "basketball_total"}
PAGE_DATE = re.compile(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b")


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(text):
    if not isinstance(text, str) or not text:
        raise ValueError("missing timezone-aware timestamp")
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp without timezone")
    return dt.astimezone(timezone.utc)


def fetch(url, headers=None, timeout=12):
    req = Request(url, headers={
        "User-Agent": "ClawScoreSourceHealth/1.0 (public-documentation-check)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.5",
        **(headers or {}),
    })
    with urlopen(req, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.status, content_type, response.read(400_001)


def check_page(source, today, fetcher=fetch):
    record = {"id": source["id"], "url": source.get("url"), "reachability": "not_checked",
              "date_signal": "not_checked", "odds_freshness": "not_verified", "http_status": None}
    if not source.get("url"):
        record["reachability"] = "requires_configuration"
        return record
    try:
        code, ctype, raw = fetcher(source["url"])
        record["http_status"] = code
        if len(raw) > 400_000:
            record["reachability"] = "oversized_response"
            return record
        body = raw.decode("utf-8", "replace")
        if re.search(r"captcha|cloudflare|access denied|验证码|安全验证", body[:5000], re.I):
            record["reachability"] = "blocked_or_challenged"
            return record
        if code != 200:
            record["reachability"] = "http_error"
            return record
        record["reachability"] = "page_reachable"
        # A reachable third-party page can explicitly warn about its own sales pause.
        # Never infer an official Sporttery suspension from that third-party notice.
        if source["id"] == "zgzcw_basketball":
            plain = re.sub(r"\\s+", "", re.sub(r"<[^>]*>", " ", body))
            record["page_sales_notice"] = (
                "third_party_page_reports_paused"
                if "该彩种暂停销售" in plain else "not_detected"
            )
        dates = set()
        for match in PAGE_DATE.findall(body):
            try:
                dates.add(datetime.strptime(match.replace("/", "-"), "%Y-%m-%d").date())
            except ValueError:
                pass
        record["date_signal"] = "current_fixture_date_visible" if (today in dates or today + timedelta(days=1) in dates) else "no_current_fixture_date_detected"
        # Neither signal establishes that SP/handicap prices are actually current.
    except HTTPError as exc:
        record["http_status"] = exc.code
        record["reachability"] = "blocked_or_challenged" if exc.code in (401, 403, 429) else "http_error"
    except (URLError, TimeoutError, OSError) as exc:
        record["reachability"] = "request_failed"
        record["error_type"] = type(exc).__name__
    except Exception as exc:
        record["reachability"] = "request_failed"
        record["error_type"] = type(exc).__name__
    return record


def validate_quotes(payload, registry, now):
    """Only accept explicit provider timestamps, fixture identity, and complete market prices."""
    if not isinstance(payload, dict) or not isinstance(payload.get("quotes"), list):
        raise ValueError("expected JSON object with quotes list")
    feed_time = parse_time(payload.get("generated_at_utc"))
    if not timedelta(0) <= now - feed_time <= timedelta(minutes=45):
        raise ValueError("feed timestamp older than 45 minutes or in the future")
    known = {s["id"] for s in registry["sources"]}
    valid, rejected = [], []
    seen = set()
    for idx, q in enumerate(payload["quotes"]):
        try:
            if not isinstance(q, dict):
                raise ValueError("quote is not an object")
            sport, market = q["sport"], q["market"]
            if sport not in ("football", "basketball") or market not in MARKET_KEYS or not market.startswith(sport):
                raise ValueError("sport/market mismatch")
            source = q["source_id"]
            if source not in known:
                raise ValueError("unknown source id")
            quoted = parse_time(q.get("quoted_at_utc"))
            kickoff = parse_time(q.get("kickoff_utc"))
            if not timedelta(0) <= now - quoted <= timedelta(minutes=45):
                raise ValueError("stale or future quote")
            if not now - timedelta(minutes=5) <= kickoff <= now + timedelta(days=10):
                raise ValueError("fixture outside forward window")
            home, away = q["home_team"], q["away_team"]
            if not all(isinstance(t, str) and t.strip() for t in (home, away)) or home.strip() == away.strip():
                raise ValueError("invalid teams")
            fixture_id = q["fixture_id"]
            if not isinstance(fixture_id, str) or not fixture_id.strip():
                raise ValueError("missing fixture_id")
            selections = q["selection_odds"]
            if not isinstance(selections, dict) or set(selections) != MARKET_KEYS[market]:
                raise ValueError("missing/extra market outcomes")
            if any(type(x) not in (int, float) or not 1.01 <= x <= 1000 for x in selections.values()):
                raise ValueError("invalid SP/odds")
            line = q.get("line")
            if market in LINE_REQUIRED:
                if type(line) not in (int, float) or not -200 <= line <= 350:
                    raise ValueError("invalid signed home handicap/total line")
                if market == "football_handicap_1x2" and int(line) != line:
                    raise ValueError("football handicap must be an integer")
                if market == "basketball_total" and line <= 0:
                    raise ValueError("total line must be positive")
            elif line is not None:
                raise ValueError("unexpected line for no-handicap market")
            key = (source, fixture_id, market, line)
            if key in seen:
                raise ValueError("duplicate quote key")
            seen.add(key)
            valid.append({"source_id": source, "fixture_id": fixture_id, "sport": sport,
                          "market": market, "home_team": home.strip(), "away_team": away.strip(),
                          "kickoff_utc": iso(kickoff), "line": line, "selection_odds": selections,
                          "quoted_at_utc": iso(quoted), "captured_at_utc": iso(now),
                          "is_official_confirmed": False,
                          "provenance": "authorized_feed_claim_unverified_against_official"})
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"index": idx, "reason": str(exc)[:140]})
    return valid, rejected


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(mode, fetcher=fetch, now=None):
    now = now or utc_now()
    registry = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    if mode in ("health", "all"):
        today = now.astimezone(CST).date()
        results = [check_page(s, today, fetcher) for s in registry["sources"]]
        status = {"checked_at_utc": iso(now), "meaning": "availability only; quote freshness always unverified",
                  "sources": results}
        write_json(ROOT / "status/latest.json", status)
        print("Health:", {key: sum(r["reachability"] == key for r in results) for key in set(r["reachability"] for r in results)})
    if mode in ("feed", "all"):
        feed_url = os.getenv("ODDS_FEED_URL", "").strip()
        latest = {"checked_at_utc": iso(now), "status": "no_authorized_feed", "is_fresh": False,
                  "max_quote_age_minutes": 45, "quotes": [], "rejected_quotes": [],
                  "note": "No live Sporttery odds are implied by source health checks."}
        if feed_url:
            headers = {}
            if os.getenv("ODDS_FEED_BEARER"):
                headers["Authorization"] = "Bearer " + os.getenv("ODDS_FEED_BEARER")
            try:
                code, ctype, raw = fetcher(feed_url, headers=headers)
                if code != 200 or len(raw) > 400_000:
                    raise ValueError("feed HTTP status or payload length invalid")
                payload = json.loads(raw)
                valid, rejected = validate_quotes(payload, registry, now)
                latest.update(status="fresh_authorized_feed" if valid else "no_valid_quotes",
                              is_fresh=bool(valid), quotes=valid, rejected_quotes=rejected,
                              feed_generated_at_utc=iso(parse_time(payload["generated_at_utc"])))
            except (ValueError, TypeError, URLError, HTTPError, OSError) as exc:
                latest.update(status="feed_unavailable_or_invalid", error_type=type(exc).__name__)
        write_json(ROOT / "data/latest.json", latest)
        print("Feed:", latest["status"], "valid quotes:", len(latest["quotes"]))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("health", "feed", "all"), default="all")
    args = parser.parse_args()
    sys.exit(run(args.mode))
