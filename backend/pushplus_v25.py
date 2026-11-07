from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from typing import Any, Sequence

from multiregime_v25 import ROLE_WEIGHTS


PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"


def _fmt(numbers: Sequence[int]) -> str:
    return " ".join(f"{int(number):02d}" for number in numbers)


def _top_regime_numbers(plan: dict, area: str, regime: str, count: int) -> list[int]:
    table = plan[f"{area}_regime_table"]
    ordered = sorted(table, key=lambda row: (row[f"{regime}_rank"], row["number"]))
    return [int(row["number"]) for row in ordered[:count]]


def _core_pool(plan: dict, count: int = 12) -> list[int]:
    usage: Counter[int] = Counter()
    for item in plan.get("items", []):
        usage.update(int(number) for number in item.get("front", []))
    ordered = sorted(usage, key=lambda number: (-usage[number], number))
    return ordered[:count]


def build_v25_prediction_digest(plan: dict, *, target_issue: str) -> dict[str, Any]:
    if plan.get("generator_version") != "multi-regime-exposure-v2.5":
        raise ValueError("PushPlus V2.5 renderer only accepts a V2.5 plan")
    items = list(plan.get("items", []))
    if not items:
        raise ValueError("V2.5 plan contains no tickets")

    game = str(plan.get("algorithm_version", "")).split("-")[2]
    first = items[0]
    core_pool = _core_pool(plan)
    evidence = _top_regime_numbers(plan, "front", "evidence", 6)
    scarcity = _top_regime_numbers(plan, "front", "scarcity", 6)
    neutral = _top_regime_numbers(plan, "front", "neutral", 6)

    role_text = "/".join(str(int(round(ROLE_WEIGHTS[key] * 100))) for key in ("evidence", "scarcity", "neutral"))
    core_line = f"{_fmt(first['front'])} + {_fmt(first['back'])}"

    lines = [
        f"# CEWAY V2.5 {game} {target_issue}",
        "",
        f"- 历史截止期：**{plan.get('history_cutoff_issue')}**",
        f"- 模型：**{plan.get('generator_version')}**",
        f"- 状态曝光：**Evidence / Scarcity / Neutral = {role_text}**",
        f"- 核心号码池：**{_fmt(core_pool)}**",
        f"- 核心参考线：**{core_line}**",
        "",
        "## 三轴号码",
        f"- Evidence：{_fmt(evidence)}",
        f"- Scarcity：{_fmt(scarcity)}",
        f"- Neutral：{_fmt(neutral)}",
        "",
        "## V2.5 组合",
    ]
    for index, item in enumerate(items, 1):
        lines.append(f"{index}. {_fmt(item['front'])} + {_fmt(item['back'])}")
    lines.extend(
        [
            "",
            "## 说明",
            "Evidence、Scarcity、Neutral 使用同一份 V2.5 预测对象生成；PushPlus 与本地输出不维护独立号码或独立文案。",
            "Scarcity 仅表示历史稀缺/覆盖状态，不代表未来中奖概率更高；本结果为研究辅助，不构成中奖承诺。",
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
        "core_reference": {"front": list(first["front"]), "back": list(first["back"])},
        "evidence_pool": evidence,
        "scarcity_pool": scarcity,
        "neutral_pool": neutral,
        "items": items,
        "markdown": markdown,
    }


def build_pushplus_payload(digest: dict[str, Any], *, token: str, topic: str | None = None) -> dict[str, Any]:
    if not token:
        raise ValueError("PushPlus token is required")
    payload: dict[str, Any] = {
        "token": token,
        "title": f"CEWAY V2.5 {digest['game']} {digest['target_issue']}",
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
