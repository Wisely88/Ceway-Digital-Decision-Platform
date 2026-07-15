from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _plan(record: dict) -> dict:
    return record.get("plan") if isinstance(record.get("plan"), dict) else record


def _cost(record: dict) -> float:
    try:
        return max(0.0, float(_plan(record).get("cost", 0)))
    except (TypeError, ValueError):
        return 0.0


def _saved_at(record: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(record.get("saved_at", "")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _escalation_count(records: list[dict]) -> int:
    costs = [_cost(record) for record in sorted(records, key=lambda item: str(item.get("saved_at", "")))]
    return sum(1 for index in range(2, len(costs)) if costs[index - 2] < costs[index - 1] < costs[index])


def _market_pulse(snapshot: dict) -> dict:
    rows = [
        {"issue": issue, **item}
        for issue, item in (snapshot.get("issues") or {}).items()
        if isinstance(item.get("sales"), (int, float)) and item["sales"] > 0
    ][-20:]
    if not rows:
        return {
            "available": False,
            "label": "暂无官方销售额",
            "message": "当前数据源没有可用销售额，不以论坛讨论量代替真实市场数据。",
            "source": snapshot.get("source", ""),
            "series": [],
        }
    recent = rows[-5:]
    previous = rows[-10:-5]
    recent_avg = sum(row["sales"] for row in recent) / len(recent)
    previous_avg = sum(row["sales"] for row in previous) / len(previous) if previous else recent_avg
    change = round((recent_avg - previous_avg) / previous_avg * 100, 1) if previous_avg else 0.0
    label = "参与升温" if change >= 5 else "参与降温" if change <= -5 else "参与平稳"
    return {
        "available": True,
        "label": label,
        "change_percent": change,
        "latest_sales": rows[-1]["sales"],
        "latest_issue": rows[-1]["issue"],
        "source": rows[-1].get("source") or snapshot.get("source", ""),
        "message": "官方销售额只描述市场参与规模，不改变任何一注的中奖概率。",
        "series": [{"issue": row["issue"], "sales": row["sales"]} for row in rows],
    }


def build_behavior_profile(records: list[dict], review: dict, snapshot: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    recent = [record for record in records if (_saved_at(record) or now) >= cutoff]
    costs = [_cost(record) for record in records]
    recent_cost = sum(_cost(record) for record in recent)
    dantuo_count = sum(1 for record in records if _plan(record).get("mode") == "dantuo")
    escalations = _escalation_count(records)
    max_cost = max(costs, default=0)
    avg_cost = round(sum(costs) / len(costs), 2) if costs else 0
    risk_score = min(100, escalations * 30 + (20 if len(recent) >= 8 else 0) + (20 if avg_cost and max_cost >= avg_cost * 2 else 0))
    risk_level = "高" if risk_score >= 60 else "中" if risk_score >= 30 else "低"
    summary = review.get("summary") or {}
    signals = []
    if escalations:
        signals.append(f"发现 {escalations} 次连续三期加码")
    if len(recent) >= 8:
        signals.append("近30日保存方案频次偏高")
    if avg_cost and max_cost >= avg_cost * 2:
        signals.append("最大单次支出达到平均支出的两倍")
    if not signals:
        signals.append("未发现连续加码或异常高频保存")
    action = (
        "暂停新增方案，恢复基础预算并等待已保存方案完成复盘。"
        if risk_level == "高"
        else "保持固定预算，不因市场热度、遗漏或未中奖临时加码。"
    )
    return {
        "engine": "可解释规则引擎",
        "generated_at": now.isoformat(),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "metrics": {
            "record_count": len(records),
            "recent_count": len(recent),
            "recent_cost": round(recent_cost, 2),
            "average_cost": avg_cost,
            "maximum_cost": round(max_cost, 2),
            "dantuo_ratio": round(dantuo_count / len(records) * 100, 1) if records else 0,
            "escalation_count": escalations,
            "reviewed_count": summary.get("reviewed", 0),
            "historical_roi": summary.get("roi") if summary.get("roi_complete") else None,
        },
        "signals": signals,
        "action": action,
        "market": _market_pulse(snapshot),
        "disclaimer": "智能分析只解释历史投注行为与市场参与规模，不预测开奖号码或收益。",
    }
