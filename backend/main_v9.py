from __future__ import annotations

from fastapi import Query

from engine import load_dlt_history, load_ssq_history
from main import app
from predictor_v9 import DLT, SSQ, freeze_prediction, generate_prediction_v9


def _windows(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


@app.get("/prediction/v9/dlt")
def prediction_v9_dlt(
    budget: int = Query(default=20, ge=2),
    seed: str = Query(default="ceway-v9"),
    cutoff_issue: str | None = Query(default=None),
    windows: str = Query(default="20,50,100,200"),
    candidate_band: int = Query(default=18, ge=5, le=35),
) -> dict:
    plan = generate_prediction_v9(
        load_dlt_history(), DLT, budget=budget, seed=seed,
        windows=_windows(windows), candidate_band=candidate_band,
        history_cutoff_issue=cutoff_issue,
    )
    return freeze_prediction(plan)


@app.get("/prediction/v9/ssq")
def prediction_v9_ssq(
    budget: int = Query(default=20, ge=2),
    seed: str = Query(default="ceway-v9"),
    cutoff_issue: str | None = Query(default=None),
    windows: str = Query(default="20,50,100,200"),
    candidate_band: int = Query(default=18, ge=6, le=33),
) -> dict:
    plan = generate_prediction_v9(
        load_ssq_history(), SSQ, budget=budget, seed=seed,
        windows=_windows(windows), candidate_band=candidate_band,
        history_cutoff_issue=cutoff_issue,
    )
    return freeze_prediction(plan)
