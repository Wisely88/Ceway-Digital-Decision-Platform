from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .types import DltValidationError, Draw, Ticket


@dataclass(frozen=True)
class CollisionProfile:
    n_total_hits: tuple[int, ...]
    n_front_back: tuple[tuple[int, int, int], ...]
    history_start_issue: str | None = None
    history_end_issue: str | None = None

    @property
    def history_draw_count(self) -> int:
        return sum(self.n_total_hits)

    @property
    def max_total_hits(self) -> int:
        return max((index for index, count in enumerate(self.n_total_hits) if count), default=0)

    @property
    def scarcity_key(self) -> tuple[int, ...]:
        return tuple(self.n_total_hits[index] for index in range(7, 0, -1))

    def to_dict(self) -> dict:
        return {
            "n_total_hits": list(self.n_total_hits),
            "n_front_back": [list(row) for row in self.n_front_back],
            "history_draw_count": self.history_draw_count,
            "history_start_issue": self.history_start_issue,
            "history_end_issue": self.history_end_issue,
            "max_total_hits": self.max_total_hits,
            "scarcity_key": list(self.scarcity_key),
        }


def issue_key(issue: str) -> tuple[int, str]:
    value = str(issue)
    return (int(value), value) if value.isdigit() else (0, value)


def select_history(
    draws: Sequence[Draw],
    history_cutoff_issue: str,
    window: Mapping[str, object] | None = None,
) -> list[Draw]:
    if not history_cutoff_issue:
        raise DltValidationError("history_cutoff_issue 不能为空")
    cutoff_key = issue_key(history_cutoff_issue)
    eligible = sorted((draw for draw in draws if issue_key(draw.issue) <= cutoff_key), key=lambda draw: issue_key(draw.issue))
    spec = dict(window or {"mode": "all_history"})
    mode = str(spec.get("mode") or "all_history")
    if mode == "all_history":
        selected = eligible
    elif mode == "last_N":
        count = int(spec.get("count") or spec.get("n") or 0)
        if count < 1:
            raise DltValidationError("最近 N 期窗口的 N 必须大于 0")
        selected = eligible[-count:]
    elif mode == "custom":
        start_issue = str(spec.get("start_issue") or "")
        end_issue = str(spec.get("end_issue") or history_cutoff_issue)
        if not start_issue:
            raise DltValidationError("自定义窗口需要 start_issue")
        if issue_key(end_issue) > cutoff_key:
            raise DltValidationError("自定义窗口结束期不能超过历史截止期")
        selected = [draw for draw in eligible if issue_key(start_issue) <= issue_key(draw.issue) <= issue_key(end_issue)]
    else:
        raise DltValidationError("历史窗口仅支持 all_history、last_N 或 custom")
    if not selected:
        raise DltValidationError("历史窗口内没有可用开奖记录")
    return selected


def hit_pair(ticket: Ticket, draw: Draw) -> tuple[int, int]:
    return (
        (ticket.front_mask & draw.front_mask).bit_count(),
        (ticket.back_mask & draw.back_mask).bit_count(),
    )


def collision_profile(ticket: Ticket, draws: Sequence[Draw]) -> CollisionProfile:
    totals = [0] * 8
    matrix = [[0] * 3 for _ in range(6)]
    front_mask = ticket.front_mask
    back_mask = ticket.back_mask
    for draw in draws:
        front_hits = (front_mask & draw.front_mask).bit_count()
        back_hits = (back_mask & draw.back_mask).bit_count()
        matrix[front_hits][back_hits] += 1
        totals[front_hits + back_hits] += 1
    return CollisionProfile(
        n_total_hits=tuple(totals),
        n_front_back=tuple(tuple(row) for row in matrix),
        history_start_issue=draws[0].issue if draws else None,
        history_end_issue=draws[-1].issue if draws else None,
    )


def aggregate_collision_profiles(profiles: Sequence[CollisionProfile]) -> dict[str, object]:
    m_total = [0] * 8
    u_total = [0] * 8
    m_front_back = [[0] * 3 for _ in range(6)]
    u_front_back = [[0] * 3 for _ in range(6)]
    for profile in profiles:
        for index, count in enumerate(profile.n_total_hits):
            m_total[index] += count
            u_total[index] += int(count > 0)
        for front_hits in range(6):
            for back_hits in range(3):
                count = profile.n_front_back[front_hits][back_hits]
                m_front_back[front_hits][back_hits] += count
                u_front_back[front_hits][back_hits] += int(count > 0)
    return {
        "candidate_count": len(profiles),
        "m_total_hits": m_total,
        "u_total_hits": u_total,
        "m_front_back": m_front_back,
        "u_front_back": u_front_back,
    }
