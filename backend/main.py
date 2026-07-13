from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backtest import build_dlt_backtest, build_ssq_backtest
from capital import capital_state
from db import (
    data_status,
    delete_dlt_record_db,
    delete_ssq_record_db,
    load_ssq_records_db,
    save_review_results,
    save_ssq_review_results,
    save_ssq_sync_run,
    search_dlt_draws,
    search_ssq_draws,
    ssq_data_status,
)
from engine import (
    calculate_trends,
    calculate_ssq_trends,
    load_dlt_history,
    load_dlt_records,
    load_latest_dlt_draws,
    load_latest_ssq_draws,
    load_scenes,
    load_ssq_history,
    load_ssq_records,
    save_dlt_history,
    save_dlt_record,
    save_ssq_history,
    save_ssq_record,
)
from generator import generate_plans, generate_ssq_plans, normalize_strategy
from review import build_review, build_ssq_review, review_ssq_plan
from scorer import score_back_numbers, score_front_numbers, score_ssq_back_numbers, score_ssq_front_numbers


app = FastAPI(title="Ceway v1.6 Decision Risk API")
ROOT_DIR = Path(__file__).resolve().parents[1]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    budget: int = Field(default=20, ge=2)
    strategy: str | None = Field(default=None, pattern="^(conservative|balanced|aggressive)$")
    mode: str | None = Field(default=None, pattern="^(single|dantuo|auto)$")
    last_prize: float = Field(default=0, ge=0)
    principal: float = Field(default=1000, ge=0)
    balance: float | None = Field(default=None, ge=0)
    level_units: int = Field(default=1, ge=1, le=4)
    window: int = Field(default=100, ge=30, le=200)
    variant: int = Field(default=0, ge=0)


class RecordRequest(BaseModel):
    budget: int = Field(ge=2)
    strategy: str
    latest_issue: str | None = None
    plan: dict


def next_issue_label(issue: str | None) -> str | None:
    if not issue or not issue.isdigit():
        return None
    return f"{int(issue) + 1:0{len(issue)}d}"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/scenes")
def scenes() -> list[dict]:
    scene_config = load_scenes()
    return [
        {
            "code": scene["code"],
            "name": scene["name"],
            "module": scene.get("module"),
            "status": scene.get("status", "已上线" if scene["enabled"] else "规划中"),
            "description": scene.get("description", ""),
            "enabled": scene["enabled"],
            "front": scene["front"],
            "back": scene["back"],
        }
        for scene in scene_config.values()
    ]


def build_dlt_payload(
    budget: int,
    last_prize: float,
    strategy: str | None = "balanced",
    mode: str | None = None,
    principal: float = 1000,
    balance: float | None = None,
    level_units: int = 1,
    window: int = 100,
    variant: int = 0,
) -> dict:
    selected_strategy = normalize_strategy(strategy, mode)
    history = load_dlt_history()
    trends = calculate_trends(history, window=window)
    score_table = score_front_numbers(trends)
    back_scores = score_back_numbers(trends)
    plans = generate_plans(
        budget=budget,
        strategy=selected_strategy,
        score_table=score_table,
        back_scores=back_scores,
        mode=mode,
        variant=variant,
    )
    capital = capital_state(
        last_prize=last_prize,
        principal=principal,
        balance=balance,
        level_units=level_units,
    )
    top_numbers = [item["number"] for item in score_table[:5]]
    latest_row = history[-1] if history else None
    based_on_issue = latest_row["issue"] if latest_row else None
    recommended_issue = next_issue_label(based_on_issue)
    for plan in plans:
        plan["scene"] = "DLT"
        plan["play_name"] = "大乐透"
        plan["play_labels"] = {
            "front": "前区",
            "back": "后区",
            "dan": "前区胆码",
            "tuo": "前区拖码",
            "single": "单式票",
            "rule": "大乐透：前区 35 选 5，后区 12 选 2。胆拖费用 = C(拖码数, 5 - 胆码数) × C(后区号码数, 2) × 2 元。",
        }
        plan["based_on_issue"] = based_on_issue
        plan["recommended_issue"] = recommended_issue
        plan["recommendation_label"] = (
            f"基于第 {based_on_issue} 期开奖数据，生成第 {recommended_issue} 期推荐方案。"
            if based_on_issue and recommended_issue
            else "基于当前最新开奖数据，生成下一期开奖推荐方案。"
        )
    storage_status = data_status()

    return {
        "scene": "DLT",
        "product": {
            "name": "策维",
            "english_name": "Ceway",
            "subtitle": "Digital Decision Platform",
            "framework": "Powered by CBGO Framework",
            "baseline": "v1.2 MVP",
            "version": "v1.6 Decision Risk",
        },
        "disclaimer": "策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
        "history_count": len(history),
        "latest_issue": based_on_issue,
        "recommended_issue": recommended_issue,
        "data_status": {
            "source": "sqlite",
            "source_label": "SQLite 数据库",
            "path": "backend/data/ceway.sqlite3",
            "latest_issue": based_on_issue,
            "latest_date": latest_row["date"] if latest_row else None,
            "is_sample": len(history) <= 30,
            "message": "当前走势分析基于本地 SQLite 数据库。可通过 CSV 导入更新开奖数据。",
            "quality": storage_status.get("quality"),
            "last_sync": storage_status.get("last_sync"),
        },
        "top_numbers": top_numbers,
        "budget": budget,
        "strategy": selected_strategy,
        "window": trends["window"],
        "recommended_amount": max((plan["cost"] for plan in plans), default=0),
        "capital_state": capital,
        "trends": trends,
        "score_table": score_table,
        "plans": plans,
    }


@app.get("/dashboard/dlt")
def dashboard_dlt(
    budget: int = Query(default=20, ge=2),
    last_prize: float = Query(default=0, ge=0),
    strategy: str | None = Query(default="balanced", pattern="^(conservative|balanced|aggressive)$"),
    mode: str | None = Query(default=None, pattern="^(single|dantuo|auto)$"),
    principal: float = Query(default=1000, ge=0),
    balance: float | None = Query(default=None, ge=0),
    level_units: int = Query(default=1, ge=1, le=4),
    window: int = Query(default=100, ge=30, le=200),
) -> dict:
    return build_dlt_payload(
        budget=budget,
        last_prize=last_prize,
        strategy=strategy,
        mode=mode,
        principal=principal,
        balance=balance,
        level_units=level_units,
        window=window,
    )


@app.post("/generate/dlt")
def generate_dlt(request: GenerateRequest) -> dict:
    plans = build_dlt_payload(
        budget=request.budget,
        last_prize=request.last_prize,
        strategy=request.strategy,
        mode=request.mode,
        principal=request.principal,
        balance=request.balance,
        level_units=request.level_units,
        window=request.window,
        variant=request.variant,
    )["plans"]
    if not plans:
        raise HTTPException(status_code=400, detail="No plan can be generated within this budget")
    return plans[0]


@app.post("/plan/dlt")
def plan_dlt(request: GenerateRequest) -> dict:
    return generate_dlt(request)


@app.get("/records/dlt")
def records_dlt() -> list[dict]:
    try:
        return load_dlt_records()
    except Exception:
        return []


@app.delete("/records/dlt/{record_id}")
def delete_record_dlt(record_id: str) -> dict:
    deleted = delete_dlt_record_db(record_id)
    return {"status": "ok", "deleted": deleted, "id": record_id}


@app.post("/records/dlt")
def create_record_dlt(request: RecordRequest) -> dict:
    record = {
        "id": f"dlt-{datetime.now(timezone.utc).timestamp()}",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "budget": request.budget,
        "strategy": request.strategy,
        "latest_issue": request.latest_issue,
        "plan": request.plan,
    }
    records = save_dlt_record(record)
    return {"status": "ok", "record": record, "count": len(records)}


@app.get("/review/dlt")
def review_dlt(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    try:
        payload = build_review(load_dlt_records(), load_dlt_history(), limit=limit)
        save_review_results(payload.get("items", []))
        return payload
    except Exception as exc:
        return {
            "summary": {
                "records": 0,
                "reviewed": 0,
                "pending": 0,
                "total_cost": 0,
                "hit_records": 0,
                "record_hit_rate": 0.0,
                "best_hit": "-",
                "best_prize_label": "-",
            },
            "items": [],
            "disclaimer": f"复盘数据暂不可用，已跳过异常记录。原因：{exc}",
        }


@app.get("/backtest/dlt")
def backtest_dlt(
    budget: int = Query(default=20, ge=2),
    strategy: str = Query(default="balanced", pattern="^(conservative|balanced|aggressive)$"),
    periods: int = Query(default=100, ge=5, le=500),
    window: int = Query(default=100, ge=30, le=200),
) -> dict:
    return build_dlt_backtest(
        load_dlt_history(),
        budget=budget,
        strategy=strategy,
        periods=periods,
        window=window,
    )


@app.get("/data/dlt/status")
def dlt_data_status() -> dict:
    load_dlt_history()
    return data_status()


@app.get("/data/dlt/draws")
def dlt_draws(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    issue: str | None = Query(default=None),
) -> dict:
    return search_dlt_draws(limit=limit, offset=offset, issue=issue)


@app.post("/data/dlt/sync")
def sync_dlt_history(
    source: str = Query(default="78500", pattern="^(sporttery|78500)$"),
    full: bool = Query(default=False),
) -> dict:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "update_dlt_history.py"),
        "--source",
        source,
        "--mode",
        "replace" if full else "append",
        "--limit",
        "100",
    ]
    if full:
        command.append("--all")
    try:
        result = subprocess.run(
            command,
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="开奖数据同步超时，请稍后重试。") from exc

    output = (result.stdout or result.stderr).strip()
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = {"status": "failed", "message": output or "同步脚本没有返回有效结果"}

    if result.returncode != 0:
        raise HTTPException(status_code=502, detail=payload.get("message", "开奖数据同步失败"))
    return {"status": "ok", "sync": payload, "data_status": data_status()}


@app.get("/data/dlt/template")
def dlt_template() -> Response:
    csv_text = "issue,date,f1,f2,f3,f4,f5,b1,b2\n2025001,2025-01-01,3,7,18,22,31,4,11\n"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=dlt_history_template.csv"},
    )


@app.post("/data/dlt/import")
async def import_dlt_history(
    file: UploadFile = File(...),
    mode: str = Query(default="replace", pattern="^(replace|append)$"),
) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
        count = save_dlt_history(csv_text, mode=mode)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "filename": file.filename,
        "mode": mode,
        "rows": count,
    }


# --- SSQ 双色球路由 ---


def build_ssq_payload(
    budget: int,
    last_prize: float,
    strategy: str | None = "balanced",
    mode: str | None = None,
    principal: float = 1000,
    balance: float | None = None,
    level_units: int = 1,
    window: int = 100,
    variant: int = 0,
) -> dict:
    selected_strategy = normalize_strategy(strategy, mode)
    history = load_ssq_history()
    trends = calculate_ssq_trends(history, window=window)
    score_table = score_ssq_front_numbers(trends)
    back_scores = score_ssq_back_numbers(trends)
    plans = generate_ssq_plans(
        budget=budget,
        strategy=selected_strategy,
        score_table=score_table,
        back_scores=back_scores,
        mode=mode,
        variant=variant,
    )
    capital = capital_state(
        last_prize=last_prize,
        principal=principal,
        balance=balance,
        level_units=level_units,
    )
    top_numbers = [item["number"] for item in score_table[:6]]
    latest_row = history[-1] if history else None
    based_on_issue = latest_row["issue"] if latest_row else None
    recommended_issue = next_issue_label(based_on_issue)
    for plan in plans:
        plan["scene"] = "SSQ"
        plan["play_name"] = "双色球"
        plan["play_labels"] = {
            "front": "红球",
            "back": "蓝球",
            "dan": "红球胆码",
            "tuo": "红球拖码",
            "single": "单式票",
            "rule": "双色球：红球 33 选 6，蓝球 16 选 1。胆拖费用 = C(拖码数, 6 - 胆码数) × 蓝球个数 × 2 元。",
        }
        plan["based_on_issue"] = based_on_issue
        plan["recommended_issue"] = recommended_issue
        plan["recommendation_label"] = (
            f"基于第 {based_on_issue} 期开奖数据，生成第 {recommended_issue} 期推荐方案。"
            if based_on_issue and recommended_issue
            else "基于当前最新开奖数据，生成下一期开奖推荐方案。"
        )
    storage_status = ssq_data_status()

    return {
        "scene": "SSQ",
        "product": {
            "name": "策维",
            "english_name": "Ceway",
            "subtitle": "Digital Decision Platform",
            "framework": "Powered by CBGO Framework",
            "baseline": "v1.2 MVP",
            "version": "v1.6 Decision Risk",
        },
        "disclaimer": "策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
        "history_count": len(history),
        "latest_issue": based_on_issue,
        "recommended_issue": recommended_issue,
        "plans": plans,
        "trends": trends,
        "scoreboard": score_table,
        "back_scoreboard": back_scores,
        "top_front": top_numbers,
        "capital": capital,
        "storage": storage_status,
    }


@app.get("/dashboard/ssq")
@app.get("/api/ssq/dashboard")
def ssq_dashboard(
    budget: int = Query(default=20, ge=2),
    last_prize: float = Query(default=0, ge=0),
    strategy: str | None = Query(default="balanced", pattern="^(conservative|balanced|aggressive)$"),
    mode: str | None = Query(default=None, pattern="^(single|dantuo|auto)$"),
    principal: float = Query(default=1000, ge=0),
    balance: float | None = Query(default=None, ge=0),
    level_units: int = Query(default=1, ge=1, le=4),
    window: int = Query(default=100, ge=30, le=200),
) -> dict:
    return build_ssq_payload(
        budget=budget,
        last_prize=last_prize,
        strategy=strategy,
        mode=mode,
        principal=principal,
        balance=balance,
        level_units=level_units,
        window=window,
    )


@app.post("/generate/ssq")
def generate_ssq(request: GenerateRequest) -> dict:
    plans = build_ssq_payload(
        budget=request.budget,
        last_prize=request.last_prize,
        strategy=request.strategy,
        mode=request.mode,
        principal=request.principal,
        balance=request.balance,
        level_units=request.level_units,
        window=request.window,
        variant=request.variant,
    )["plans"]
    if not plans:
        raise HTTPException(status_code=400, detail="此预算下无法生成方案")
    return plans[0]


@app.post("/plan/ssq")
def plan_ssq(request: GenerateRequest) -> dict:
    return generate_ssq(request)


@app.get("/records/ssq")
def records_ssq() -> list[dict]:
    try:
        return load_ssq_records()
    except Exception:
        return []


@app.delete("/records/ssq/{record_id}")
def delete_record_ssq(record_id: str) -> dict:
    deleted = delete_ssq_record_db(record_id)
    return {"status": "ok", "deleted": deleted, "id": record_id}


@app.post("/records/ssq")
def create_record_ssq(request: RecordRequest) -> dict:
    record = {
        "id": f"ssq-{datetime.now(timezone.utc).timestamp()}",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "budget": request.budget,
        "strategy": request.strategy,
        "latest_issue": request.latest_issue,
        "plan": request.plan,
    }
    records = save_ssq_record(record)
    return {"status": "ok", "record": record, "count": len(records)}


@app.get("/review/ssq")
def review_ssq(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    try:
        payload = build_ssq_review(load_ssq_records(), load_ssq_history(), limit=limit)
        save_ssq_review_results(payload.get("items", []))
        return payload
    except Exception as exc:
        return {
            "summary": {
                "records": 0,
                "reviewed": 0,
                "pending": 0,
                "total_cost": 0,
                "hit_records": 0,
                "record_hit_rate": 0.0,
                "best_hit": "-",
                "best_prize_label": "-",
            },
            "items": [],
            "disclaimer": f"SSQ复盘数据暂不可用，已跳过异常记录。原因：{exc}",
        }


@app.get("/backtest/ssq")
@app.get("/api/ssq/backtest")
def backtest_ssq_api(
    budget: int = Query(default=20, ge=2),
    strategy: str = Query(default="balanced", pattern="^(conservative|balanced|aggressive)$"),
    periods: int = Query(default=100, ge=5, le=500),
    window: int = Query(default=100, ge=30, le=200),
) -> dict:
    return build_ssq_backtest(
        load_ssq_history(),
        budget=budget,
        strategy=strategy,
        periods=periods,
        window=window,
    )


@app.get("/data/ssq/status")
def ssq_data_status_api() -> dict:
    load_ssq_history()
    return ssq_data_status()


@app.get("/data/ssq/draws")
def ssq_draws(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    issue: str | None = Query(default=None),
) -> dict:
    return search_ssq_draws(limit=limit, offset=offset, issue=issue)


@app.get("/data/ssq/template")
def ssq_template() -> Response:
    csv_text = "issue,date,f1,f2,f3,f4,f5,f6,b1\n2025001,2025-01-01,5,10,15,20,25,30,7\n"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ssq_history_template.csv"},
    )


@app.post("/data/ssq/import")
async def import_ssq_history(
    file: UploadFile = File(...),
    mode: str = Query(default="replace", pattern="^(replace|append)$"),
) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
        count = save_ssq_history(csv_text, mode=mode)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV 必须为 UTF-8 编码") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "filename": file.filename,
        "mode": mode,
        "rows": count,
    }


@app.post("/data/ssq/sync")
def sync_ssq_history(
    source: str = Query(default="78500", pattern="^(auto|cwl|78500)$"),
    full: bool = Query(default=False),
) -> dict:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "update_ssq_history.py"),
        "--source",
        source,
        "--mode",
        "replace" if full else "append",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="双色球数据同步超时，请稍后重试。") from exc

    output = (result.stdout or result.stderr).strip()
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = {"status": "failed", "message": output or "同步脚本没有返回有效结果"}

    if result.returncode != 0:
        raise HTTPException(status_code=502, detail=payload.get("message", "双色球数据同步失败"))
    return {"status": "ok", "sync": payload, "data_status": ssq_data_status()}
