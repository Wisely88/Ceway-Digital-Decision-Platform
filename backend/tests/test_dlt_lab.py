from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import db  # noqa: E402
from dlt_lab import (  # noqa: E402
    DltValidationError,
    Draw,
    Ticket,
    aggregate_collision_profiles,
    calculate_bet,
    collision_profile,
    generate_model_run,
    generate_package_run,
    generate_random_run,
    select_history,
)
from dlt_lab.betting import expand_bet_expression  # noqa: E402
from dlt_lab.storage import clone_run, compare_runs, freeze_run, get_candidate_profiles, get_run, migrate_down, migrate_up, save_run, settle_run  # noqa: E402
from main import app  # noqa: E402


def fixture_draws() -> list[Draw]:
    return [
        Draw.create("26001", [1, 2, 3, 4, 5], [1, 2], "2026-01-01"),
        Draw.create("26002", [1, 6, 7, 8, 9], [1, 3], "2026-01-03"),
        Draw.create("26003", [10, 11, 12, 13, 14], [4, 5], "2026-01-05"),
    ]


async def asgi_request(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    parsed = urlsplit(url)
    body = json.dumps(payload or {}, ensure_ascii=False).encode() if payload is not None else b""
    sent = False
    messages: list[dict] = []

    async def receive() -> dict:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        messages.append(message)

    headers = [(b"host", b"testserver")]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
    await app(
        {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
            "scheme": "http", "path": parsed.path, "raw_path": parsed.path.encode(),
            "query_string": parsed.query.encode(), "headers": headers,
            "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
        },
        receive,
        send,
    )
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(response or b"{}")


class CollisionDomainTests(unittest.TestCase):
    def test_reference_collision_profile_and_aggregate(self) -> None:
        draws = fixture_draws()
        first = collision_profile(Ticket.create([1, 2, 6, 10, 20], [1, 5]), draws)
        second = collision_profile(Ticket.create([30, 31, 32, 33, 34], [11, 12]), draws)
        self.assertEqual(first.n_total_hits, (0, 0, 1, 2, 0, 0, 0, 0))
        self.assertEqual(first.n_front_back[2][1], 2)
        self.assertEqual(sum(first.n_total_hits), len(draws))
        self.assertEqual(sum(map(sum, first.n_front_back)), len(draws))
        self.assertEqual(first.scarcity_key, (0, 0, 0, 0, 2, 1, 0))
        aggregate = aggregate_collision_profiles([first, second])
        self.assertEqual(aggregate["m_total_hits"][0], 3)
        self.assertEqual(aggregate["u_total_hits"][0], 1)
        self.assertEqual(aggregate["m_front_back"][0][0], 3)
        self.assertEqual(aggregate["u_front_back"][0][0], 1)

    def test_history_windows_never_read_after_cutoff(self) -> None:
        draws = fixture_draws() + [Draw.create("26004", [20, 21, 22, 23, 24], [11, 12])]
        self.assertEqual([draw.issue for draw in select_history(draws, "26003", {"mode": "all_history"})], ["26001", "26002", "26003"])
        self.assertEqual([draw.issue for draw in select_history(draws, "26003", {"mode": "last_N", "count": 2})], ["26002", "26003"])
        self.assertEqual([draw.issue for draw in select_history(draws, "26003", {"mode": "custom", "start_issue": "26002", "end_issue": "26003"})], ["26002", "26003"])
        with self.assertRaises(DltValidationError):
            select_history(draws, "", {"mode": "all_history"})
        with self.assertRaises(DltValidationError):
            select_history(draws, "25000", {"mode": "all_history"})

    def test_future_perfect_match_cannot_change_model_run(self) -> None:
        draws = fixture_draws()
        arguments = {
            "target_issue": "26004", "history_cutoff_issue": "26003",
            "history_window": {"mode": "all_history"}, "front_pool_size": 7,
            "back_pool_size": 3, "output_count": 3,
        }
        first = generate_model_run(draws, **arguments)
        future = Draw.create("26005", first["tickets"][0]["front"], first["tickets"][0]["back"])
        second = generate_model_run(draws + [future], **arguments)
        self.assertEqual(first["tickets"], second["tickets"])
        self.assertEqual(first["aggregate"], second["aggregate"])
        self.assertEqual(first["aggregate"]["candidate_count"], first["candidate_count"])
        self.assertEqual(len(first["candidate_profiles"]), first["candidate_count"])


class BettingDomainTests(unittest.TestCase):
    def test_compound_dantuo_addon_and_multiplier_formulas(self) -> None:
        compound = calculate_bet({"type": "double_compound", "front": [1, 2, 3, 4, 5, 6], "back": [1, 2, 3]})
        self.assertEqual(compound.expanded_bets, 18)
        self.assertEqual(compound.cost_yuan, 36)
        dantuo = calculate_bet(
            {"type": "double_dantuo", "front_dan": [1, 2], "front_tuo": [3, 4, 5, 6, 7], "back_dan": [1], "back_tuo": [2, 3, 4]},
            addon=True,
            multiplier=2,
        )
        self.assertEqual(dantuo.expanded_bets, 30)
        self.assertEqual(dantuo.cost_yuan, 180)
        self.assertEqual(len(expand_bet_expression({"type": "double_compound", "front": [1, 2, 3, 4, 5, 6], "back": [1, 2, 3]})), 18)

    def test_invalid_boundaries_and_ticket_limit(self) -> None:
        with self.assertRaises(DltValidationError):
            calculate_bet({"type": "single", "front": [1, 2, 3, 4, 5], "back": [1, 2]}, multiplier=0)
        with self.assertRaises(DltValidationError):
            calculate_bet({"type": "front_dantuo", "front_dan": [], "front_tuo": [1, 2, 3, 4, 5, 6], "back": [1, 2]})
        with self.assertRaises(DltValidationError):
            calculate_bet(
                {"type": "double_compound", "front": list(range(1, 36)), "back": list(range(1, 13))},
                addon=True,
                multiplier=99,
            )

    def test_seeded_random_is_reproducible_and_unique(self) -> None:
        first = generate_random_run(target_issue="26004", history_cutoff_issue="26003", count=20, seed=42)
        second = generate_random_run(target_issue="26004", history_cutoff_issue="26003", count=20, seed=42)
        self.assertEqual(first["tickets"], second["tickets"])
        self.assertEqual(first["history_cutoff_issue"], "26003")
        self.assertEqual(len({(tuple(item["front"]), tuple(item["back"])) for item in first["tickets"]}), 20)

    def test_random_source_supports_compound_and_dantuo_expressions(self) -> None:
        compound = generate_random_run(
            target_issue="26004", count=1, seed=7,
            bet_expression={"type": "double_compound", "front_count": 6, "back_count": 3},
        )
        self.assertEqual(compound["total_bets"], 18)
        self.assertEqual(compound["total_cost_yuan"], 36)
        self.assertEqual(compound["structures"][0]["expression_type"], "double_compound")
        dantuo = generate_random_run(
            target_issue="26004", count=1, seed=7,
            bet_expression={"type": "double_dantuo", "front_dan_count": 2, "front_tuo_count": 5, "back_dan_count": 1, "back_tuo_count": 2},
        )
        self.assertEqual(dantuo["total_bets"], 20)
        self.assertEqual(dantuo["total_cost_yuan"], 40)

    def test_budget_templates_use_real_structures_and_never_exceed_budget(self) -> None:
        for template in ("dispersed_singles", "addon_singles", "small_compound", "dantuo", "mixed"):
            with self.subTest(template=template):
                run = generate_package_run(target_issue="26004", budget_yuan=60, template=template, seed=3)
                self.assertLessEqual(run["spent"], 60)
                self.assertEqual(run["unspent"], 60 - run["spent"])
                self.assertEqual(run["total_bets"], len(run["tickets"]))
                if template == "small_compound":
                    self.assertIn("front_compound", {item["expression_type"] for item in run["components"]})
                if template == "dantuo":
                    self.assertIn("front_dantuo", {item["expression_type"] for item in run["components"]})
        addon = generate_package_run(target_issue="26004", budget_yuan=18, template="addon_singles", seed=3)
        self.assertTrue(all(ticket["addon"] and ticket["cost_yuan"] == 3 for ticket in addon["tickets"]))


class StorageLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "ceway.sqlite3"
        db.replace_dlt_draws([
            {"issue": "26004", "date": "2026-01-08", "front": [1, 2, 3, 4, 5], "back": [1, 2]},
        ])

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db
        self.temp_dir.cleanup()

    def test_freeze_is_immutable_clone_versions_and_settlement_reads_draw(self) -> None:
        run = save_run(generate_random_run(target_issue="26004", count=2, seed=2))
        frozen = freeze_run(run["id"])
        self.assertEqual(frozen["status"], "frozen")
        self.assertEqual(len(frozen["freeze"]["sha256"]), 64)
        with self.assertRaises(DltValidationError):
            freeze_run(run["id"])
        clone = clone_run(run["id"])
        self.assertEqual(clone["status"], "draft")
        self.assertEqual(clone["version"], 2)
        settled = settle_run(run["id"])
        self.assertEqual(settled["status"], "settled")
        self.assertEqual(settled["settlement"]["actual"]["issue"], "26004")
        self.assertIn("pool_coverage", settled["settlement"])
        self.assertEqual(settled["settlement"]["cumulative"]["settled_runs"], 1)
        self.assertTrue(all("prize_label" in detail for detail in settled["settlement"]["details"]))

    def test_migration_is_reversible(self) -> None:
        migrate_up()
        migrate_down()
        with db.connect() as connection:
            names = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
        self.assertNotIn("dlt_lab_runs", names)
        migrate_up()
        with db.connect() as connection:
            names = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
        self.assertIn("dlt_lab_runs", names)

    def test_complete_candidate_profiles_are_persisted_separately_from_top_tickets(self) -> None:
        payload = generate_model_run(
            fixture_draws(), target_issue="26004", history_cutoff_issue="26003",
            history_window={"mode": "all_history"}, front_pool_size=7, back_pool_size=3, output_count=2,
        )
        run = save_run(payload)
        profiles = get_candidate_profiles(run["id"], limit=1000)
        self.assertEqual(len(run["tickets"]), 2)
        self.assertEqual(profiles["total"], payload["candidate_count"])
        self.assertEqual(run["aggregate"]["candidate_count"], payload["candidate_count"])

    def test_abc_comparison_is_trimmed_to_the_same_ticket_count(self) -> None:
        for mode, count in (("model", 3), ("scarcity", 2), ("random", 4)):
            payload = generate_random_run(target_issue="26004", count=count, seed=count)
            payload["mode"] = mode
            run = save_run(payload)
            freeze_run(run["id"])
            settle_run(run["id"])
        comparison = compare_runs("26004", "ticket_count")
        self.assertEqual(comparison["comparison_limit"], 2)
        self.assertEqual(set(comparison["groups"]), {"A", "B", "C"})
        self.assertTrue(all(group["compared_tickets"] == 2 for group in comparison["groups"].values()))


class DltLabApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "ceway.sqlite3"
        db.replace_dlt_draws([draw.to_dict() for draw in fixture_draws()])

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db
        self.temp_dir.cleanup()

    def request(self, method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
        return asyncio.run(asgi_request(method, url, payload))

    def test_openapi_contains_laboratory_contract(self) -> None:
        paths = app.openapi()["paths"]
        for path in (
            "/api/v1/lottery/dlt/rules", "/api/v1/lottery/dlt/collisions/analyze",
            "/api/v1/lottery/dlt/generate/model", "/api/v1/lottery/dlt/generate/random",
            "/api/v1/lottery/dlt/generate/package", "/api/v1/lottery/dlt/bet/calculate",
            "/api/v1/lottery/dlt/runs/{run_id}/freeze", "/api/v1/lottery/dlt/runs/{run_id}/settle",
        ):
            self.assertIn(path, paths)

    def test_collision_random_freeze_and_pending_settle_api(self) -> None:
        status, collision = self.request("POST", "/api/v1/lottery/dlt/collisions/analyze", {
            "history_cutoff_issue": "26003", "window": {"mode": "all_history"},
            "tickets": [{"front": [1, 2, 6, 10, 20], "back": [1, 5]}],
        })
        self.assertEqual(status, 200)
        self.assertEqual(collision["tickets"][0]["collision"]["n_total_hits"], [0, 0, 1, 2, 0, 0, 0, 0])
        status, run = self.request("POST", "/api/v1/lottery/dlt/generate/random", {"target_issue": "26004", "count": 2, "seed": 9})
        self.assertEqual(status, 200)
        self.assertEqual(run["history_cutoff_issue"], "26003")
        status, frozen = self.request("POST", f"/api/v1/lottery/dlt/runs/{run['id']}/freeze")
        self.assertEqual(status, 200)
        self.assertEqual(frozen["status"], "frozen")
        status, response = self.request("POST", f"/api/v1/lottery/dlt/runs/{run['id']}/settle")
        self.assertEqual(status, 409)
        self.assertIn("尚无开奖记录", response["detail"])

    def test_model_and_model_sourced_package_api_persist_real_candidate_data(self) -> None:
        status, model = self.request("POST", "/api/v1/lottery/dlt/generate/model", {
            "target_issue": "26004", "history_cutoff_issue": "26003",
            "history_window": {"mode": "all_history"}, "front_pool_size": 7,
            "back_pool_size": 3, "output_count": 2, "ranking_mode": "model",
        })
        self.assertEqual(status, 200)
        self.assertEqual(model["aggregate"]["candidate_count"], 63)
        status, candidates = self.request("GET", f"/api/v1/lottery/dlt/runs/{model['id']}/candidates?limit=10")
        self.assertEqual(status, 200)
        self.assertEqual(candidates["total"], 63)
        status, package = self.request("POST", "/api/v1/lottery/dlt/generate/package", {
            "target_issue": "26004", "history_cutoff_issue": "26003",
            "history_window": {"mode": "all_history"}, "budget_yuan": 40,
            "template": "mixed", "source": "model",
        })
        self.assertEqual(status, 200)
        self.assertLessEqual(package["spent"], 40)
        self.assertEqual(package["config"]["source"], "model")
        self.assertEqual(package["history_cutoff_issue"], "26003")
        status, random_package = self.request("POST", "/api/v1/lottery/dlt/generate/package", {
            "target_issue": "26004", "budget_yuan": 20,
            "template": "dispersed_singles", "source": "random", "seed": 7,
        })
        self.assertEqual(status, 200)
        self.assertEqual(random_package["history_cutoff_issue"], "26003")

    def test_empty_cutoff_and_invalid_import_are_explicit_errors(self) -> None:
        status, response = self.request("POST", "/api/v1/lottery/dlt/collisions/analyze", {
            "history_cutoff_issue": "25000", "window": {"mode": "all_history"},
            "tickets": [{"front": [1, 2, 3, 4, 5], "back": [1, 2]}],
        })
        self.assertEqual(status, 400)
        self.assertIn("没有可用", response["detail"])
        status, response = self.request("POST", "/api/v1/lottery/dlt/draws/import", {
            "mode": "append", "draws": [
                {"issue": "26010", "date": "2026-02-01", "front": [1, 2, 3, 4, 5], "back": [1, 2]},
                {"issue": "26010", "date": "2026-02-01", "front": [6, 7, 8, 9, 10], "back": [3, 4]},
            ],
        })
        self.assertEqual(status, 400)
        self.assertIn("重复期号", response["detail"])


if __name__ == "__main__":
    unittest.main()
