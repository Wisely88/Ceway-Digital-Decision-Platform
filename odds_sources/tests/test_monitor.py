import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor import check_page, validate_quotes, iso

REGISTRY = {"sources": [{"id": "licensed_feed"}]}
NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)

def item(**changes):
    data = {"fixture_id": "2026-09-24-4302", "sport": "basketball",
            "market": "basketball_spread", "source_id": "licensed_feed",
            "home_team": "墨凤凰", "away_team": "墨尔本联",
            "kickoff_utc": iso(NOW + timedelta(hours=2)),
            "quoted_at_utc": iso(NOW - timedelta(minutes=3)),
            "line": 2.5, "selection_odds": {"home": 1.75, "away": 1.65}}
    data.update(changes)
    return data

def payload(quote, offset=1):
    return {"generated_at_utc": iso(NOW - timedelta(minutes=offset)), "quotes": [quote]}

class MonitorTests(unittest.TestCase):
    def test_valid_basketball_spread_signed_for_home(self):
        valid, rejected = validate_quotes(payload(item()), REGISTRY, NOW)
        self.assertEqual(len(valid), 1)
        self.assertFalse(rejected)
        self.assertEqual(valid[0]["line"], 2.5)
        self.assertFalse(valid[0]["is_official_confirmed"])

    def test_stale_price_rejected(self):
        valid, rejected = validate_quotes(payload(item(quoted_at_utc=iso(NOW - timedelta(hours=2)))), REGISTRY, NOW)
        self.assertFalse(valid)
        self.assertEqual(len(rejected), 1)

    def test_feed_future_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            validate_quotes(payload(item(), offset=-10), REGISTRY, NOW)

    def test_no_line_for_1x2(self):
        q = item(sport="football", market="football_1x2", line=None,
                 selection_odds={"home": 1.85, "draw": 3.55, "away": 4.75})
        valid, rejected = validate_quotes(payload(q), REGISTRY, NOW)
        self.assertEqual(len(valid), 1)
        self.assertFalse(rejected)

    def test_wrong_outcomes_rejected(self):
        valid, rejected = validate_quotes(payload(item(selection_odds={"home": 1.7, "draw": 3.1})), REGISTRY, NOW)
        self.assertFalse(valid)
        self.assertEqual(len(rejected), 1)

    def test_http_200_not_quote_freshness(self):
        def fake(_url):
            return 200, "text/html", b"match 2026-09-24 and some old odds"
        rec = check_page({"id": "mock", "url": "https://example.org"}, NOW.date(), fake)
        self.assertEqual(rec["date_signal"], "current_fixture_date_visible")
        self.assertEqual(rec["odds_freshness"], "not_verified")

    def test_mismatched_football_market_rejected(self):
        valid, rejected = validate_quotes(payload(item(sport="football")), REGISTRY, NOW)
        self.assertFalse(valid)
        self.assertEqual(len(rejected), 1)

    def test_duplicate_keys_rejected(self):
        data = payload(item())
        data["quotes"].append(item())
        valid, rejected = validate_quotes(data, REGISTRY, NOW)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(rejected), 1)

if __name__ == "__main__":
    unittest.main()
