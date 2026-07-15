from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import db  # noqa: E402
from main import app  # noqa: E402


async def asgi_request(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    parsed = urlsplit(url)
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    request_sent = False
    messages: list[dict] = []

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        messages.append(message)

    headers = [(b"host", b"testserver")]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("utf-8"),
        "query_string": parsed.query.encode("utf-8"),
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    await app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return status, json.loads(response_body or b"{}")


def request(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    return asyncio.run(asgi_request(method, url, payload))


class ApiReviewFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "ceway-test.sqlite3"

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_dlt_save_draw_and_review_flow(self) -> None:
        db.replace_dlt_draws(
            [
                {"issue": "26001", "date": "2026-01-01", "front": [6, 7, 8, 9, 10], "back": [3, 4]},
                {"issue": "26002", "date": "2026-01-03", "front": [1, 2, 3, 4, 5], "back": [1, 2]},
            ]
        )
        record = {
            "budget": 2,
            "strategy": "balanced",
            "latest_issue": "26001",
            "plan": {
                "scene": "DLT",
                "mode": "single",
                "recommended_issue": "26002",
                "items": [{"front": [1, 2, 3, 4, 5], "back": [1, 2]}],
                "tickets": 1,
                "cost": 2,
            },
        }

        save_status, saved = request("POST", "/records/dlt", record)
        review_status, reviewed = request("GET", "/review/dlt")

        self.assertEqual(save_status, 200)
        self.assertEqual(saved["status"], "ok")
        self.assertEqual(review_status, 200)
        self.assertEqual(reviewed["summary"]["reviewed"], 1)
        self.assertEqual(reviewed["items"][0]["status"], "reviewed")
        self.assertEqual(reviewed["items"][0]["actual"]["issue"], "26002")
        self.assertEqual(reviewed["items"][0]["best"]["prize_label"], "一等奖")
        with sqlite3.connect(db.DB_PATH) as connection:
            self.assertEqual(connection.execute("select count(*) from dlt_review_results").fetchone()[0], 1)

    def test_ssq_save_draw_and_review_flow(self) -> None:
        db.replace_ssq_draws(
            [
                {"issue": "2026001", "date": "2026-01-01", "front": [7, 8, 9, 10, 11, 12], "back": [2]},
                {"issue": "2026002", "date": "2026-01-04", "front": [1, 2, 3, 4, 5, 6], "back": [1]},
            ]
        )
        record = {
            "budget": 2,
            "strategy": "balanced",
            "latest_issue": "2026001",
            "plan": {
                "scene": "SSQ",
                "mode": "single",
                "recommended_issue": "2026002",
                "items": [{"front": [1, 2, 3, 4, 5, 6], "back": [1]}],
                "tickets": 1,
                "cost": 2,
            },
        }

        save_status, saved = request("POST", "/records/ssq", record)
        review_status, reviewed = request("GET", "/review/ssq")

        self.assertEqual(save_status, 200)
        self.assertEqual(saved["status"], "ok")
        self.assertEqual(review_status, 200)
        self.assertEqual(reviewed["summary"]["reviewed"], 1)
        self.assertEqual(reviewed["items"][0]["status"], "reviewed")
        self.assertEqual(reviewed["items"][0]["actual"]["issue"], "2026002")
        self.assertEqual(reviewed["items"][0]["best"]["prize_label"], "一等奖")
        with sqlite3.connect(db.DB_PATH) as connection:
            self.assertEqual(connection.execute("select count(*) from ssq_review_results").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
