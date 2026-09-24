#!/usr/bin/env python3
"""Fail-closed reader for the GitHub odds snapshot used before football/basketball predictions.

GitHub stores a captured feed snapshot, not a continuously live market. A valid result
means the snapshot is recently captured and internally well-formed; it does NOT prove
that the source is an officially authenticated Sporttery feed.
"""
import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from monitor import LINE_REQUIRED, MARKET_KEYS, iso, parse_time, utc_now

RAW_LATEST = (
    "https://raw.githubusercontent.com/Wisely88/"
    "Ceway-Digital-Decision-Platform/main/odds_sources/data/latest.json"
)
MAX_AGE = timedelta(minutes=45)


def recent(ts, now):
    try:
        return timedelta(0) <= now - parse_time(ts) <= MAX_AGE
    except (ValueError, TypeError, OverflowError):
        return False


def usable_quotes(snapshot, now=None, *, sport=None, market=None, fixture_id=None,
                  home_team=None, away_team=None):
    """Return conservative, prediction-ready quotes plus a machine-readable status."""
    now = now or utc_now()
    result = {"status": "invalid_snapshot", "is_fresh": False, "checked_at_utc": None,
              "used_at_utc": iso(now), "quotes": [], "reason": ""}
    if not isinstance(snapshot, dict):
        result["reason"] = "snapshot_not_object"
        return result
    result["checked_at_utc"] = snapshot.get("checked_at_utc")
    if snapshot.get("status") != "fresh_authorized_feed" or snapshot.get("is_fresh") is not True:
        result.update(status="no_live_feed", reason=snapshot.get("status", "unverified_snapshot"))
        return result
    if not recent(snapshot.get("checked_at_utc"), now) or not recent(
        snapshot.get("feed_generated_at_utc"), now
    ):
        result.update(status="stale_snapshot", reason="capture_or_feed_outside_45_min")
        return result
    quotes = snapshot.get("quotes")
    if not isinstance(quotes, list):
        result["reason"] = "quotes_not_list"
        return result
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        try:
            quote_sport, quote_market = quote["sport"], quote["market"]
            if quote_sport not in ("football", "basketball"):
                continue
            if quote_market not in MARKET_KEYS or not quote_market.startswith(quote_sport):
                continue
            if sport and quote_sport != sport:
                continue
            if market and quote_market != market:
                continue
            if fixture_id and quote.get("fixture_id") != fixture_id:
                continue
            if home_team and quote.get("home_team", "").strip() != home_team.strip():
                continue
            if away_team and quote.get("away_team", "").strip() != away_team.strip():
                continue
            if not recent(quote.get("quoted_at_utc"), now) or not recent(
                quote.get("captured_at_utc"), now
            ):
                continue
            if parse_time(quote["kickoff_utc"]) <= now:
                continue
            if not all(isinstance(quote.get(key), str) and quote[key].strip()
                       for key in ("source_id", "fixture_id", "home_team", "away_team")):
                continue
            if quote["home_team"].strip() == quote["away_team"].strip():
                continue
            selections = quote["selection_odds"]
            if not isinstance(selections, dict) or set(selections) != MARKET_KEYS[quote_market]:
                continue
            if any(type(v) not in (int, float) or not 1.01 <= v <= 1000
                   for v in selections.values()):
                continue
            line = quote.get("line")
            if quote_market in LINE_REQUIRED:
                if type(line) not in (int, float) or not -200 <= line <= 350:
                    continue
                if quote_market == "football_handicap_1x2" and int(line) != line:
                    continue
                if quote_market == "basketball_total" and line <= 0:
                    continue
            elif line is not None:
                continue
            result["quotes"].append(quote)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    result.update(status="fresh_quotes" if result["quotes"] else "no_matching_fresh_quotes",
                  is_fresh=bool(result["quotes"]),
                  reason="" if result["quotes"] else "no_pre_match_quote_passed_filters")
    return result


def fetch_snapshot(url=RAW_LATEST):
    request = Request(url, headers={"Accept": "application/json",
                                    "Cache-Control": "no-cache",
                                    "User-Agent": "Ceway-Prediction-Reader/1.0"})
    with urlopen(request, timeout=12) as response:
        payload = response.read(1_000_001)
        if len(payload) > 1_000_000:
            raise ValueError("snapshot_too_large")
        return json.loads(payload)


def main():
    parser = argparse.ArgumentParser(description="Read verified-fresh GitHub odds snapshot.")
    parser.add_argument("--snapshot", type=Path, help="Optional local JSON file for offline checks.")
    parser.add_argument("--sport", choices=("football", "basketball"))
    parser.add_argument("--market", choices=tuple(MARKET_KEYS))
    parser.add_argument("--fixture-id")
    parser.add_argument("--home-team")
    parser.add_argument("--away-team")
    args = parser.parse_args()
    try:
        snapshot = (json.loads(args.snapshot.read_text(encoding="utf-8"))
                    if args.snapshot else fetch_snapshot())
        result = usable_quotes(snapshot, sport=args.sport, market=args.market,
                               fixture_id=args.fixture_id, home_team=args.home_team,
                               away_team=args.away_team)
    except (OSError, ValueError, TimeoutError, json.JSONDecodeError) as exc:
        result = {"status": "read_failed", "is_fresh": False, "quotes": [],
                  "reason": type(exc).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_fresh"] else 2


if __name__ == "__main__":
    sys.exit(main())
