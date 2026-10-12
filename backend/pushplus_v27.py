from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Sequence

from multiregime_v27 import MULTIREGIME_V27_VERSION


PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"


def _fmt(numbers: Sequence[int]) -> str:
    return " ".join(f"{int(number):02d}" for number in numbers)


def _collision_text(profile: dict) -> str:
    if not profile:
        return "n/a"
    return " / ".join(f"N{key}={profile[key]}" for key in sorted(profile, key=lambda value: int(value)))


def build_v27_prediction_digest(plan: dict, *, target_issue: str) -> dict[str, Any]:
    if plan.get("generator_version") != MULTIREGIME_V27_VERSION:
        raise ValueError("PushPlus V2.7 renderer only accepts a V2.7 plan")
    items = list(plan.get("items", []))
    if not items:
        raise ValueError("V2.7 plan contains no tickets")

    game = str(plan.get("algorithm_version", "")).split("-")[2]
    core = dict(plan.get("core_reference", {}))
    scarcity = plan["scarcity_analysis"]["front"]
    scarcity_pool = [int(row["number"]) for row in scarcity["pool"]]
    scarcity_top = scarcity["full_combination_ranking"][:10]
    quotas = plan["track_diagnostics"]["quotas"]

    lines = [
        f"# CEWAY V2.7 {game} {target_issue}",
        "",
        f"- 历史截止期：**{plan.get('history_cutoff_issue')}**",
        f"- 模型：**{MULTIREGIME_V27_VERSION}**",
        f"- 完整组合来源配额：**Evidence {quotas['evidence']} / Scarcity {quotas['scarcity']} / Neutral {quotas['neutral']}**",
        f"- 稀缺池（完整排序）：**{_fmt(scarcity_pool)}**",
        f"- 稀缺池合法组合数：**{scarcity['combination_count_after_constraints']}**",
        f"- 核心参考线：**{_fmt(core.get('front', []))} + {_fmt(core.get('back', []))}**（{core.get('origin_track')}轨）",
        "",
        "## 最终10注",
    ]
    for index, item in enumerate(items, 1):
        lines.append(
            f"{index}. [{item['origin_track']}] {_fmt(item['front'])} + {_fmt(item['back'])} | score={float(item['rank_score']):.4f} | track-rank={item['front_track_rank']}"
        )

    lines.extend(["", "## 稀缺组合 Top10"])
    for row in scarcity_top:
        lines.append(
            f"S{row['track_rank']}. {_fmt(row['numbers'])} | score={float(row['rank_score']):.4f} | min={float(row['track_quality']['minimum']):.4f} | {_collision_text(row['collision']['profile'])}"
        )

    lines.extend(
        [
            "",
            "## 稀缺池排序规则",
            "号码：scarcity_score↓ → gap_percentile↓ → divergence↓ → rarity7↓ → rarity20↓ → rarity3↓ → number↑。",
            "组合：0.70×平均稀缺度 + 0.30×最弱号码稀缺度；再与碰撞校准、结构质量合成 rank_score。",
            "完整稀缺组合榜会随冻结对象持久化，开奖后只回放、不重算；稀缺与碰撞均不代表未来中奖概率。",
        ]
    )

    markdown = "\n".join(lines)
    return {
        "game": game,
        "target_issue": str(target_issue),
        "history_cutoff_issue": str(plan.get("history_cutoff_issue")),
        "generator_version": MULTIREGIME_V27_VERSION,
        "core_reference": core,
        "scarcity_pool": scarcity_pool,
        "scarcity_combination_count": scarcity["combination_count_after_constraints"],
        "scarcity_top10": scarcity_top,
        "items": items,
        "markdown": markdown,
    }


def build_pushplus_payload(digest: dict[str, Any], *, token: str, topic: str | None = None) -> dict[str, Any]:
    if not token:
        raise ValueError("PushPlus token is required")
    payload: dict[str, Any] = {
        "token": token,
        "title": f"CEWAY V2.7 {digest['game']} {digest['target_issue']}",
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
