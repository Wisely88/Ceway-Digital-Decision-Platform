from __future__ import annotations

import copy
import math
import os
import sys
import threading
from collections import defaultdict
from pathlib import Path


DEFAULT_RUNTIME_ROOT = Path("/Volumes/wisely data/Projects/CEWAY-Lottery")
_PREVIEW_CACHE: dict[tuple[str, str, str], dict] = {}
_PREVIEW_CACHE_LOCK = threading.Lock()


class RuntimeUnavailable(RuntimeError):
    pass


def _runtime_root() -> Path:
    return Path(os.getenv("CEWAY_LOTTERY_ROOT", str(DEFAULT_RUNTIME_ROOT))).expanduser()


def _load_runtime(root: Path):
    if not (root / "ceway_lottery" / "runner.py").exists():
        raise RuntimeUnavailable(f"未找到推荐后台：{root}")
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from ceway_lottery.rules import SPECS, next_issue
        from ceway_lottery.runner import App
    except Exception as exc:  # pragma: no cover - depends on the local installation
        raise RuntimeUnavailable(f"推荐后台加载失败：{exc}") from exc
    return App, SPECS, next_issue


def _weighted_primary_rates(recommendations: list[dict]) -> dict[int, float]:
    rates: dict[int, float] = defaultdict(float)
    for candidate in recommendations:
        weight = max(float(candidate.get("final_score") or 0), 0.000001)
        for number in candidate.get("primary", []):
            rates[int(number)] += weight
    return rates


def _covers(candidate: dict, primary_dan: list[int], primary_tuo: list[int], secondary: list[int]) -> bool:
    primary = set(map(int, candidate.get("primary", [])))
    candidate_secondary = set(map(int, candidate.get("secondary", [])))
    return (
        set(primary_dan) <= primary
        and primary <= set(primary_dan) | set(primary_tuo)
        and candidate_secondary <= set(secondary)
    )


def select_budget_dantuo(payload: dict, min_cost: int = 18, max_cost: int = 24) -> dict | None:
    """Build one compact dantuo around the highest-ranked candidate.

    The official recommendation list remains unchanged. This helper merely
    expands its top candidate with high-consensus numbers until a valid ticket
    falls inside the requested cost window.
    """
    game = str(payload.get("game") or "").lower()
    recommendations = list(payload.get("recommendations") or [])
    if game not in {"dlt", "ssq"} or not recommendations:
        return None
    if min_cost < 2 or max_cost < min_cost:
        raise ValueError("预算区间无效")

    primary_pick = 5 if game == "dlt" else 6
    dan_count = 2 if game == "dlt" else 3
    secondary_pick = 2 if game == "dlt" else 1
    top = recommendations[0]
    rates = _weighted_primary_rates(recommendations)
    top_primary = list(map(int, top.get("primary", [])))
    primary_dan = sorted(
        sorted(top_primary, key=lambda number: (-rates[number], number))[:dan_count]
    )
    ranked_pool = sorted(rates, key=lambda number: (-rates[number], number))
    primary_tuo = [number for number in top_primary if number not in primary_dan]
    primary_tuo += [number for number in ranked_pool if number not in primary_dan and number not in primary_tuo]
    secondary = sorted(map(int, top.get("secondary", [])))
    if len(secondary) != secondary_pick:
        return None

    chosen_tuo: list[int] | None = None
    notes = 0
    for size in range(primary_pick - dan_count, len(primary_tuo) + 1):
        candidate_notes = math.comb(size, primary_pick - dan_count)
        cost = candidate_notes * 2
        if min_cost <= cost <= max_cost:
            chosen_tuo = sorted(primary_tuo[:size])
            notes = candidate_notes
            break
        if cost > max_cost:
            break
    if chosen_tuo is None:
        return None

    covered_indexes = [
        index
        for index, candidate in enumerate(recommendations, 1)
        if _covers(candidate, primary_dan, chosen_tuo, secondary)
    ]
    return {
        "type": "胆拖",
        "primary_dan": primary_dan,
        "primary_tuo": chosen_tuo,
        "secondary_dan": [],
        "secondary_tuo": secondary,
        "notes": notes,
        "cost": notes * 2,
        "covered_indexes": covered_indexes,
        "source_rank": 1,
    }


def get_runtime_recommendation(
    game: str,
    *,
    refresh: bool = False,
    min_cost: int = 18,
    max_cost: int = 24,
) -> dict:
    game = game.lower()
    if game not in {"dlt", "ssq"}:
        raise ValueError("仅支持大乐透和双色球")

    root = _runtime_root()
    App, specs, next_issue = _load_runtime(root)
    app = App(project_root=root)
    try:
        latest = app.db.latest_draw(game)
        if latest is None:
            raise RuntimeUnavailable(f"{specs[game].name}历史数据为空")
        target_issue = next_issue(game, latest.issue)
        frozen = app.db.get_freeze(game, target_issue)
        # 已冻结结果是正式版本，网页刷新不能绕过它生成另一套号码。
        if frozen:
            payload = frozen
            mode = "frozen"
        else:
            cache_key = (game, str(latest.issue), str(target_issue))
            with _PREVIEW_CACHE_LOCK:
                cached = None if refresh else _PREVIEW_CACHE.get(cache_key)
                if cached is None:
                    payload = app.recommend(game, target_issue, persist=False)
                    _PREVIEW_CACHE[cache_key] = copy.deepcopy(payload)
                    for key in list(_PREVIEW_CACHE):
                        if key[0] == game and key != cache_key:
                            _PREVIEW_CACHE.pop(key, None)
                else:
                    payload = copy.deepcopy(cached)
            mode = "preview"
        result = copy.deepcopy(payload)
        result["runtime"] = {
            "mode": mode,
            "pushed": bool(payload.get("_db_pushed")),
            "push_receipt": payload.get("_db_push_receipt"),
            "latest_issue": latest.issue,
            "latest_date": latest.draw_date,
            "root": str(root),
            "refresh_requested": bool(refresh),
        }
        result["budget_pick"] = select_budget_dantuo(result, min_cost=min_cost, max_cost=max_cost)
        return result
    finally:
        app.close()
