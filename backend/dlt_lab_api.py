from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import db
from dlt_lab import (
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
from dlt_lab.statistics import number_trends
from dlt_lab.storage import clone_run, compare_runs, freeze_run, get_candidate_profiles, get_run, list_runs, save_run, settle_run
from engine import load_dlt_history


router = APIRouter(prefix="/api/v1/lottery/dlt", tags=["大乐透实验室"])
ROOT_DIR = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT_DIR / "config" / "dlt_game_rules.json"


class WindowSpec(BaseModel):
    mode: Literal["all_history", "last_N", "custom"] = "all_history"
    count: int | None = Field(default=None, ge=1)
    start_issue: str | None = None
    end_issue: str | None = None


class TicketInput(BaseModel):
    front: list[int]
    back: list[int]


class DrawInput(TicketInput):
    issue: str
    date: str


class DrawImportRequest(BaseModel):
    draws: list[DrawInput]
    mode: Literal["append", "replace"] = "append"


class CollisionRequest(BaseModel):
    history_cutoff_issue: str
    window: WindowSpec = Field(default_factory=WindowSpec)
    tickets: list[TicketInput] = Field(min_length=1, max_length=1000)


class ModelGenerationRequest(BaseModel):
    target_issue: str
    history_cutoff_issue: str
    history_window: WindowSpec = Field(default_factory=WindowSpec)
    front_pool_size: int = Field(default=12, ge=5, le=18)
    back_pool_size: int = Field(default=5, ge=2, le=8)
    output_count: int = Field(default=10, ge=1, le=100)
    model_config_version: str = "ceway-dlt-collision-v1"
    ranking_mode: Literal["model", "scarcity"] = "model"


class RandomGenerationRequest(BaseModel):
    target_issue: str
    history_cutoff_issue: str | None = None
    count: int = Field(default=10, ge=1, le=1000)
    bet_expression: dict[str, Any] = Field(default_factory=lambda: {"type": "single"})
    addon: bool = False
    multiplier: int = Field(default=1, ge=1, le=99)
    seed: int | None = None


class PackageGenerationRequest(BaseModel):
    target_issue: str
    budget_yuan: int = Field(ge=2)
    template: Literal["dispersed_singles", "addon_singles", "small_compound", "dantuo", "mixed"] = "mixed"
    source: Literal["model", "random", "scarcity", "mixed"] = "random"
    addon: bool = False
    multiplier: int = Field(default=1, ge=1, le=99)
    seed: int | None = None
    history_cutoff_issue: str | None = None
    history_window: WindowSpec = Field(default_factory=lambda: WindowSpec(mode="last_N", count=120))


class BetCalculateRequest(BaseModel):
    expression: dict[str, Any]
    addon: bool = False
    multiplier: int = Field(default=1, ge=1, le=99)


def _draws() -> list[Draw]:
    return [Draw.from_mapping(row) for row in load_dlt_history()]


def _window(window: WindowSpec) -> dict:
    return window.model_dump(exclude_none=True)


def _raise_domain_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail="未找到该实验运行") from exc
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rules")
def rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


@router.get("/draws")
def draws(
    start_issue: str | None = None,
    end_issue: str | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
) -> dict:
    rows = load_dlt_history()
    if start_issue:
        rows = [row for row in rows if row["issue"] >= start_issue]
    if end_issue:
        rows = [row for row in rows if row["issue"] <= end_issue]
    return {"items": rows[-limit:], "total": len(rows), "limit": limit}


@router.post("/draws/import")
def import_draws(request: DrawImportRequest) -> dict:
    try:
        normalized = [Draw.create(row.issue, row.front, row.back, row.date).to_dict() for row in request.draws]
        issues = [row["issue"] for row in normalized]
        if len(set(issues)) != len(issues):
            raise DltValidationError("导入数据中存在重复期号")
        if request.mode == "replace":
            db.replace_dlt_draws(normalized)
        else:
            db.upsert_dlt_draws(normalized)
        return {"status": "ok", "mode": request.mode, "rows": len(normalized)}
    except (DltValidationError, ValueError) as exc:
        _raise_domain_error(exc)


@router.get("/statistics/numbers")
def statistics_numbers(
    history_cutoff_issue: str = Query(...),
    window: int = Query(default=120, ge=1, le=5000),
) -> dict:
    try:
        selected = select_history(_draws(), history_cutoff_issue, {"mode": "last_N", "count": window})
        return {
            "history_cutoff_issue": history_cutoff_issue,
            "history_draw_count": len(selected),
            "front": number_trends(selected, "front"),
            "back": number_trends(selected, "back"),
        }
    except DltValidationError as exc:
        _raise_domain_error(exc)


@router.post("/collisions/analyze")
def analyze_collisions(request: CollisionRequest) -> dict:
    try:
        history = select_history(_draws(), request.history_cutoff_issue, _window(request.window))
        tickets = [Ticket.create(ticket.front, ticket.back) for ticket in request.tickets]
        profiles = [collision_profile(ticket, history) for ticket in tickets]
        return {
            "history_cutoff_issue": request.history_cutoff_issue,
            "history": {"start_issue": history[0].issue, "end_issue": history[-1].issue, "draw_count": len(history)},
            "tickets": [
                {**ticket.to_dict(), "collision": profile.to_dict()}
                for ticket, profile in zip(tickets, profiles)
            ],
            "aggregate": aggregate_collision_profiles(profiles),
            "disclaimer": "历史碰撞次数只描述过去，不代表未来开奖概率。",
        }
    except DltValidationError as exc:
        _raise_domain_error(exc)


@router.post("/generate/model")
def generate_model(request: ModelGenerationRequest) -> dict:
    try:
        payload = generate_model_run(
            _draws(),
            target_issue=request.target_issue,
            history_cutoff_issue=request.history_cutoff_issue,
            history_window=_window(request.history_window),
            front_pool_size=request.front_pool_size,
            back_pool_size=request.back_pool_size,
            output_count=request.output_count,
            ranking_mode=request.ranking_mode,
        )
        return save_run(payload)
    except DltValidationError as exc:
        _raise_domain_error(exc)


@router.post("/generate/random")
def generate_random(request: RandomGenerationRequest) -> dict:
    try:
        history = _draws()
        cutoff = request.history_cutoff_issue or (history[-1].issue if history else None)
        return save_run(generate_random_run(
            target_issue=request.target_issue,
            history_cutoff_issue=cutoff,
            count=request.count,
            addon=request.addon,
            multiplier=request.multiplier,
            seed=request.seed,
            bet_expression=request.bet_expression,
        ))
    except DltValidationError as exc:
        _raise_domain_error(exc)


@router.post("/generate/package")
def generate_package(request: PackageGenerationRequest) -> dict:
    try:
        history = _draws()
        cutoff = request.history_cutoff_issue or (history[-1].issue if history else None)
        preferred_tickets = None
        if request.source != "random":
            if not cutoff:
                raise DltValidationError("模型来源的预算模板需要历史截止期")
            ranking_mode = "scarcity" if request.source == "scarcity" else "model"
            model_payload = generate_model_run(
                history,
                target_issue=request.target_issue,
                history_cutoff_issue=cutoff,
                history_window=_window(request.history_window),
                front_pool_size=10,
                back_pool_size=4,
                output_count=30,
                ranking_mode=ranking_mode,
            )
            preferred_tickets = [Ticket.create(ticket["front"], ticket["back"]) for ticket in model_payload["tickets"]]
        return save_run(generate_package_run(
            target_issue=request.target_issue,
            budget_yuan=request.budget_yuan,
            template=request.template,
            source=request.source,
            addon=request.addon,
            multiplier=request.multiplier,
            seed=request.seed,
            history_cutoff_issue=cutoff,
            source_tickets=preferred_tickets,
        ))
    except DltValidationError as exc:
        _raise_domain_error(exc)


@router.post("/bet/calculate")
def bet_calculate(request: BetCalculateRequest) -> dict:
    try:
        return calculate_bet(request.expression, addon=request.addon, multiplier=request.multiplier).to_dict()
    except DltValidationError as exc:
        _raise_domain_error(exc)


@router.get("/runs")
def runs(limit: int = Query(default=50, ge=1, le=500), target_issue: str | None = None) -> dict:
    items = list_runs(limit=limit, target_issue=target_issue)
    return {"items": items, "total": len(items)}


@router.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    try:
        return get_run(run_id)
    except KeyError as exc:
        _raise_domain_error(exc)


@router.get("/runs/{run_id}/candidates")
def run_candidates(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    try:
        return get_candidate_profiles(run_id, limit=limit, offset=offset)
    except KeyError as exc:
        _raise_domain_error(exc)


@router.post("/runs/{run_id}/freeze")
def freeze(run_id: str) -> dict:
    try:
        return freeze_run(run_id)
    except (KeyError, DltValidationError) as exc:
        _raise_domain_error(exc)


@router.post("/runs/{run_id}/clone")
def clone(run_id: str) -> dict:
    try:
        return clone_run(run_id)
    except KeyError as exc:
        _raise_domain_error(exc)


@router.post("/runs/{run_id}/settle")
def settle(run_id: str) -> dict:
    try:
        return settle_run(run_id)
    except (KeyError, LookupError, DltValidationError) as exc:
        _raise_domain_error(exc)


@router.get("/compare")
def compare(target_issue: str = Query(...), basis: Literal["ticket_count", "budget"] = "ticket_count") -> dict:
    try:
        return compare_runs(target_issue, basis)
    except DltValidationError as exc:
        _raise_domain_error(exc)
