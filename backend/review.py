from __future__ import annotations

from itertools import combinations

from prizes import prize_financials, review_financial_summary


DLT_LABELS = {
    "front": "前区",
    "back": "后区",
    "front_hits": "前区命中",
    "back_hits": "后区命中",
}

SSQ_LABELS = {
    "front": "红球",
    "back": "蓝球",
    "front_hits": "红球命中",
    "back_hits": "蓝球命中",
}


def prize_label(front_hits: int, back_hits: int, issue: str | None = None) -> str:
    new_rules = bool(issue and issue.isdigit() and int(issue) >= 26014)
    if front_hits == 5 and back_hits == 2:
        return "一等奖"
    if front_hits == 5 and back_hits == 1:
        return "二等奖"
    if new_rules:
        if front_hits == 5 or (front_hits == 4 and back_hits == 2):
            return "三等奖"
        if front_hits == 4 and back_hits == 1:
            return "四等奖"
        if front_hits == 4 or (front_hits == 3 and back_hits == 2):
            return "五等奖"
        if (front_hits == 3 and back_hits == 1) or (front_hits == 2 and back_hits == 2):
            return "六等奖"
        if (
            (front_hits == 3 and back_hits == 0)
            or (front_hits == 2 and back_hits == 1)
            or (front_hits == 1 and back_hits == 2)
            or (front_hits == 0 and back_hits == 2)
        ):
            return "七等奖"
        return "未命中固定奖级"
    if front_hits == 5:
        return "三等奖"
    if front_hits == 4 and back_hits == 2:
        return "四等奖"
    if front_hits == 4 and back_hits == 1:
        return "五等奖"
    if front_hits == 3 and back_hits == 2:
        return "六等奖"
    if front_hits == 4:
        return "七等奖"
    if (front_hits == 3 and back_hits == 1) or (front_hits == 2 and back_hits == 2):
        return "八等奖"
    if (
        (front_hits == 3 and back_hits == 0)
        or (front_hits == 2 and back_hits == 1)
        or (front_hits == 1 and back_hits == 2)
        or (front_hits == 0 and back_hits == 2)
    ):
        return "九等奖"
    return "未命中固定奖级"


def next_draw(history: list[dict], issue: str | None) -> dict | None:
    if not history:
        return None
    if not issue:
        return history[-1]
    for index, row in enumerate(history):
        if row["issue"] == issue:
            return history[index + 1] if index + 1 < len(history) else None
    return history[-1]


def hit_counts(front: list[int], back: list[int], draw: dict) -> tuple[int, int]:
    return len(set(front) & set(draw["front"])), len(set(back) & set(draw["back"]))


def review_single(plan: dict, draw: dict) -> tuple[list[dict], dict]:
    rows = []
    for index, item in enumerate(plan.get("items", []), start=1):
        front_hits, back_hits = hit_counts(item.get("front", []), item.get("back", []), draw)
        rows.append(
            {
                "ticket": index,
                "front": item.get("front", []),
                "back": item.get("back", []),
                "front_hits": front_hits,
                "back_hits": back_hits,
                "hit_label": f"{front_hits}+{back_hits}",
                "prize_label": prize_label(front_hits, back_hits, draw.get("issue")),
            }
        )
    best = max(rows, key=lambda item: (item["front_hits"] + item["back_hits"], item["front_hits"], item["back_hits"]), default=None)
    return rows, best or {}


def best_dantuo_hit(plan: dict, draw: dict) -> dict:
    dan = plan.get("front_dan", [])
    tuo = plan.get("front_tuo", [])
    back_pool = plan.get("back", [])
    need_tuo = max(0, 5 - len(dan))
    front_candidates = [sorted(dan + list(combo)) for combo in combinations(tuo, need_tuo)]
    back_candidates = [sorted(combo) for combo in combinations(back_pool, 2)]
    best = {}

    for front in front_candidates:
        for back in back_candidates:
            front_hits, back_hits = hit_counts(front, back, draw)
            current = {
                "ticket": 1,
                "front": front,
                "back": back,
                "front_hits": front_hits,
                "back_hits": back_hits,
                "hit_label": f"{front_hits}+{back_hits}",
                "prize_label": prize_label(front_hits, back_hits, draw.get("issue")),
            }
            if not best or (front_hits + back_hits, front_hits, back_hits) > (
                best["front_hits"] + best["back_hits"],
                best["front_hits"],
                best["back_hits"],
            ):
                best = current

    return best


def review_dantuo(plan: dict, draw: dict) -> tuple[list[dict], dict]:
    dan = plan.get("front_dan", [])
    tuo = plan.get("front_tuo", [])
    back_pool = plan.get("back", [])
    need_tuo = max(0, 5 - len(dan))
    rows = []

    for front_combo in combinations(tuo, need_tuo):
        front = sorted(dan + list(front_combo))
        for back_combo in combinations(back_pool, 2):
            back = sorted(back_combo)
            front_hits, back_hits = hit_counts(front, back, draw)
            rows.append(
                {
                    "ticket": len(rows) + 1,
                    "front": front,
                    "back": back,
                    "front_hits": front_hits,
                    "back_hits": back_hits,
                    "hit_label": f"{front_hits}+{back_hits}",
                    "prize_label": prize_label(front_hits, back_hits, draw.get("issue")),
                }
            )

    best = max(
        rows,
        key=lambda item: (item["front_hits"] + item["back_hits"], item["front_hits"], item["back_hits"]),
        default={},
    )
    return rows, best


def prize_distribution(rows: list[dict]) -> dict[str, int]:
    distribution = {}
    for row in rows:
        label = row.get("prize_label")
        if label and label != "未命中固定奖级":
            distribution[label] = distribution.get(label, 0) + 1
    return distribution


def review_plan(plan: dict, draw: dict) -> dict:
    if plan.get("mode") == "dantuo":
        rows, best = review_dantuo(plan, draw)
    else:
        rows, best = review_single(plan, draw)

    hit_tickets = [row for row in rows if row.get("prize_label") != "未命中固定奖级"]
    return {
        "scene": "DLT",
        "play_labels": plan.get("play_labels") or DLT_LABELS,
        "actual": {
            "issue": draw["issue"],
            "date": draw["date"],
            "front": draw["front"],
            "back": draw["back"],
        },
        "mode": plan.get("mode"),
        "cost": plan.get("cost", 0),
        "tickets": plan.get("tickets", len(rows)),
        "best": best,
        "details": rows[:20],
        "hit_tickets": len(hit_tickets),
        "hit_rate": round((len(hit_tickets) / max(1, plan.get("tickets", len(rows)))) * 100, 2),
        "prize_distribution": prize_distribution(rows),
    }


def build_review(records: list[dict], history: list[dict], limit: int = 20, prize_snapshot: dict | None = None) -> dict:
    items = []
    for record in records[:limit]:
        draw = next_draw(history, record.get("latest_issue"))
        if not draw:
            plan = record.get("plan", {})
            items.append(
                {
                    "record_id": record.get("id"),
                    "saved_at": record.get("saved_at"),
                    "latest_issue": record.get("latest_issue"),
                    "recommended_issue": plan.get("recommended_issue"),
                    "plan": plan,
                    "scene": plan.get("scene", "DLT"),
                    "play_labels": plan.get("play_labels") or DLT_LABELS,
                    "status": "pending",
                    "status_label": "待开奖",
                    "next_step": f"等待第 {plan.get('recommended_issue') or '下一'} 期开奖后复盘。",
                    "message": "推荐期之后暂无下一期开奖数据，暂不能复盘。",
                }
            )
            continue

        result = review_plan(record.get("plan", {}), draw)
        result.update(
            prize_financials(
                result.get("prize_distribution", {}),
                (prize_snapshot or {}).get("issues", {}).get(draw["issue"]),
                result.get("cost", 0),
                appended=bool(record.get("plan", {}).get("appended")),
                multiplier=record.get("plan", {}).get("multiplier") or 1,
            )
        )
        items.append(
            {
                "record_id": record.get("id"),
                "saved_at": record.get("saved_at"),
                "latest_issue": record.get("latest_issue"),
                "recommended_issue": record.get("plan", {}).get("recommended_issue"),
                "strategy": record.get("strategy"),
                "budget": record.get("budget"),
                "plan": record.get("plan", {}),
                "status": "reviewed",
                "status_label": "已复盘",
                "next_step": "已完成推荐号码与实际开奖号码对比。",
                **result,
            }
        )

    reviewed = [item for item in items if item["status"] == "reviewed"]
    total_cost = sum(item.get("cost", 0) for item in reviewed)
    hit_items = [item for item in reviewed if item.get("hit_tickets", 0) > 0]
    best_item = max(
        reviewed,
        key=lambda item: (
            item.get("best", {}).get("front_hits", 0) + item.get("best", {}).get("back_hits", 0),
            item.get("best", {}).get("front_hits", 0),
            item.get("best", {}).get("back_hits", 0),
        ),
        default=None,
    )

    financials = review_financial_summary(items)
    return {
        "summary": {
            "records": len(items),
            "reviewed": len(reviewed),
            "pending": len(items) - len(reviewed),
            "total_cost": total_cost,
            "hit_records": len(hit_items),
            "record_hit_rate": round((len(hit_items) / max(1, len(reviewed))) * 100, 2),
            "best_hit": best_item.get("best", {}).get("hit_label") if best_item else "-",
            "best_prize_label": best_item.get("best", {}).get("prize_label") if best_item else "-",
            **financials,
        },
        "items": items,
        "disclaimer": "复盘只统计历史推荐与实际开奖号码的匹配结果，不代表未来命中概率或收益能力。",
    }


# --- SSQ 双色球复盘函数 ---

def ssq_prize_label(front_hits: int, back_hits: int) -> str:
    """SSQ 奖级判定：6 个红球与 1 个蓝球，共六个奖级。"""
    if front_hits == 6 and back_hits == 1:
        return "一等奖"
    if front_hits == 6:
        return "二等奖"
    if front_hits == 5 and back_hits == 1:
        return "三等奖"
    if front_hits == 5 or (front_hits == 4 and back_hits == 1):
        return "四等奖"
    if front_hits == 4 or (front_hits == 3 and back_hits == 1):
        return "五等奖"
    if (front_hits == 2 and back_hits == 1) or (front_hits == 1 and back_hits == 1) or (front_hits == 0 and back_hits == 1):
        return "六等奖"
    return "未命中固定奖级"


def review_ssq_single(plan: dict, draw: dict) -> tuple[list[dict], dict]:
    rows = []
    for index, item in enumerate(plan.get("items", []), start=1):
        front_hits, back_hits = hit_counts(item.get("front", []), item.get("back", []), draw)
        rows.append(
            {
                "ticket": index,
                "front": item.get("front", []),
                "back": item.get("back", []),
                "front_hits": front_hits,
                "back_hits": back_hits,
                "hit_label": f"{front_hits}+{back_hits}",
                "prize_label": ssq_prize_label(front_hits, back_hits),
            }
        )
    best = max(rows, key=lambda item: (item["front_hits"] + item["back_hits"], item["front_hits"], item["back_hits"]), default=None)
    return rows, best or {}


def review_ssq_best_dantuo_hit(plan: dict, draw: dict) -> dict:
    dan = plan.get("front_dan", [])
    tuo = plan.get("front_tuo", [])
    back_pool = plan.get("back", [])
    need_tuo = max(0, 6 - len(dan))
    front_candidates = [sorted(dan + list(combo)) for combo in combinations(tuo, need_tuo)]
    back_candidates = [sorted([back]) for back in back_pool]
    best = {}

    for front in front_candidates:
        for back in back_candidates:
            front_hits, back_hits = hit_counts(front, back, draw)
            current = {
                "ticket": 1,
                "front": front,
                "back": back,
                "front_hits": front_hits,
                "back_hits": back_hits,
                "hit_label": f"{front_hits}+{back_hits}",
                "prize_label": ssq_prize_label(front_hits, back_hits),
            }
            if not best or (front_hits + back_hits, front_hits, back_hits) > (
                best["front_hits"] + best["back_hits"],
                best["front_hits"],
                best["back_hits"],
            ):
                best = current

    return best


def review_ssq_dantuo(plan: dict, draw: dict) -> tuple[list[dict], dict]:
    dan = plan.get("front_dan", [])
    tuo = plan.get("front_tuo", [])
    back_pool = plan.get("back", [])
    need_tuo = max(0, 6 - len(dan))
    rows = []

    for front_combo in combinations(tuo, need_tuo):
        front = sorted(dan + list(front_combo))
        for back_number in back_pool:
            back = [back_number]
            front_hits, back_hits = hit_counts(front, back, draw)
            rows.append(
                {
                    "ticket": len(rows) + 1,
                    "front": front,
                    "back": back,
                    "front_hits": front_hits,
                    "back_hits": back_hits,
                    "hit_label": f"{front_hits}+{back_hits}",
                    "prize_label": ssq_prize_label(front_hits, back_hits),
                }
            )

    best = max(
        rows,
        key=lambda item: (item["front_hits"] + item["back_hits"], item["front_hits"], item["back_hits"]),
        default={},
    )
    return rows, best


def review_ssq_plan(plan: dict, draw: dict) -> dict:
    if plan.get("mode") == "dantuo":
        rows, best = review_ssq_dantuo(plan, draw)
    else:
        rows, best = review_ssq_single(plan, draw)

    hit_tickets = [row for row in rows if row.get("prize_label") != "未命中固定奖级"]
    return {
        "scene": "SSQ",
        "play_labels": plan.get("play_labels") or SSQ_LABELS,
        "actual": {
            "issue": draw["issue"],
            "date": draw["date"],
            "front": draw["front"],
            "back": draw["back"],
        },
        "mode": plan.get("mode"),
        "cost": plan.get("cost", 0),
        "tickets": plan.get("tickets", len(rows)),
        "best": best,
        "details": rows[:20],
        "hit_tickets": len(hit_tickets),
        "hit_rate": round((len(hit_tickets) / max(1, plan.get("tickets", len(rows)))) * 100, 2),
        "prize_distribution": prize_distribution(rows),
    }


def build_ssq_review(records: list[dict], history: list[dict], limit: int = 20, prize_snapshot: dict | None = None) -> dict:
    items = []
    for record in records[:limit]:
        draw = next_draw(history, record.get("latest_issue"))
        if not draw:
            plan = record.get("plan", {})
            items.append(
                {
                    "record_id": record.get("id"),
                    "saved_at": record.get("saved_at"),
                    "latest_issue": record.get("latest_issue"),
                    "recommended_issue": plan.get("recommended_issue"),
                    "plan": plan,
                    "scene": plan.get("scene", "SSQ"),
                    "play_labels": plan.get("play_labels") or SSQ_LABELS,
                    "status": "pending",
                    "status_label": "待开奖",
                    "next_step": f"等待第 {plan.get('recommended_issue') or '下一'} 期开奖后复盘。",
                    "message": "推荐期之后暂无下一期开奖数据，暂不能复盘。",
                }
            )
            continue

        result = review_ssq_plan(record.get("plan", {}), draw)
        result.update(
            prize_financials(
                result.get("prize_distribution", {}),
                (prize_snapshot or {}).get("issues", {}).get(draw["issue"]),
                result.get("cost", 0),
                multiplier=record.get("plan", {}).get("multiplier") or 1,
            )
        )
        items.append(
            {
                "record_id": record.get("id"),
                "saved_at": record.get("saved_at"),
                "latest_issue": record.get("latest_issue"),
                "recommended_issue": record.get("plan", {}).get("recommended_issue"),
                "strategy": record.get("strategy"),
                "budget": record.get("budget"),
                "plan": record.get("plan", {}),
                "status": "reviewed",
                "status_label": "已复盘",
                "next_step": "已完成推荐号码与实际开奖号码对比。",
                **result,
            }
        )

    reviewed = [item for item in items if item["status"] == "reviewed"]
    total_cost = sum(item.get("cost", 0) for item in reviewed)
    hit_items = [item for item in reviewed if item.get("hit_tickets", 0) > 0]
    best_item = max(
        reviewed,
        key=lambda item: (
            item.get("best", {}).get("front_hits", 0) + item.get("best", {}).get("back_hits", 0),
            item.get("best", {}).get("front_hits", 0),
            item.get("best", {}).get("back_hits", 0),
        ),
        default=None,
    )

    financials = review_financial_summary(items)
    return {
        "summary": {
            "records": len(items),
            "reviewed": len(reviewed),
            "pending": len(items) - len(reviewed),
            "total_cost": total_cost,
            "hit_records": len(hit_items),
            "record_hit_rate": round((len(hit_items) / max(1, len(reviewed))) * 100, 2),
            "best_hit": best_item.get("best", {}).get("hit_label") if best_item else "-",
            "best_prize_label": best_item.get("best", {}).get("prize_label") if best_item else "-",
            **financials,
        },
        "items": items,
        "disclaimer": "复盘只统计历史推荐与实际开奖号码的匹配结果，不代表未来命中概率或收益能力。",
    }
