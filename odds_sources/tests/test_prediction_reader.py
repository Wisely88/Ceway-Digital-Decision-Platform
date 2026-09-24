import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from for_prediction import usable_quotes
from monitor import iso

NOW = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)


def sample():
    q = {
        "source_id": "licensed_feed", "fixture_id": "2026-09-24-4302",
        "sport": "basketball", "market": "basketball_spread",
        "home_team": "墨凤凰", "away_team": "墨尔本联",
        "kickoff_utc": iso(NOW + timedelta(hours=2)),
        "quoted_at_utc": iso(NOW - timedelta(minutes=3)),
        "captured_at_utc": iso(NOW - timedelta(minutes=2)),
        "line": 2.5, "selection_odds": {"home": 1.75, "away": 1.65},
        "is_official_confirmed": False,
        "provenance": "authorized_feed_claim_unverified_against_official",
    }
    return {"checked_at_utc": iso(NOW - timedelta(minutes=2)),
            "feed_generated_at_utc": iso(NOW - timedelta(minutes=2)),
            "status": "fresh_authorized_feed", "is_fresh": True, "quotes": [q]}


class PredictionReaderTests(unittest.TestCase):
    def test_valid_quote_for_specific_match(self):
        r = usable_quotes(sample(), NOW, sport="basketball",
                          market="basketball_spread", fixture_id="2026-09-24-4302",
                          home_team="墨凤凰", away_team="墨尔本联")
        self.assertEqual(r["status"], "fresh_quotes")
        self.assertEqual(len(r["quotes"]), 1)
        self.assertFalse(r["quotes"][0]["is_official_confirmed"])

    def test_no_feed_never_uses_old_quotes(self):
        s = sample()
        s["status"], s["is_fresh"] = "no_authorized_feed", False
        self.assertEqual(usable_quotes(s, NOW)["status"], "no_live_feed")

    def test_stale_snapshot_rejected_even_when_flag_true(self):
        s = sample()
        s["checked_at_utc"] = iso(NOW - timedelta(minutes=46))
        self.assertEqual(usable_quotes(s, NOW)["status"], "stale_snapshot")

    def test_stale_feed_timestamp_rejected(self):
        s = sample()
        s["feed_generated_at_utc"] = iso(NOW - timedelta(minutes=46))
        self.assertEqual(usable_quotes(s, NOW)["status"], "stale_snapshot")

    def test_old_price_rejected_even_if_capture_current(self):
        s = sample()
        s["quotes"][0]["quoted_at_utc"] = iso(NOW - timedelta(hours=3))
        self.assertEqual(usable_quotes(s, NOW)["status"], "no_matching_fresh_quotes")

    def test_started_match_rejected(self):
        s = sample()
        s["quotes"][0]["kickoff_utc"] = iso(NOW - timedelta(minutes=1))
        self.assertEqual(usable_quotes(s, NOW)["status"], "no_matching_fresh_quotes")

    def test_team_order_is_not_silently_reversed(self):
        r = usable_quotes(sample(), NOW, home_team="墨尔本联", away_team="墨凤凰")
        self.assertEqual(r["status"], "no_matching_fresh_quotes")

    def test_market_and_outcomes_must_agree(self):
        s = sample()
        s["quotes"][0]["selection_odds"] = {"home": 1.75, "draw": 2.8, "away": 1.65}
        self.assertFalse(usable_quotes(s, NOW)["is_fresh"])

    def test_no_inferred_quote_when_live_file_empty(self):
        s = {"checked_at_utc": iso(NOW), "status": "no_authorized_feed",
             "is_fresh": False, "quotes": []}
        self.assertFalse(usable_quotes(s, NOW)["is_fresh"])


if __name__ == "__main__":
    unittest.main()
