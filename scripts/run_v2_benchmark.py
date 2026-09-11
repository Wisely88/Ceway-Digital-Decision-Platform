from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from backtest import CEWAY_V2_ALGORITHM_VERSION, build_dlt_backtest, build_ssq_backtest  # noqa: E402
from engine import load_dlt_history, load_ssq_history  # noqa: E402


def compact_result(game: str, window: int, result: dict) -> dict:
    validation = result.get("v2_validation") or {}
    return {
        "game": game,
        "window": window,
        "config": result.get("config", {}),
        "summary": result.get("summary", {}),
        "baseline": result.get("baseline", {}),
        "validation": {
            "baseline_type": validation.get("baseline_type"),
            "periods": validation.get("periods"),
            "best_hit_uplift": validation.get("best_hit_uplift"),
            "record_hit_uplift": validation.get("record_hit_uplift"),
            "win_rate": validation.get("win_rate"),
            "loss_rate": validation.get("loss_rate"),
            "tie_rate": validation.get("tie_rate"),
            "status": validation.get("status"),
            "note": validation.get("note"),
        },
    }


def promotion_gate(rows: list[dict]) -> dict:
    if not rows:
        return {"decision": "HOLD", "reason": "no benchmark rows"}

    ci_lows = []
    means = []
    statuses = []
    for row in rows:
        validation = row.get("validation") or {}
        uplift = validation.get("best_hit_uplift") or {}
        if uplift.get("ci95_low") is not None:
            ci_lows.append(float(uplift["ci95_low"]))
        if uplift.get("mean") is not None:
            means.append(float(uplift["mean"]))
        statuses.append(validation.get("status"))

    if len(ci_lows) != len(rows):
        decision = "HOLD"
        reason = "one or more windows have no confidence interval"
    elif all(value > 0 for value in ci_lows):
        decision = "PROMOTE_CANDIDATE"
        reason = "all tested windows have best-hit uplift 95% CI above zero"
    elif all(status == "negative" for status in statuses):
        decision = "REJECT"
        reason = "all tested windows have negative validation status"
    else:
        decision = "HOLD"
        reason = "uplift is not stable across all tested windows"

    worst_row = min(
        rows,
        key=lambda row: float(((row.get("validation") or {}).get("best_hit_uplift") or {}).get("mean") or 0),
    )
    return {
        "decision": decision,
        "reason": reason,
        "tested_windows": [row["window"] for row in rows],
        "worst_window": worst_row["window"],
        "worst_mean_best_hit_uplift": ((worst_row.get("validation") or {}).get("best_hit_uplift") or {}).get("mean"),
        "minimum_ci95_low": min(ci_lows) if ci_lows else None,
        "mean_of_window_means": round(sum(means) / len(means), 4) if means else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CEWAY-FWD-V2 real-history benchmark")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument("--windows", type=str, default="50,100,200")
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v2_benchmark.json")
    args = parser.parse_args()

    windows = [int(value.strip()) for value in args.windows.split(",") if value.strip()]
    dlt_history = load_dlt_history()
    ssq_history = load_ssq_history()
    rows = []

    for game, history, builder in (
        ("DLT", dlt_history, build_dlt_backtest),
        ("SSQ", ssq_history, build_ssq_backtest),
    ):
        for window in windows:
            print(f"Running {game}: periods={args.periods}, window={window}, baseline_seeds={args.baseline_seeds}", flush=True)
            result = builder(
                history,
                budget=args.budget,
                strategy=args.strategy,
                periods=args.periods,
                window=window,
                baseline_seeds=args.baseline_seeds,
            )
            rows.append(compact_result(game, window, result))

    dlt_rows = [row for row in rows if row["game"] == "DLT"]
    ssq_rows = [row for row in rows if row["game"] == "SSQ"]
    report = {
        "schema_version": "ceway.v2.benchmark.1",
        "algorithm_version": CEWAY_V2_ALGORITHM_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "periods": args.periods,
            "windows": windows,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "data": {
            "DLT": {
                "history_count": len(dlt_history),
                "latest_issue": dlt_history[-1]["issue"] if dlt_history else None,
            },
            "SSQ": {
                "history_count": len(ssq_history),
                "latest_issue": ssq_history[-1]["issue"] if ssq_history else None,
            },
        },
        "rows": rows,
        "gates": {
            "DLT": promotion_gate(dlt_rows),
            "SSQ": promotion_gate(ssq_rows),
        },
        "interpretation": (
            "PROMOTE_CANDIDATE is only a research gate: every tested window must have a best-hit uplift "
            "95% Bootstrap CI above zero. It does not prove future lottery predictability and does not auto-deploy parameters."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["gates"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
