from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Sequence

from multiregime_v25 import ROLE_WEIGHTS
from multiregime_v26 import MULTIREGIME_V26_VERSION


PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"


def _fmt(numbers: Sequence[int]) -> str:
    return " ".join(f"{int(number):02d}" for number in numbers)


def _top_regime_numbers(plan: dict, area: str, regime: str, count: int) -> list[int]:
    table = plan[f"{area}_regime_table"]
    ordered = sorted(table, key=lambda row: (row[f"{regime}_rank"], row["number"]))
    return [int(row["number"]) for row in ordered[:count]]


def _collision_text(profile: dict) -> str:
    if not profile:
        return "n/a"
    pairs = []
    for key in sorted(profile, key=lambda value: int(value)):
        pairs.append(f"N{key}={profile[key]}")
    return " / ".join(pairs)


def build_v26_prediction_digest(plan: dict, *, target_issue: str) -> dict[str, Any]:
    if plan.get("generator_version") != MULTIREGIME_V26_VERSION:
        raise ValueError("PushPlus V2.6 renderer only accepts a V2.6 plan")
    items = list(plan.get("items", []))
    if not items:
        raise ValueError("V2.6 plan contains no tickets")

    game = str(plan.get("algorithm_version", "")).split("-")[2]
    core_reference = dict(plan.get("core_reference", {}))
    core_pool = [int(number) for number in plan.get("core_pool", [])]
    evidence = _top_regime_numbers(plan, "front", "evidence", 6)
    scarcity = _top_regime_numbers(plan, "front", "scarcity", 6)
    neutral = _top_regime_numbers(plan, "front", "neutral", 6)
    role_text = "/".join(str(int(round(ROLE_WEIGHTS[key] * 100))) for key in ("evidence", "scarcity", "neutral"))
    core_line = f"{_fmt(core_reference.get('front', []))} + {_fmt(core_reference.get('back', []))}"
    core_collision = _collision_text(core_reference.get("front_collision", {}).get("profile", {}))

    lines = [
        f"# CEWAY V2.6 {game} {target_issue}",
        "",
        f"- 历史截止期：**{plan.get('history_cutoff_issue')}**",
        f"- 模型：**{plan.get('generator_version')}**",
        f"- 状态曝光：**Evidence / Scarcity / Neutral = {role_text}**",
        f"- 核心号码池：**{_fmt(core_pool)}**",
        f"- 核心参考线：**{core_line}**",
        f"- 核心线历史碰撞：**{core_collision}**",
        "",
        "## 三轴号码",
        f"- Evidence：{_fmt(evidence)}",
        f"- Scarcity：{_fmt(scarcity)}",
        f"- Neutral：{_fmt(neutral)}",
        "",
        "## V2.6 组合",
    ]
    for index, item in enumerate(items, 1):
        collision = _collision_text(item.get("front_collision", {}).get("profile", {}))
        lines.append(
            f"{index}. {_fmt(item['front'])} + {_fmt(item['back'])} | score={float(item['rank_score']):.4f} | {collision}"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "V2.6 保留 V2.5 的 Evidence/Scarcity/Neutral 三轴，同时把每一组完整候选组合的历史碰撞 N_k 纳入排序与组合审计。",
            "核心号码池来自模型三轴融合排名，不再按出票使用次数定义；核心参考线取实际综合 rank_score 最高组合，不再默认第一注。",
            "碰撞统计仅用于历史校准、结构与覆盖分析，不代表未来中奖概率；本结果为研究辅助，不构成中奖承诺。",
        ]
    )

    markdown = "\n".join(lines)
    return {
        "game": game,
        "target_issue": str(target_issue),
        "history_cutoff_issue": str(plan.get("history_cutoff_issue")),
        "generator_version": plan.get("generator_version"),
        "role_weights": dict(ROLE_WEIGHTS),
        "core_pool": core_pool,
        "core_reference": core_reference,
        "evidence_pool": evidence,
        "scarcity_pool": scarcity,
        "neutral_pool": neutral,
        "combination_collision_audit": plan.get("combination_collision_audit", {}),
        "items": items,
        "markdown": markdown,
    }


def build_pushplus_payload(digest: dict[str, Any], *, token: str, topic: str | None = None) -> dict[str, Any]:
    if not token:
        raise ValueError("PushPlus token is required")
    payload: dict[str, Any] = {
        "token": token,
        "title": f"CEWAY V2.6 {digest['game']} {digest['target_issue']}",
        "content": digest["markdown"],
        "template": "markdown",
    }
    if topic:
        payload["topic"] = topic
    return payload


def send_pushplus(
    digest: dict[str, Any],
    *,
    token: str | None = None,
    topic: str | None = None,
    endpoint: str = PUSHPLUS_ENDPOINT,
    timeout: int = 15,
) -> dict[str, Any]:
    resolved_token = token or os.environ.get("PUSHPLUS_TOKEN", "").strip()
    resolved_topic = topic if topic is not None else os.environ.get("PUSHPLUS_TOPIC", "").strip() or None
    payload = build_pushplus_payload(digest, token=resolved_token, topic=resolved_topic)
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"PushPlus request failed: {exc}") from exc
    if int(body.get("code", 0)) != 200:
        raise RuntimeError(f"PushPlus rejected message: {body}")
    return body
