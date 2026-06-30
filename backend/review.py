from __future__ import annotations

from itertools import combinations


def prize_label(front_hits: int, back_hits: int) -> str:
    if front_hits == 5 and back_hits == 2:
        return "一等奖"
    if front_hits == 5 and back_hits == 1:
        return "二等奖"
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
                "prize_label": prize_label(front_hits, back_hits),
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
                "prize_label": prize_label(front_hits, back_hits),
            }
            if not best or (front_hits + back_hits, front_hits, back_hits) > (
                best["front_hits"] + best["back_hits"],
                best["front_hits"],
                best["back_hits"],
            ):
                best = current

    return best


def review_plan(plan: dict, draw: dict) -> dict:
    if plan.get("mode") == "dantuo":
        best = best_dantuo_hit(plan, draw)
        rows = [best] if best else []
    else:
        rows, best = review_single(plan, draw)

    hit_tickets = [row for row in rows if row.get("prize_label") != "未命中固定奖级"]
    return {
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
    }


def build_review(records: list[dict], history: list[dict], limit: int = 20) -> dict:
    items = []
    for record in records[:limit]:
        draw = next_draw(history, record.get("latest_issue"))
        if not draw:
            items.append(
                {
                    "record_id": record.get("id"),
                    "saved_at": record.get("saved_at"),
                    "latest_issue": record.get("latest_issue"),
                    "status": "pending",
                    "message": "推荐期之后暂无下一期开奖数据，暂不能复盘。",
                }
            )
            continue

        result = review_plan(record.get("plan", {}), draw)
        items.append(
            {
                "record_id": record.get("id"),
                "saved_at": record.get("saved_at"),
                "latest_issue": record.get("latest_issue"),
                "strategy": record.get("strategy"),
                "budget": record.get("budget"),
                "status": "reviewed",
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
        },
        "items": items,
        "disclaimer": "复盘只统计历史推荐与实际开奖号码的匹配结果，不代表未来命中概率或收益能力。",
    }
