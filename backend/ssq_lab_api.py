from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine import load_ssq_history
from ssq_lab import SsqLabValidationError, analyze_tickets, generate_model, generate_random


router = APIRouter(prefix="/api/v1/lottery/ssq", tags=["双色球实验室"])


class WindowSpec(BaseModel):
    mode: Literal["all_history", "last_N", "custom"] = "all_history"
    count: int | None = Field(default=None, ge=1)
    start_issue: str | None = None
    end_issue: str | None = None


class TicketInput(BaseModel):
    front: list[int]
    back: list[int]


class CollisionRequest(BaseModel):
    history_cutoff_issue: str
    window: WindowSpec = Field(default_factory=WindowSpec)
    tickets: list[TicketInput] = Field(min_length=1, max_length=200)


class ModelRequest(BaseModel):
    target_issue: str
    history_cutoff_issue: str
    history_window: WindowSpec = Field(default_factory=lambda: WindowSpec(mode="last_N", count=120))
    front_pool_size: int = Field(default=10, ge=6, le=12)
    back_pool_size: int = Field(default=4, ge=1, le=8)
    output_count: int = Field(default=8, ge=1, le=50)


class RandomRequest(BaseModel):
    target_issue: str
    history_cutoff_issue: str
    count: int = Field(default=8, ge=1, le=200)
    seed: int | None = None


def _window(value: WindowSpec) -> dict:
    return value.model_dump(exclude_none=True)


def _error(exc: Exception) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rules")
def rules() -> dict:
    return {"name": "双色球", "code": "SSQ", "front": {"min": 1, "max": 33, "pick": 6}, "back": {"min": 1, "max": 16, "pick": 1}, "base_unit_yuan": 2}


@router.post("/collisions/analyze")
def collisions(request: CollisionRequest) -> dict:
    try:
        return analyze_tickets(load_ssq_history(), request.history_cutoff_issue, _window(request.window), [ticket.model_dump() for ticket in request.tickets])
    except (SsqLabValidationError, ValueError) as exc:
        _error(exc)


@router.post("/generate/model")
def model(request: ModelRequest) -> dict:
    try:
        return generate_model(
            load_ssq_history(),
            target_issue=request.target_issue,
            cutoff=request.history_cutoff_issue,
            window=_window(request.history_window),
            front_pool_size=request.front_pool_size,
            back_pool_size=request.back_pool_size,
            output_count=request.output_count,
        )
    except (SsqLabValidationError, ValueError) as exc:
        _error(exc)


@router.post("/generate/random")
def random_run(request: RandomRequest) -> dict:
    try:
        return generate_random(load_ssq_history(), target_issue=request.target_issue, cutoff=request.history_cutoff_issue, count=request.count, seed=request.seed)
    except (SsqLabValidationError, ValueError) as exc:
        _error(exc)
