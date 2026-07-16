from __future__ import annotations

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"
DLT_PRIZE_PATH = DATA_DIR / "dlt_prizes.json"
SSQ_PRIZE_PATH = DATA_DIR / "ssq_prizes.json"


def load_prize_snapshot(scene: str) -> dict:
    path = SSQ_PRIZE_PATH if scene.upper() == "SSQ" else DLT_PRIZE_PATH
    if not path.exists():
        return {"source": "", "synced_at": "", "issues": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"source": "", "synced_at": "", "issues": {}}
    return payload if isinstance(payload, dict) else {"source": "", "synced_at": "", "issues": {}}


def prize_financials(distribution: dict[str, int], issue_prizes: dict | None, cost: float, appended: bool = False) -> dict:
    prizes = (issue_prizes or {}).get("prizes", {})
    additional_prizes = (issue_prizes or {}).get("additional_prizes", {})
    total = 0
    missing_labels = []
    for label, count in distribution.items():
        amount = prizes.get(label)
        if not isinstance(amount, (int, float)) or amount < 0:
            missing_labels.append(label)
            continue
        total += int(count) * amount
        if appended:
            additional_amount = additional_prizes.get(label)
            if not isinstance(additional_amount, (int, float)) or additional_amount < 0:
                missing_labels.append(f"{label}(追加)")
            else:
                total += int(count) * additional_amount
    complete = not missing_labels
    net = total - cost
    roi = round((net / cost) * 100, 2) if cost and complete else None
    return {
        "prize_amount": total,
        "prize_amount_complete": complete,
        "missing_prize_labels": missing_labels,
        "net_profit": net if complete else None,
        "roi": roi,
        "prize_source": (issue_prizes or {}).get("source", ""),
    }


def review_financial_summary(items: list[dict]) -> dict:
    reviewed = [item for item in items if item.get("status") == "reviewed"]
    total_cost = sum(float(item.get("cost", 0)) for item in reviewed)
    total_prize = sum(float(item.get("prize_amount", 0)) for item in reviewed)
    complete = all(item.get("prize_amount_complete", False) for item in reviewed)
    net = total_prize - total_cost if complete else None
    roi = round((net / total_cost) * 100, 2) if complete and total_cost else None
    return {
        "total_prize": total_prize,
        "net_profit": net,
        "roi": roi,
        "roi_complete": complete,
    }
