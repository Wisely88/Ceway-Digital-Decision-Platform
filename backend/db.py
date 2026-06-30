from __future__ import annotations

import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "ceway.sqlite3"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            create table if not exists dlt_draws (
              issue text primary key,
              draw_date text not null,
              f1 integer not null,
              f2 integer not null,
              f3 integer not null,
              f4 integer not null,
              f5 integer not null,
              b1 integer not null,
              b2 integer not null,
              created_at text not null default current_timestamp,
              updated_at text not null default current_timestamp
            );

            create table if not exists dlt_recommendation_records (
              id text primary key,
              saved_at text not null,
              budget integer not null,
              strategy text not null,
              latest_issue text,
              plan_json text not null
            );

            create table if not exists dlt_review_results (
              record_id text primary key,
              reviewed_at text not null default current_timestamp,
              actual_issue text,
              result_json text not null
            );
            """
        )


def dlt_draw_count() -> int:
    init_db()
    with connect() as connection:
        return connection.execute("select count(*) from dlt_draws").fetchone()[0]


def replace_dlt_draws(rows: list[dict]) -> None:
    init_db()
    with connect() as connection:
        connection.execute("delete from dlt_draws")
        upsert_dlt_draws(rows, connection=connection)


def upsert_dlt_draws(rows: list[dict], connection: sqlite3.Connection | None = None) -> None:
    if connection is None:
        init_db()
    owns_connection = connection is None
    db = connection or connect()
    try:
        db.executemany(
            """
            insert into dlt_draws (issue, draw_date, f1, f2, f3, f4, f5, b1, b2)
            values (:issue, :date, :f1, :f2, :f3, :f4, :f5, :b1, :b2)
            on conflict(issue) do update set
              draw_date=excluded.draw_date,
              f1=excluded.f1,
              f2=excluded.f2,
              f3=excluded.f3,
              f4=excluded.f4,
              f5=excluded.f5,
              b1=excluded.b1,
              b2=excluded.b2,
              updated_at=current_timestamp
            """,
            [
                {
                    "issue": row["issue"],
                    "date": row["date"],
                    "f1": row["front"][0],
                    "f2": row["front"][1],
                    "f3": row["front"][2],
                    "f4": row["front"][3],
                    "f5": row["front"][4],
                    "b1": row["back"][0],
                    "b2": row["back"][1],
                }
                for row in rows
            ],
        )
        if owns_connection:
            db.commit()
    finally:
        if owns_connection:
            db.close()


def load_dlt_draws(limit: int | None = None, offset: int = 0) -> list[dict]:
    init_db()
    query = "select * from dlt_draws order by issue"
    params: list[int] = []
    if limit is not None:
        query += " limit ? offset ?"
        params.extend([limit, offset])
    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [draw_from_row(row) for row in rows]


def latest_dlt_draws(limit: int = 20) -> list[dict]:
    init_db()
    with connect() as connection:
        rows = connection.execute(
            "select * from dlt_draws order by issue desc limit ?",
            [limit],
        ).fetchall()
    return [draw_from_row(row) for row in rows]


def draw_from_row(row: sqlite3.Row) -> dict:
    return {
        "issue": row["issue"],
        "date": row["draw_date"],
        "front": [row["f1"], row["f2"], row["f3"], row["f4"], row["f5"]],
        "back": [row["b1"], row["b2"]],
    }


def save_dlt_record_db(record: dict) -> list[dict]:
    init_db()
    with connect() as connection:
        connection.execute(
            """
            insert into dlt_recommendation_records (id, saved_at, budget, strategy, latest_issue, plan_json)
            values (?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
              saved_at=excluded.saved_at,
              budget=excluded.budget,
              strategy=excluded.strategy,
              latest_issue=excluded.latest_issue,
              plan_json=excluded.plan_json
            """,
            [
                record["id"],
                record["saved_at"],
                record["budget"],
                record["strategy"],
                record.get("latest_issue"),
                json.dumps(record["plan"], ensure_ascii=False),
            ],
        )
    return load_dlt_records_db()


def load_dlt_records_db(limit: int = 100) -> list[dict]:
    init_db()
    with connect() as connection:
        rows = connection.execute(
            "select * from dlt_recommendation_records order by saved_at desc limit ?",
            [limit],
        ).fetchall()
    return [
        {
            "id": row["id"],
            "saved_at": row["saved_at"],
            "budget": row["budget"],
            "strategy": row["strategy"],
            "latest_issue": row["latest_issue"],
            "plan": json.loads(row["plan_json"]),
        }
        for row in rows
    ]


def save_review_results(items: list[dict]) -> None:
    init_db()
    reviewed_items = [item for item in items if item.get("status") == "reviewed" and item.get("record_id")]
    with connect() as connection:
        connection.executemany(
            """
            insert into dlt_review_results (record_id, actual_issue, result_json)
            values (?, ?, ?)
            on conflict(record_id) do update set
              reviewed_at=current_timestamp,
              actual_issue=excluded.actual_issue,
              result_json=excluded.result_json
            """,
            [
                [
                    item["record_id"],
                    item.get("actual", {}).get("issue"),
                    json.dumps(item, ensure_ascii=False),
                ]
                for item in reviewed_items
            ],
        )


def data_status() -> dict:
    init_db()
    with connect() as connection:
        draw_count = connection.execute("select count(*) from dlt_draws").fetchone()[0]
        record_count = connection.execute("select count(*) from dlt_recommendation_records").fetchone()[0]
        review_count = connection.execute("select count(*) from dlt_review_results").fetchone()[0]
        latest = connection.execute("select * from dlt_draws order by issue desc limit 1").fetchone()
    return {
        "storage": "sqlite",
        "path": str(DB_PATH),
        "draw_count": draw_count,
        "record_count": record_count,
        "review_count": review_count,
        "latest_issue": latest["issue"] if latest else None,
        "latest_date": latest["draw_date"] if latest else None,
    }
