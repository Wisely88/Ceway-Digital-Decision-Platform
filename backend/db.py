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

            create table if not exists dlt_sync_runs (
              id integer primary key autoincrement,
              source text not null,
              status text not null,
              fetched_rows integer not null default 0,
              imported_rows integer not null default 0,
              message text,
              synced_at text not null default current_timestamp
            );
            """
        )


def dlt_draw_count() -> int:
    init_db()
    with connect() as connection:
        return connection.execute("select count(*) from dlt_draws").fetchone()[0]


def init_db_ssq() -> None:
    with connect() as connection:
        connection.executescript(
            """
            create table if not exists ssq_draws (
              issue text primary key,
              draw_date text not null,
              f1 integer not null,
              f2 integer not null,
              f3 integer not null,
              f4 integer not null,
              f5 integer not null,
              f6 integer not null,
              b1 integer not null,
              created_at text not null default current_timestamp,
              updated_at text not null default current_timestamp
            );

            create table if not exists ssq_recommendation_records (
              id text primary key,
              saved_at text not null,
              budget integer not null,
              strategy text not null,
              latest_issue text,
              plan_json text not null
            );

            create table if not exists ssq_review_results (
              record_id text primary key,
              reviewed_at text not null default current_timestamp,
              actual_issue text,
              result_json text not null
            );

            create table if not exists ssq_sync_runs (
              id integer primary key autoincrement,
              source text not null,
              status text not null,
              fetched_rows integer not null default 0,
              imported_rows integer not null default 0,
              message text,
              synced_at text not null default current_timestamp
            );
            """
        )


def ssq_draw_count() -> int:
    init_db_ssq()
    with connect() as connection:
        return connection.execute("select count(*) from ssq_draws").fetchone()[0]


def replace_ssq_draws(rows: list[dict]) -> None:
    init_db_ssq()
    with connect() as connection:
        connection.execute("delete from ssq_draws")
        upsert_ssq_draws(rows, connection=connection)


def upsert_ssq_draws(rows: list[dict], connection: sqlite3.Connection | None = None) -> None:
    if connection is None:
        init_db_ssq()
    owns_connection = connection is None
    db = connection or connect()
    try:
        db.executemany(
            """
            insert into ssq_draws (issue, draw_date, f1, f2, f3, f4, f5, f6, b1)
            values (:issue, :date, :f1, :f2, :f3, :f4, :f5, :f6, :b1)
            on conflict(issue) do update set
              draw_date=excluded.draw_date,
              f1=excluded.f1,
              f2=excluded.f2,
              f3=excluded.f3,
              f4=excluded.f4,
              f5=excluded.f5,
              f6=excluded.f6,
              b1=excluded.b1,
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
                    "f6": row["front"][5],
                    "b1": row["back"][0],
                }
                for row in rows
            ],
        )
        if owns_connection:
            db.commit()
    finally:
        if owns_connection:
            db.close()


def load_ssq_draws(limit: int | None = None, offset: int = 0) -> list[dict]:
    init_db_ssq()
    query = "select * from ssq_draws order by issue"
    params: list[int] = []
    if limit is not None:
        query += " limit ? offset ?"
        params.extend([limit, offset])
    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [ssq_draw_from_row(row) for row in rows]


def latest_ssq_draws(limit: int = 20) -> list[dict]:
    init_db_ssq()
    with connect() as connection:
        rows = connection.execute(
            "select * from ssq_draws order by issue desc limit ?",
            [limit],
        ).fetchall()
    return [ssq_draw_from_row(row) for row in rows]


def search_ssq_draws(limit: int = 20, offset: int = 0, issue: str | None = None) -> dict:
    init_db_ssq()
    where = ""
    params: list[str | int] = []
    if issue:
        where = " where issue like ?"
        params.append(f"%{issue}%")
    with connect() as connection:
        total = connection.execute(f"select count(*) from ssq_draws{where}", params).fetchone()[0]
        rows = connection.execute(
            f"select * from ssq_draws{where} order by issue desc limit ? offset ?",
            [*params, limit, offset],
        ).fetchall()
    return {
        "items": [ssq_draw_from_row(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "issue": issue or "",
    }


def ssq_draw_from_row(row: sqlite3.Row) -> dict:
    return {
        "issue": row["issue"],
        "date": row["draw_date"],
        "front": [row["f1"], row["f2"], row["f3"], row["f4"], row["f5"], row["f6"]],
        "back": [row["b1"]],
    }


def save_ssq_record_db(record: dict) -> list[dict]:
    init_db_ssq()
    with connect() as connection:
        connection.execute(
            """
            insert into ssq_recommendation_records (id, saved_at, budget, strategy, latest_issue, plan_json)
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
    return load_ssq_records_db()


def load_ssq_records_db(limit: int = 100) -> list[dict]:
    init_db_ssq()
    with connect() as connection:
        rows = connection.execute(
            "select * from ssq_recommendation_records order by saved_at desc limit ?",
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


def delete_ssq_record_db(record_id: str) -> bool:
    init_db_ssq()
    with connect() as connection:
        cursor = connection.execute("delete from ssq_recommendation_records where id = ?", [record_id])
        connection.execute("delete from ssq_review_results where record_id = ?", [record_id])
        return cursor.rowcount > 0


def save_ssq_review_results(items: list[dict]) -> None:
    init_db_ssq()
    reviewed_items = [item for item in items if item.get("status") == "reviewed" and item.get("record_id")]
    with connect() as connection:
        connection.executemany(
            """
            insert into ssq_review_results (record_id, actual_issue, result_json)
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


def save_ssq_sync_run(source: str, status: str, fetched_rows: int, imported_rows: int, message: str = "") -> None:
    init_db_ssq()
    with connect() as connection:
        connection.execute(
            """
            insert into ssq_sync_runs (source, status, fetched_rows, imported_rows, message)
            values (?, ?, ?, ?, ?)
            """,
            [source, status, fetched_rows, imported_rows, message],
        )


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


def search_dlt_draws(limit: int = 20, offset: int = 0, issue: str | None = None) -> dict:
    init_db()
    where = ""
    params: list[str | int] = []
    if issue:
        where = " where issue like ?"
        params.append(f"%{issue}%")
    with connect() as connection:
        total = connection.execute(f"select count(*) from dlt_draws{where}", params).fetchone()[0]
        rows = connection.execute(
            f"select * from dlt_draws{where} order by issue desc limit ? offset ?",
            [*params, limit, offset],
        ).fetchall()
    return {
        "items": [draw_from_row(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "issue": issue or "",
    }


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


def delete_dlt_record_db(record_id: str) -> bool:
    init_db()
    with connect() as connection:
        cursor = connection.execute("delete from dlt_recommendation_records where id = ?", [record_id])
        connection.execute("delete from dlt_review_results where record_id = ?", [record_id])
        return cursor.rowcount > 0


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
    init_db_ssq()
    with connect() as connection:
        draw_count = connection.execute("select count(*) from dlt_draws").fetchone()[0]
        record_count = connection.execute("select count(*) from dlt_recommendation_records").fetchone()[0]
        review_count = connection.execute("select count(*) from dlt_review_results").fetchone()[0]
        latest = connection.execute("select * from dlt_draws order by issue desc limit 1").fetchone()
        first = connection.execute("select * from dlt_draws order by issue asc limit 1").fetchone()
        rows = connection.execute("select issue from dlt_draws order by issue").fetchall()
        sync = connection.execute("select * from dlt_sync_runs order by synced_at desc, id desc limit 1").fetchone()
    quality = dlt_quality_from_issues([row["issue"] for row in rows])
    return {
        "storage": "sqlite",
        "path": str(DB_PATH),
        "draw_count": draw_count,
        "record_count": record_count,
        "review_count": review_count,
        "first_issue": first["issue"] if first else None,
        "first_date": first["draw_date"] if first else None,
        "latest_issue": latest["issue"] if latest else None,
        "latest_date": latest["draw_date"] if latest else None,
        "quality": quality,
        "last_sync": dict(sync) if sync else None,
    }


def ssq_data_status() -> dict:
    init_db_ssq()
    with connect() as connection:
        draw_count = connection.execute("select count(*) from ssq_draws").fetchone()[0]
        record_count = connection.execute("select count(*) from ssq_recommendation_records").fetchone()[0]
        review_count = connection.execute("select count(*) from ssq_review_results").fetchone()[0]
        latest = connection.execute("select * from ssq_draws order by issue desc limit 1").fetchone()
        first = connection.execute("select * from ssq_draws order by issue asc limit 1").fetchone()
        rows = connection.execute("select issue from ssq_draws order by issue").fetchall()
        sync = connection.execute("select * from ssq_sync_runs order by synced_at desc, id desc limit 1").fetchone()
    quality = ssq_quality_from_issues([row["issue"] for row in rows])
    return {
        "storage": "sqlite",
        "path": str(DB_PATH),
        "draw_count": draw_count,
        "record_count": record_count,
        "review_count": review_count,
        "first_issue": first["issue"] if first else None,
        "first_date": first["draw_date"] if first else None,
        "latest_issue": latest["issue"] if latest else None,
        "latest_date": latest["draw_date"] if latest else None,
        "quality": quality,
        "last_sync": dict(sync) if sync else None,
    }


def dlt_quality_from_issues(issues: list[str]) -> dict:
    year_groups: dict[str, set[int]] = {}
    skipped = []
    for issue in issues:
        issue_text = str(issue).strip()
        if len(issue_text) == 5:
            year = issue_text[:2]
            sequence = issue_text[2:]
        elif len(issue_text) == 7:
            year = issue_text[:4]
            sequence = issue_text[4:]
        else:
            skipped.append(issue_text)
            continue
        if not sequence.isdigit():
            skipped.append(issue_text)
            continue
        year_groups.setdefault(year, set()).add(int(sequence))

    missing = []
    year_ranges = []
    for year, numbers in sorted(year_groups.items()):
        if not numbers:
            continue
        start = min(numbers)
        end = max(numbers)
        year_missing = [
            format_dlt_issue(year, number)
            for number in range(start, end + 1)
            if number not in numbers
        ]
        missing.extend(year_missing)
        year_ranges.append(
            {
                "year": year,
                "first": format_dlt_issue(year, start),
                "last": format_dlt_issue(year, end),
                "count": len(numbers),
                "missing_count": len(year_missing),
            }
        )

    if len(issues) <= 30:
        level = "sample"
        label = "样例数据"
        message = "当前开奖数据量较少，仅适合界面验证和流程测试。"
    elif missing:
        level = "gap"
        label = "存在缺口"
        message = f"检测到 {len(missing)} 个期号缺口，请补充历史开奖 CSV 后再做正式分析。"
    else:
        level = "ok"
        label = "连续完整"
        message = "已导入期号范围内未发现连续性缺口。"

    return {
        "level": level,
        "label": label,
        "message": message,
        "missing_count": len(missing),
        "missing_issues": missing[:30],
        "skipped_issues": skipped[:10],
        "year_ranges": year_ranges,
    }


def format_dlt_issue(year: str, number: int) -> str:
    return f"{year}{number:03d}"


def ssq_quality_from_issues(issues: list[str]) -> dict:
    year_groups: dict[str, set[int]] = {}
    skipped = []
    for issue in issues:
        issue_text = str(issue).strip()
        if len(issue_text) == 5:
            year = issue_text[:2]
            sequence = issue_text[2:]
        elif len(issue_text) == 7:
            year = issue_text[:4]
            sequence = issue_text[4:]
        else:
            skipped.append(issue_text)
            continue
        if not sequence.isdigit():
            skipped.append(issue_text)
            continue
        year_groups.setdefault(year, set()).add(int(sequence))

    missing = []
    year_ranges = []
    for year, numbers in sorted(year_groups.items()):
        if not numbers:
            continue
        start = min(numbers)
        end = max(numbers)
        year_missing = [
            format_ssq_issue(year, number)
            for number in range(start, end + 1)
            if number not in numbers
        ]
        missing.extend(year_missing)
        year_ranges.append(
            {
                "year": year,
                "first": format_ssq_issue(year, start),
                "last": format_ssq_issue(year, end),
                "count": len(numbers),
                "missing_count": len(year_missing),
            }
        )

    if len(issues) <= 30:
        level = "sample"
        label = "样例数据"
        message = "当前开奖数据量较少，仅适合界面验证和流程测试。"
    elif missing:
        level = "gap"
        label = "存在缺口"
        message = f"检测到 {len(missing)} 个期号缺口，请补充历史开奖 CSV 后再做正式分析。"
    else:
        level = "ok"
        label = "连续完整"
        message = "已导入期号范围内未发现连续性缺口。"

    return {
        "level": level,
        "label": label,
        "message": message,
        "missing_count": len(missing),
        "missing_issues": missing[:30],
        "skipped_issues": skipped[:10],
        "year_ranges": year_ranges,
    }


def format_ssq_issue(year: str, number: int) -> str:
    return f"{year}{number:03d}"


def load_ssq_review_results() -> dict:
    init_db_ssq()
    with connect() as connection:
        items = connection.execute(
            """
            select r.*, rr.result_json
            from ssq_recommendation_records r
            left join ssq_review_results rr on r.id = rr.record_id
            order by r.saved_at desc
            limit 100
            """
        ).fetchall()
    reviewed = []
    pending = []
    for row in items:
        plan = json.loads(row["plan_json"])
        if row["result_json"]:
            result = json.loads(row["result_json"])
            reviewed.append(result)
        else:
            pending.append(
                {
                    "record_id": row["id"],
                    "saved_at": row["saved_at"],
                    "budget": row["budget"],
                    "strategy": row["strategy"],
                    "latest_issue": row["latest_issue"],
                    "plan": plan,
                }
            )
    summary = {
        "reviewed": len(reviewed),
        "pending": len(pending),
        "total_cost": sum(
            sum(item.get("plan", {}).get("plan", {}).get("cost", 0) if isinstance(item.get("plan"), dict) else 0 for item in reviewed)
            if isinstance(reviewed, list)
            else 0
        ),
        "record_hit_rate": 0,
        "best_hit": "-",
        "best_prize_label": "-",
    }
    if reviewed:
        hit_items = [r for r in reviewed if r.get("status") == "reviewed" and r.get("result", {}).get("best_hit", 0) > 0]
        summary["record_hit_rate"] = round(len(hit_items) / max(len(reviewed), 1) * 100, 1)
        best = max(reviewed, key=lambda r: r.get("result", {}).get("best_hit", 0) or 0) if reviewed else None
        if best:
            summary["best_hit"] = best.get("result", {}).get("best_hit", "-")
            summary["best_prize_label"] = best.get("result", {}).get("best_prize_label", "-")
    return {
        "summary": summary,
        "items": reviewed + pending,
        "disclaimer": "SSQ复盘结果基于推荐记录与对应开奖数据计算。",
    }


def save_sync_run(source: str, status: str, fetched_rows: int, imported_rows: int, message: str = "") -> None:
    init_db()
    with connect() as connection:
        connection.execute(
            """
            insert into dlt_sync_runs (source, status, fetched_rows, imported_rows, message)
            values (?, ?, ?, ?, ?)
            """,
            [source, status, fetched_rows, imported_rows, message],
        )
