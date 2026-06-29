from __future__ import annotations


def capital_state(last_prize: float, principal: float = 1000, balance: float | None = None) -> dict:
    current_balance = principal if balance is None else balance
    if last_prize >= 10:
        level = 4
    elif last_prize >= 5:
        level = 2
    else:
        level = 1

    next_level = min(4, level * 2) if last_prize > 0 else 1
    return {
        "level": f"{level}注",
        "level_units": level,
        "next_level": f"{next_level}注",
        "principal": principal,
        "balance": current_balance,
        "profit": round(current_balance - principal, 2),
        "total_invested": 0,
        "total_prize": 0,
        "max_drawdown": 0,
    }

