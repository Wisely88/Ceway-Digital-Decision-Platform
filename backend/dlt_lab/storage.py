from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import db
from review import prize_label

from .types import DltValidationError, Ticket


MIGRATION_VERSION = "001_dlt_lab"

UP_SQL = """
create table if not exists dlt_lab_runs (
  id text primary key,
  parent_run_id text,
  version integer not null default 1,
  target_issue text not null,
  history_cutoff_issue text,
  mode text not null,
  model_version text not null,
  config_json text not null,
  result_json text not null default '{}',
  random_seed integer,
  status text not null default 'draft' check(status in ('draft','frozen','settled')),
  total_bets integer not null default 0,
  total_cost_yuan integer not null default 0,
  created_at text not null,
  updated_at text not null
);
create index if not exists idx_dlt_lab_runs_target on dlt_lab_runs(target_issue, created_at desc);

create table if not exists dlt_lab_tickets (
  id text primary key,
  run_id text not null references dlt_lab_runs(id) on delete cascade,
  ordinal integer not null,
  front_json text not null,
  back_json text not null,
  expression_type text not null,
  addon integer not null default 0,
  multiplier integer not null default 1,
  expanded_bets integer not null default 1,
  cost_yuan integer not null default 2,
  score_json text,
  structure_json text,
  collision_json text,
  unique(run_id, ordinal)
);

create table if not exists dlt_lab_aggregates (
  run_id text primary key references dlt_lab_runs(id) on delete cascade,
  aggregate_json text not null,
  candidate_profiles_json text
);

create table if not exists dlt_lab_freezes (
  id text primary key,
  run_id text not null unique references dlt_lab_runs(id) on delete restrict,
  version integer not null,
  frozen_payload_json text not null,
  sha256 text not null,
  frozen_at text not null
);

create table if not exists dlt_lab_settlements (
  run_id text primary key references dlt_lab_runs(id) on delete restrict,
  actual_issue text not null references dlt_draws(issue),
  result_json text not null,
  settled_at text not null
);
"""

DOWN_SQL = """
drop table if exists dlt_lab_settlements;
drop table if exists dlt_lab_freezes;
drop table if exists dlt_lab_aggregates;
drop table if exists dlt_lab_tickets;
drop index if exists idx_dlt_lab_runs_target;
drop table if exists dlt_lab_runs;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def migrate_up() -> None:
    db.init_db()
    with db.connect() as connection:
        connection.execute("pragma foreign_keys = on")
        connection.executescript(UP_SQL)
        run_columns = {row[1] for row in connection.execute("pragma table_info(dlt_lab_runs)")}
        if "result_json" not in run_columns:
            connection.execute("alter table dlt_lab_runs add column result_json text not null default '{}'")
        aggregate_columns = {row[1] for row in connection.execute("pragma table_info(dlt_lab_aggregates)")}
        if "candidate_profiles_json" not in aggregate_columns:
            connection.execute("alter table dlt_lab_aggregates add column candidate_profiles_json text")


def migrate_down() -> None:
    with db.connect() as connection:
        connection.execute("pragma foreign_keys = off")
        connection.executescript(DOWN_SQL)


def save_run(payload: dict) -> dict:
    migrate_up()
    run_id = payload.get("id") or f"dltlab-{uuid.uuid4()}"
    now = _now()
    tickets = payload.get("tickets") or []
    with db.connect() as connection:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            """
            insert into dlt_lab_runs (
              id, parent_run_id, version, target_issue, history_cutoff_issue, mode,
              model_version, config_json, result_json, random_seed, status, total_bets,
              total_cost_yuan, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            [
                run_id,
                payload.get("parent_run_id"),
                int(payload.get("version") or 1),
                payload["target_issue"],
                payload.get("history_cutoff_issue"),
                payload["mode"],
                payload.get("model_version") or "unspecified",
                _json(payload.get("config") or {}),
                _json({
                    key: payload[key]
                    for key in ("history", "candidate_count", "collision_fingerprint", "structures", "components", "spent", "unspent", "disclaimer")
                    if key in payload
                }),
                payload.get("random_seed"),
                int(payload.get("total_bets") or len(tickets)),
                int(payload.get("total_cost_yuan") or sum(int(ticket.get("cost_yuan") or 0) for ticket in tickets)),
                now,
                now,
            ],
        )
        for ordinal, ticket in enumerate(tickets, start=1):
            connection.execute(
                """
                insert into dlt_lab_tickets (
                  id, run_id, ordinal, front_json, back_json, expression_type, addon,
                  multiplier, expanded_bets, cost_yuan, score_json, structure_json, collision_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"{run_id}-ticket-{ordinal}",
                    run_id,
                    ordinal,
                    _json(ticket["front"]),
                    _json(ticket["back"]),
                    ticket.get("expression_type") or "single",
                    int(bool(ticket.get("addon"))),
                    int(ticket.get("multiplier") or 1),
                    int(ticket.get("expanded_bets") or 1),
                    int(ticket.get("cost_yuan") or 2),
                    _json(ticket.get("score_breakdown")) if ticket.get("score_breakdown") is not None else None,
                    _json(ticket.get("structure_features")) if ticket.get("structure_features") is not None else None,
                    _json(ticket.get("collision")) if ticket.get("collision") is not None else None,
                ],
            )
        if payload.get("aggregate") is not None:
            connection.execute(
                "insert into dlt_lab_aggregates (run_id, aggregate_json, candidate_profiles_json) values (?, ?, ?)",
                [
                    run_id,
                    _json(payload["aggregate"]),
                    _json(payload.get("candidate_profiles")) if payload.get("candidate_profiles") is not None else None,
                ],
            )
    return get_run(run_id)


def _row_to_run(row, tickets: list[dict], aggregate: dict | None, freeze: dict | None, settlement: dict | None) -> dict:
    result = {
        "id": row["id"],
        "parent_run_id": row["parent_run_id"],
        "version": row["version"],
        "target_issue": row["target_issue"],
        "history_cutoff_issue": row["history_cutoff_issue"],
        "mode": row["mode"],
        "model_version": row["model_version"],
        "config": json.loads(row["config_json"]),
        "random_seed": row["random_seed"],
        "status": row["status"],
        "total_bets": row["total_bets"],
        "total_cost_yuan": row["total_cost_yuan"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "tickets": tickets,
        "aggregate": aggregate,
        "freeze": freeze,
        "settlement": settlement,
    }
    result.update(json.loads(row["result_json"]) if "result_json" in row.keys() else {})
    return result


def get_run(run_id: str) -> dict:
    migrate_up()
    with db.connect() as connection:
        row = connection.execute("select * from dlt_lab_runs where id = ?", [run_id]).fetchone()
        if row is None:
            raise KeyError(run_id)
        ticket_rows = connection.execute("select * from dlt_lab_tickets where run_id = ? order by ordinal", [run_id]).fetchall()
        aggregate_row = connection.execute("select aggregate_json from dlt_lab_aggregates where run_id = ?", [run_id]).fetchone()
        freeze_row = connection.execute("select * from dlt_lab_freezes where run_id = ?", [run_id]).fetchone()
        settlement_row = connection.execute("select * from dlt_lab_settlements where run_id = ?", [run_id]).fetchone()
    tickets = [
        {
            "id": ticket["id"],
            "ordinal": ticket["ordinal"],
            "front": json.loads(ticket["front_json"]),
            "back": json.loads(ticket["back_json"]),
            "expression_type": ticket["expression_type"],
            "addon": bool(ticket["addon"]),
            "multiplier": ticket["multiplier"],
            "expanded_bets": ticket["expanded_bets"],
            "cost_yuan": ticket["cost_yuan"],
            "score_breakdown": json.loads(ticket["score_json"]) if ticket["score_json"] else None,
            "structure_features": json.loads(ticket["structure_json"]) if ticket["structure_json"] else None,
            "collision": json.loads(ticket["collision_json"]) if ticket["collision_json"] else None,
        }
        for ticket in ticket_rows
    ]
    freeze = None if freeze_row is None else {
        "version": freeze_row["version"], "sha256": freeze_row["sha256"], "frozen_at": freeze_row["frozen_at"]
    }
    settlement = None if settlement_row is None else json.loads(settlement_row["result_json"])
    return _row_to_run(
        row,
        tickets,
        json.loads(aggregate_row["aggregate_json"]) if aggregate_row else None,
        freeze,
        settlement,
    )


def list_runs(limit: int = 50, target_issue: str | None = None) -> list[dict]:
    migrate_up()
    where = " where target_issue = ?" if target_issue else ""
    params: list[object] = [target_issue] if target_issue else []
    with db.connect() as connection:
        rows = connection.execute(
            f"select id from dlt_lab_runs{where} order by created_at desc limit ?",
            [*params, limit],
        ).fetchall()
    return [get_run(row["id"]) for row in rows]


def get_candidate_profiles(run_id: str, limit: int = 100, offset: int = 0) -> dict:
    migrate_up()
    with db.connect() as connection:
        row = connection.execute("select candidate_profiles_json from dlt_lab_aggregates where run_id = ?", [run_id]).fetchone()
    if row is None:
        raise KeyError(run_id)
    profiles = json.loads(row["candidate_profiles_json"]) if row["candidate_profiles_json"] else []
    return {"items": profiles[offset:offset + limit], "total": len(profiles), "limit": limit, "offset": offset}


def freeze_run(run_id: str) -> dict:
    run = get_run(run_id)
    if run["status"] != "draft":
        raise DltValidationError("只有草稿运行可以冻结；已冻结运行请复制为新版本")
    payload = {
        "run_id": run["id"],
        "version": run["version"],
        "target_issue": run["target_issue"],
        "history_cutoff_issue": run["history_cutoff_issue"],
        "mode": run["mode"],
        "model_version": run["model_version"],
        "config": run["config"],
        "tickets": run["tickets"],
        "aggregate": run["aggregate"],
        "collision_fingerprint": run.get("collision_fingerprint"),
        "total_bets": run["total_bets"],
        "total_cost_yuan": run["total_cost_yuan"],
    }
    canonical = _json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    frozen_at = _now()
    with db.connect() as connection:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            "insert into dlt_lab_freezes (id, run_id, version, frozen_payload_json, sha256, frozen_at) values (?, ?, ?, ?, ?, ?)",
            [f"freeze-{uuid.uuid4()}", run_id, run["version"], canonical, digest, frozen_at],
        )
        connection.execute("update dlt_lab_runs set status = 'frozen', updated_at = ? where id = ?", [frozen_at, run_id])
    return get_run(run_id)


def clone_run(run_id: str) -> dict:
    source = get_run(run_id)
    payload = {
        "parent_run_id": source["id"],
        "version": source["version"] + 1,
        "target_issue": source["target_issue"],
        "history_cutoff_issue": source["history_cutoff_issue"],
        "mode": source["mode"],
        "model_version": source["model_version"],
        "config": source["config"],
        "random_seed": source["random_seed"],
        "tickets": source["tickets"],
        "aggregate": source["aggregate"],
        "total_bets": source["total_bets"],
        "total_cost_yuan": source["total_cost_yuan"],
    }
    for key in ("history", "candidate_count", "collision_fingerprint", "structures", "components", "spent", "unspent", "disclaimer"):
        if key in source:
            payload[key] = source[key]
    if source.get("aggregate") is not None:
        payload["candidate_profiles"] = get_candidate_profiles(run_id, limit=1_000_000)["items"]
    return save_run(payload)


def settle_run(run_id: str) -> dict:
    run = get_run(run_id)
    if run["status"] == "draft":
        raise DltValidationError("运行需要先冻结再复盘")
    if run["settlement"] is not None:
        return run
    with db.connect() as connection:
        draw = connection.execute("select * from dlt_draws where issue = ?", [run["target_issue"]]).fetchone()
    if draw is None:
        raise LookupError("目标期尚无开奖记录")
    actual_front = {draw[f"f{index}"] for index in range(1, 6)}
    actual_back = {draw[f"b{index}"] for index in range(1, 3)}
    details = []
    front_pool, back_pool = set(), set()
    for ticket in run["tickets"]:
        front_pool.update(ticket["front"])
        back_pool.update(ticket["back"])
        front_hits = len(set(ticket["front"]) & actual_front)
        back_hits = len(set(ticket["back"]) & actual_back)
        details.append({
            "ordinal": ticket["ordinal"],
            "front_hits": front_hits,
            "back_hits": back_hits,
            "total_hits": front_hits + back_hits,
            "hit_label": f"{front_hits}+{back_hits}",
            "prize_label": prize_label(front_hits, back_hits, run["target_issue"]),
        })
    with db.connect() as connection:
        previous_rows = connection.execute("select result_json from dlt_lab_settlements").fetchall()
    previous = [json.loads(row["result_json"]) for row in previous_rows]
    previous_details = [detail for item in previous for detail in item.get("details", [])]
    all_details = previous_details + details
    result = {
        "actual": {
            "issue": draw["issue"],
            "date": draw["draw_date"],
            "front": sorted(actual_front),
            "back": sorted(actual_back),
        },
        "details": details,
        "best": max(details, key=lambda item: (item["total_hits"], item["front_hits"], item["back_hits"]), default=None),
        "pool_coverage": {
            "front_hits": len(front_pool & actual_front),
            "back_hits": len(back_pool & actual_back),
            "front_pool_size": len(front_pool),
            "back_pool_size": len(back_pool),
        },
        "cumulative": {
            "settled_runs": len(previous) + 1,
            "settled_tickets": len(all_details),
            "prize_tickets": sum(detail.get("prize_label") != "未命中固定奖级" for detail in all_details),
            "best_total_hits": max((detail.get("total_hits", 0) for detail in all_details), default=0),
        },
    }
    settled_at = _now()
    with db.connect() as connection:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            "insert into dlt_lab_settlements (run_id, actual_issue, result_json, settled_at) values (?, ?, ?, ?)",
            [run_id, run["target_issue"], _json(result), settled_at],
        )
        connection.execute("update dlt_lab_runs set status = 'settled', updated_at = ? where id = ?", [settled_at, run_id])
    return get_run(run_id)


def compare_runs(target_issue: str, basis: str = "ticket_count") -> dict:
    if basis not in {"ticket_count", "budget"}:
        raise DltValidationError("对照口径仅支持 ticket_count 或 budget")
    runs = [run for run in list_runs(1000, target_issue) if run["settlement"]]
    if not runs:
        return {"target_issue": target_issue, "basis": basis, "comparison_limit": 0, "groups": {}, "disclaimer": "当前目标期没有已复盘的实验运行。"}
    comparison_limit = min(
        run["total_bets"] if basis == "ticket_count" else run["total_cost_yuan"]
        for run in runs
    )
    groups = {}
    for run in runs:
        label = "A" if run["mode"] == "model" else "B" if run["mode"] == "scarcity" else "C" if run["mode"] == "random" else "其他"
        allowed_details = []
        spent = 0
        for ticket, detail in zip(run["tickets"], run["settlement"].get("details", [])):
            if basis == "ticket_count":
                if len(allowed_details) >= comparison_limit:
                    break
            elif spent + ticket["cost_yuan"] > comparison_limit:
                break
            allowed_details.append(detail)
            spent += ticket["cost_yuan"]
        best = max((detail.get("total_hits", 0) for detail in allowed_details), default=0)
        group = groups.setdefault(label, {"runs": 0, "compared_tickets": 0, "compared_cost_yuan": 0, "best_total_hits": 0, "prize_tickets": 0})
        group["runs"] += 1
        group["compared_tickets"] += len(allowed_details)
        group["compared_cost_yuan"] += spent
        group["best_total_hits"] = max(group["best_total_hits"], best)
        group["prize_tickets"] += sum(detail.get("prize_label") != "未命中固定奖级" for detail in allowed_details)
    return {
        "target_issue": target_issue,
        "basis": basis,
        "comparison_limit": comparison_limit,
        "groups": groups,
        "disclaimer": "A/B/C 已按同注数或同预算裁齐，只比较开奖后的历史命中与覆盖，不代表未来概率提升。",
    }
