from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from capital import capital_state
from engine import calculate_trends, load_dlt_history, load_dlt_records, load_scenes, save_dlt_history, save_dlt_record
from generator import generate_plans, normalize_strategy
from scorer import score_back_numbers, score_front_numbers


app = FastAPI(title="Ceway v1.3 Decision Pipeline API")

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


class RecordRequest(BaseModel):
    budget: int = Field(ge=2)
    strategy: str
    latest_issue: str | None = None
    plan: dict


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
    )
    capital = capital_state(
        last_prize=last_prize,
        principal=principal,
        balance=balance,
        level_units=level_units,
    )
    top_numbers = [item["number"] for item in score_table[:5]]
    latest_row = history[-1] if history else None

    return {
        "scene": "DLT",
        "product": {
            "name": "策维",
            "english_name": "Ceway",
            "subtitle": "Digital Decision Platform",
            "framework": "Powered by CBGO Framework",
            "baseline": "v1.2 MVP",
            "version": "v1.3 Decision Pipeline",
        },
        "disclaimer": "策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
        "history_count": len(history),
        "latest_issue": latest_row["issue"] if latest_row else None,
        "data_status": {
            "source": "local_csv",
            "source_label": "本地 CSV",
            "path": "backend/data/dlt_history.csv",
            "latest_issue": latest_row["issue"] if latest_row else None,
            "latest_date": latest_row["date"] if latest_row else None,
            "is_sample": len(history) <= 30,
            "message": "当前走势分析基于本地 CSV 数据。请导入最新开奖 CSV 后再用于正式分析。",
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
    )["plans"]
    if not plans:
        raise HTTPException(status_code=400, detail="No plan can be generated within this budget")
    return plans[0]


@app.post("/plan/dlt")
def plan_dlt(request: GenerateRequest) -> dict:
    return generate_dlt(request)


@app.get("/records/dlt")
def records_dlt() -> list[dict]:
    return load_dlt_records()


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


@app.post("/data/dlt/import")
async def import_dlt_history(file: UploadFile = File(...)) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
        count = save_dlt_history(csv_text)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "filename": file.filename,
        "rows": count,
    }
