from __future__ import annotations


STAKE_UNIT = 2
LEVELS = (1, 2, 4)


def clamp_level(level_units: int) -> int:
    if level_units <= 1:
        return 1
    if level_units <= 2:
        return 2
    return 4


def next_level_units(current_units: int, round_profit: float) -> int:
    if round_profit > 0:
        return min(4, current_units * 2)
    return 1


def drawdown_percent(peak_balance: float, balance: float) -> float:
    if peak_balance <= 0:
        return 0
    return round(max(0, (peak_balance - balance) / peak_balance * 100), 2)


def capital_state(
    last_prize: float,
    principal: float = 1000,
    balance: float | None = None,
    level_units: int = 1,
    peak_balance: float | None = None,
    max_drawdown: float = 0,
) -> dict:
    current_units = clamp_level(level_units)
    start_balance = principal if balance is None else balance
    stake = current_units * STAKE_UNIT
    prize = max(0, last_prize)
    ending_balance = round(start_balance - stake + prize, 2)
    round_profit = round(prize - stake, 2)
    profit = round(ending_balance - principal, 2)
    interrupted_profit = round(max(0, start_balance - principal), 2) if round_profit <= 0 else 0
    high_watermark = max(principal, peak_balance if peak_balance is not None else start_balance, ending_balance)
    current_drawdown = drawdown_percent(high_watermark, ending_balance)
    max_drawdown_value = max(max_drawdown, current_drawdown)
    next_units = next_level_units(current_units, round_profit)

    if round_profit > 0:
        transition = f"{current_units}注 -> {next_units}注：本轮盈利 {round_profit} 元，按 Anti-Martingale 赢后加码。"
    elif interrupted_profit > 0:
        transition = f"{current_units}注 -> 1注：本轮未盈利，中断已累积盈利 {interrupted_profit} 元，回到基础下注。"
    else:
        transition = f"{current_units}注 -> 1注：本轮未盈利，继续使用基础下注控制回撤。"

    return {
        "principal": principal,
        "balance": ending_balance,
        "profit": profit,
        "interrupted_profit": interrupted_profit,
        "max_drawdown": round(max_drawdown_value, 2),
        "current_drawdown": current_drawdown,
        "level": f"{current_units}注",
        "level_units": current_units,
        "next_level": f"{next_units}注",
        "next_level_units": next_units,
        "stake": stake,
        "last_prize": prize,
        "round_profit": round_profit,
        "total_invested": stake,
        "total_prize": prize,
        "transition": {
            "from": f"{current_units}注",
            "to": f"{next_units}注",
            "event": "win" if round_profit > 0 else "reset",
            "explanation": transition,
        },
        "transition_explanation": transition,
    }
