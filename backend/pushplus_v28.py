from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Sequence

from multiregime_v28 import MULTIREGIME_V28_VERSION


PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"


def _fmt(numbers: Sequence[int]) -> str:
    return " ".join(f"{int(number):02d}" for number in numbers)


def _collision_text(profile: dict) -> str:
    if not profile:
        return "n/a"
    return " / ".join(f"N{key}={profile[key]}" for key in sorted(profile, key=lambda value: int(value)))


def build_v28_prediction_digest(plan: dict, *, target_issue: str) -> dict[str, Any]:
    if plan.get("generator_version") != MULTIREGIME_V28_VERSION:
        raise ValueError("PushPlus V2.8 renderer only accepts a V2.8 plan")
    items = list(plan.get("items", []))
    if not items:
        raise ValueError("V2.8 plan contains no tickets")

    game = str(plan.get("algorithm_version", "")).split("-")[2]
    core = dict(plan.get("core_reference", {}))
    fusion = plan["fusion_analysis"]["front"]
    scarcity = plan["scarcity_analysis"]["front"]
    fusion_pool = [int(row["number"]) for row in fusion["pool"]]
    scarcity_pool = [int(row["number"]) for row in scarcity["pool"]]
    fusion_top = fusion["full_combination_ranking"][:10]
    quotas = plan["track_diagnostics"]["quotas"]

    lines = [
        f"# CEWAY V2.8 {game} {target_issue}",
        "",
        f"- 历史截止期：**{plan.get('history_cutoff_issue')}**",
        f"- 模型：**{MULTIREGIME_V28_VERSION}**",
        f"- 完整组合来源配额：**Evidence {quotas.get('evidence', 0)} / Scarcity {quotas.get('scarcity', 0)} / Neutral {quotas.get('neutral', 0)} / Fusion {quotas.get('fusion', 0)}**",
        f"- Fusion 池（完整排序）：**{_fmt(fusion_pool)}**",
        f"- Fusion 合法完整组合数：**{fusion['combination_count_after_constraints']}**",
        f"- Scarcity 池（对照）：**{_fmt(scarcity_pool)}**",
        f"- 核心参考线：**{_fmt(core.get('front', []))} + {_fmt(core.get('back', []))}**（{core.get('origin_track')}轨）",
        "",
        "## 最终10注",
    ]
    for index, item in enumerate(items, 1):
        lines.append(
            f"{index}. [{item['origin_track']}] {_fmt(item['front'])} + {_fmt(item['back'])} | score={float(item['rank_score']):.4f} | track-rank={item['front_track_rank']}"
        )

    lines.extend(["", "## Fusion 完整组合 Top10"])
    for row in fusion_top:
        quality = row["fusion_quality"]
        lines.append(
            f"F{row['track_rank']}. {_fmt(row['numbers'])} | score={float(row['rank_score']):.4f} | coverage={float(quality['provenance_coverage']):.2f} | consensus={float(quality['consensus_strength']):.2f} | {_collision_text(row['collision']['profile'])}"
        )

    lines.extend(
        [
            "",
            "## V2.8 Fusion 冻结规则",
            "候选池先固定纳入 Evidence Top4 / Scarcity Top3 / Neutral Top3 的并集，再按 0.50/0.30/0.20 原长期权重融合分数补足池容量。",
            "组合质量：60%成员融合质量 + 25%来源覆盖 + 15%多轨共识；再按 55%组合质量 + 25%历史碰撞校准 + 20%结构质量排序。",
            "默认10注中固定20%为 Fusion 前瞻影子，其余80%继续按既有三轨比例分配；开奖后只回放冻结榜，不重算。",
            "Fusion、Scarcity 与碰撞均为历史数据研究特征，不代表未来中奖概率。",
        ]
    )

    markdown = "\n".join(lines)
    return {
        "game": game,
        "target_issue": str(target_issue),
        "history_cutoff_issue": str(plan.get("history_cutoff_issue")),
        "generator_version": MULTIREGIME_V28_VERSION,
        "core_reference": core,
        "fusion_pool": fusion_pool,
        "fusion_combination_count": fusion["combination_count_after_constraints"],
        "fusion_top10": fusion_top,
        "scarcity_pool": scarcity_pool,
        "items": items,
        "markdown": markdown,
    }


def build_pushplus_payload(digest: dict[str, Any], *, token: str, topic: str | None = None) -> dict[str, Any]:
    if not token:
        raise ValueError("PushPlus token is required")
    payload: dict[str, Any] = {
        "token": token,
        "title": f"CEWAY V2.8 {digest['game']} {digest['target_issue']}",
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
