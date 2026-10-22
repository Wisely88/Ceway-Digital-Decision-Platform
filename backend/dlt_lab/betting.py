from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Mapping

from .types import (
    BACK_MAX,
    BACK_MIN,
    BACK_PICK,
    FRONT_MAX,
    FRONT_MIN,
    FRONT_PICK,
    DltValidationError,
    Ticket,
    sorted_unique,
)


DEFAULT_RULES = {
    "base_unit_yuan": 2,
    "addon_unit_yuan": 1,
    "multiplier_min": 1,
    "multiplier_max": 99,
    "max_ticket_base_yuan": 20000,
    "max_ticket_with_addon_yuan": 30000,
}


@dataclass(frozen=True)
class BetCalculation:
    expression_type: str
    expanded_bets: int
    unit_yuan: int
    multiplier: int
    addon: bool
    cost_yuan: int

    def to_dict(self) -> dict:
        return {
            "expression_type": self.expression_type,
            "expanded_bets": self.expanded_bets,
            "unit_yuan": self.unit_yuan,
            "multiplier": self.multiplier,
            "addon": self.addon,
            "cost_yuan": self.cost_yuan,
        }


def _numbers(expression: Mapping[str, object], key: str, lo: int, hi: int) -> tuple[int, ...]:
    raw = expression.get(key, [])
    if not isinstance(raw, (list, tuple)):
        raise DltValidationError(f"{key} 必须是号码数组")
    return sorted_unique(raw, lo, hi, label=key)


def _validate_disjoint(dan: tuple[int, ...], tuo: tuple[int, ...], label: str) -> None:
    if set(dan) & set(tuo):
        raise DltValidationError(f"{label}胆码和拖码不能重复")


def _compound_counts(expression_type: str, front: tuple[int, ...], back: tuple[int, ...]) -> int:
    if expression_type == "single":
        if len(front) != FRONT_PICK or len(back) != BACK_PICK:
            raise DltValidationError("单式必须恰好选择 5 个前区和 2 个后区号码")
    elif expression_type == "front_compound":
        if len(front) <= FRONT_PICK or len(back) != BACK_PICK:
            raise DltValidationError("前区复式需要超过 5 个前区号码并恰好选择 2 个后区号码")
    elif expression_type == "back_compound":
        if len(front) != FRONT_PICK or len(back) <= BACK_PICK:
            raise DltValidationError("后区复式需要恰好选择 5 个前区号码并超过 2 个后区号码")
    elif expression_type in {"double_compound", "compound"}:
        if len(front) < FRONT_PICK or len(back) < BACK_PICK or (len(front) == FRONT_PICK and len(back) == BACK_PICK):
            raise DltValidationError("双区复式至少有一个分区超过基本选号数量")
    else:
        raise DltValidationError("不支持的复式类型")
    return comb(len(front), FRONT_PICK) * comb(len(back), BACK_PICK)


def _dantuo_counts(expression_type: str, expression: Mapping[str, object]) -> int:
    front_dan = _numbers(expression, "front_dan", FRONT_MIN, FRONT_MAX)
    front_tuo = _numbers(expression, "front_tuo", FRONT_MIN, FRONT_MAX)
    back_dan = _numbers(expression, "back_dan", BACK_MIN, BACK_MAX)
    back_tuo = _numbers(expression, "back_tuo", BACK_MIN, BACK_MAX)
    _validate_disjoint(front_dan, front_tuo, "前区")
    _validate_disjoint(back_dan, back_tuo, "后区")
    if len(front_dan) > 4 or len(back_dan) > 1:
        raise DltValidationError("前区胆码最多 4 个，后区胆码最多 1 个")

    front_is_dantuo = expression_type in {"front_dantuo", "double_dantuo", "dantuo"}
    back_is_dantuo = expression_type in {"back_dantuo", "double_dantuo"}
    if expression_type == "dantuo":
        back_is_dantuo = bool(back_dan or back_tuo)

    if front_is_dantuo:
        if not front_dan or len(front_dan) + len(front_tuo) <= FRONT_PICK:
            raise DltValidationError("前区胆拖必须有胆码，且胆拖总数需要超过 5 个")
        need_front = FRONT_PICK - len(front_dan)
        if len(front_tuo) < need_front:
            raise DltValidationError("前区拖码不足以补足 5 个号码")
        front_bets = comb(len(front_tuo), need_front)
    else:
        front = _numbers(expression, "front", FRONT_MIN, FRONT_MAX)
        if len(front) != FRONT_PICK:
            raise DltValidationError("后区胆拖需要恰好选择 5 个固定前区号码")
        front_bets = 1

    if back_is_dantuo:
        if not back_dan or len(back_dan) + len(back_tuo) <= BACK_PICK:
            raise DltValidationError("后区胆拖必须有胆码，且胆拖总数需要超过 2 个")
        need_back = BACK_PICK - len(back_dan)
        if len(back_tuo) < need_back:
            raise DltValidationError("后区拖码不足以补足 2 个号码")
        back_bets = comb(len(back_tuo), need_back)
    else:
        back = _numbers(expression, "back", BACK_MIN, BACK_MAX)
        if len(back) != BACK_PICK:
            raise DltValidationError("前区胆拖需要恰好选择 2 个固定后区号码")
        back_bets = 1
    return front_bets * back_bets


def calculate_bet(
    expression: Mapping[str, object],
    *,
    addon: bool = False,
    multiplier: int = 1,
    rules: Mapping[str, int] | None = None,
) -> BetCalculation:
    current_rules = {**DEFAULT_RULES, **dict(rules or {})}
    expression_type = str(expression.get("type") or "single")
    if not current_rules["multiplier_min"] <= int(multiplier) <= current_rules["multiplier_max"]:
        raise DltValidationError("倍数必须在 1 至 99 之间")
    if expression_type in {"single", "front_compound", "back_compound", "double_compound", "compound"}:
        front = _numbers(expression, "front", FRONT_MIN, FRONT_MAX)
        back = _numbers(expression, "back", BACK_MIN, BACK_MAX)
        expanded_bets = _compound_counts(expression_type, front, back)
    elif expression_type in {"front_dantuo", "back_dantuo", "double_dantuo", "dantuo"}:
        expanded_bets = _dantuo_counts(expression_type, expression)
    else:
        raise DltValidationError("未知投注表达方式")
    unit = int(current_rules["base_unit_yuan"]) + (int(current_rules["addon_unit_yuan"]) if addon else 0)
    cost = expanded_bets * unit * int(multiplier)
    maximum = int(current_rules["max_ticket_with_addon_yuan"] if addon else current_rules["max_ticket_base_yuan"])
    if cost > maximum:
        raise DltValidationError(f"单票金额 {cost} 元超过配置上限 {maximum} 元")
    return BetCalculation(expression_type, expanded_bets, unit, int(multiplier), bool(addon), cost)


def expand_bet_expression(expression: Mapping[str, object], *, limit: int = 100000) -> list[Ticket]:
    expression_type = str(expression.get("type") or "single")
    if expression_type in {"single", "front_compound", "back_compound", "double_compound", "compound"}:
        front = _numbers(expression, "front", FRONT_MIN, FRONT_MAX)
        back = _numbers(expression, "back", BACK_MIN, BACK_MAX)
        _compound_counts(expression_type, front, back)
        front_options = combinations(front, FRONT_PICK)
        back_values = list(combinations(back, BACK_PICK))
    else:
        _dantuo_counts(expression_type, expression)
        front_dan = _numbers(expression, "front_dan", FRONT_MIN, FRONT_MAX)
        front_tuo = _numbers(expression, "front_tuo", FRONT_MIN, FRONT_MAX)
        back_dan = _numbers(expression, "back_dan", BACK_MIN, BACK_MAX)
        back_tuo = _numbers(expression, "back_tuo", BACK_MIN, BACK_MAX)
        if expression_type == "back_dantuo":
            front_options = [_numbers(expression, "front", FRONT_MIN, FRONT_MAX)]
        else:
            front_options = (tuple(sorted(front_dan + option)) for option in combinations(front_tuo, FRONT_PICK - len(front_dan)))
        if expression_type in {"back_dantuo", "double_dantuo"} or (expression_type == "dantuo" and back_dan):
            back_values = [tuple(sorted(back_dan + option)) for option in combinations(back_tuo, BACK_PICK - len(back_dan))]
        else:
            back_values = [_numbers(expression, "back", BACK_MIN, BACK_MAX)]
    tickets = []
    for front in front_options:
        for back in back_values:
            tickets.append(Ticket.create(front, back))
            if len(tickets) > limit:
                raise DltValidationError(f"展开注数超过安全上限 {limit}")
    return tickets
