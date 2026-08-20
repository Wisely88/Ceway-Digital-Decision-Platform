from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from consensus_v22 import CONSENSUS_V22_VERSION  # noqa: E402
from engine import load_dlt_history, load_ssq_history  # noqa: E402
from scripts.run_v22_consensus_ablation import run_game  # noqa: E402


FRESH_V22_EXCLUDED_RECENT_POINTS = 150


def holdout_history(history: list[dict], excluded_recent_points: int) -> list[dict]:
    if excluded_recent_points <= 0:
        raise ValueError("excluded_recent_points must be positive")
    if len(history) <= excluded_recent_points + 32:
        raise ValueError("not enough history for a non-overlapping V2.2 holdout block")
    return history[:-excluded_recent_points]


def block_provenance(history: list[dict], periods: int, excluded_recent_points: int) -> dict:
    if periods <= 0:
        raise ValueError("periods must be positive")
    if excluded_recent_points < periods * 3:
        raise ValueError(
            "fresh V2.2 holdout must exclude three consumed blocks: development + V1 holdout + V2.1 holdout"
        )
    if len(history) < excluded_recent_points + periods + 1:
        raise ValueError("not enough history to describe V2.2 holdout boundaries")

    n = len(history)

    def outcome_block(end_exclusive: int, count: int) -> dict:
        start = end_exclusive - count
        rows = history[start:end_exclusive]
        return {
            "count": len(rows),
            "first_issue": rows[0]["issue"],
            "last_issue": rows[-1]["issue"],
        }

    return {
        "development_block": outcome_block(n, periods),
        "v1_consumed_holdout_block": outcome_block(n - periods, periods),
        "v21_consumed_holdout_block": outcome_block(n - periods * 2, periods),
        "v22_fresh_holdout_block": outcome_block(n - excluded_recent_points, periods),
        "blocks_overlap": False,
        "rule": (
            "V2.2 fresh holdout outcomes must be older than the recent development block and both previously consumed "
            "V1 and V2.1 holdout blocks."
        ),
    }


def fresh_holdout_gate(game: str, metrics: dict) -> dict:
    target_jaccard = 0.15 if game == "DLT" else 0.18
    structural_ok = metrics["candidate_front_mean_jaccard"] <= target_jaccard
    baseline_rows = metrics["baseline_comparisons"]
    legacy_positive_all = all(row["candidate_vs_legacy_best_hit"]["mean"] > 0 for row in baseline_rows)
    legacy_significant_two = sum(
        row["candidate_vs_legacy_best_hit"]["ci95_low"] > 0 for row in baseline_rows
    ) >= 2
    v21_nonnegative_two = sum(
        row["candidate_vs_v21_best_hit"]["mean"] >= 0 for row in baseline_rows
    ) >= 2
    random_not_significantly_worse = metrics["candidate_vs_random_best_hit"]["ci95_high"] >= 0

    significant_legacy_loss = any(
        row["candidate_vs_legacy_best_hit"]["ci95_high"] < 0 for row in baseline_rows
    )
    significant_random_loss = metrics["candidate_vs_random_best_hit"]["ci95_high"] < 0

    if structural_ok and legacy_positive_all and legacy_significant_two and v21_nonnegative_two and random_not_significantly_worse:
        decision = "ADVANCE_TO_FORWARD"
        reason = "V2.2 passes the pre-registered fresh holdout gate"
    elif not structural_ok:
        decision = "REJECT"
        reason = "V2.2 misses the pre-registered structural diversity target"
    elif significant_legacy_loss:
        decision = "REJECT"
        reason = "V2.2 is significantly worse than legacy in at least one frozen baseline comparison"
    elif significant_random_loss:
        decision = "REJECT"
        reason = "V2.2 is significantly worse than structure-matched random"
    else:
        decision = "HOLD"
        reason = "fresh holdout evidence is mixed; do not advance to forward validation"

    return {
        "decision": decision,
        "reason": reason,
        "target_front_mean_jaccard": target_jaccard,
        "structural_ok": structural_ok,
        "legacy_positive_all_windows": legacy_positive_all,
        "legacy_significant_in_at_least_two_windows": legacy_significant_two,
        "v21_nonnegative_in_at_least_two_windows": v21_nonnegative_two,
        "random_not_significantly_worse": random_not_significantly_worse,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh historical holdout for CEWAY V2.2 multi-window consensus")
    parser.add_argument("--periods", type=int, default=50)
    parser.add_argument(
        "--excluded-recent-points",
        type=int,
        default=FRESH_V22_EXCLUDED_RECENT_POINTS,
        help="Default 150 = dev50 + V1 holdout50 + V2.1 holdout50.",
    )
    parser.add_argument("--baseline-seeds", type=int, default=3)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--strategy", type=str, default="balanced")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "artifacts" / "ceway_v22_consensus_holdout.json")
    args = parser.parse_args()

    if args.excluded_recent_points < args.periods * 3:
        raise ValueError(
            "V2.2 fresh holdout refused: excluded_recent_points must cover dev + V1 holdout + V2.1 holdout"
        )

    full_histories = {"DLT": load_dlt_history(), "SSQ": load_ssq_history()}
    histories = {
        game: holdout_history(history, args.excluded_recent_points)
        for game, history in full_histories.items()
    }
    provenance = {
        game: block_provenance(history, args.periods, args.excluded_recent_points)
        for game, history in full_histories.items()
    }

    rows = []
    for game in ("DLT", "SSQ"):
        print(
            f"V2.2 FRESH HOLDOUT {game}: periods={args.periods}, excluded_recent_points={args.excluded_recent_points}",
            flush=True,
        )
        row = run_game(
            game=game,
            history=histories[game],
            periods=args.periods,
            baseline_seeds=args.baseline_seeds,
            budget=args.budget,
            strategy=args.strategy,
        )
        row["gate"] = fresh_holdout_gate(game, row["metrics"])
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=2), flush=True)

    report = {
        "schema_version": "ceway.v2.2.consensus-holdout.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "fresh_retrospective_holdout_excluding_three_consumed_blocks",
        "candidate_generator_version": CONSENSUS_V22_VERSION,
        "settings": {
            "periods": args.periods,
            "excluded_recent_points": args.excluded_recent_points,
            "baseline_seeds": args.baseline_seeds,
            "budget": args.budget,
            "strategy": args.strategy,
        },
        "block_provenance": provenance,
        "data": {
            game: {
                "full_history_count": len(full_histories[game]),
                "holdout_history_count": len(histories[game]),
                "full_latest_issue": full_histories[game][-1]["issue"],
                "holdout_cutoff_issue": histories[game][-1]["issue"],
            }
            for game in ("DLT", "SSQ")
        },
        "rows": rows,
        "all_games_advance": all(row["gate"]["decision"] == "ADVANCE_TO_FORWARD" for row in rows),
        "interpretation": (
            "This block is new promotion evidence for V2.2 only. Passing can authorize unchanged forward shadow validation, "
            "not production merge or predictive-certainty claims."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
