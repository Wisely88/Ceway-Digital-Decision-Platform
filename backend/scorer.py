from __future__ import annotations


def normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0
    return round((value / max_value) * 100, 2)


def balance_score(number: int) -> float:
    odd_score = 100 if number % 2 == 1 else 92
    size_score = 100 if 10 <= number <= 28 else 84
    edge_penalty = 8 if number in {1, 2, 34, 35} else 0
    return round(max(0, (odd_score + size_score) / 2 - edge_penalty), 2)


def score_front_numbers(trends: dict) -> list[dict]:
    heat_by_number = {item["number"]: item["count"] for item in trends["hot_front"]}
    missing_by_number = {item["number"]: item["missing"] for item in trends["omissions"]}
    max_heat = max(heat_by_number.values() or [0])
    max_missing = max(missing_by_number.values() or [0])
    rows = []

    for number in range(1, 36):
        heat = normalize(heat_by_number.get(number, 0), max_heat)
        missing = normalize(missing_by_number.get(number, 0), max_missing)
        balanced = balance_score(number)
        total = round(heat * 0.4 + missing * 0.3 + balanced * 0.3, 2)
        explanation = (
            f"热度{heat}分、遗漏{missing}分、均衡{balanced}分；"
            f"综合评分按 0.4/0.3/0.3 加权得到 {total}。"
        )
        rows.append(
            {
                "number": number,
                "heat_count": heat_by_number.get(number, 0),
                "missing_periods": missing_by_number.get(number, 0),
                "heat_score": heat,
                "missing_score": missing,
                "balance_score": balanced,
                "total_score": total,
                "explanation": explanation,
            }
        )

    rows.sort(key=lambda item: (-item["total_score"], item["number"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def score_back_numbers(trends: dict) -> list[dict]:
    heat_by_number = {item["number"]: item["count"] for item in trends["hot_back"]}
    max_heat = max(heat_by_number.values() or [0])
    rows = []
    for number in range(1, 13):
        heat = normalize(heat_by_number.get(number, 0), max_heat)
        rows.append({"number": number, "score": heat})
    return sorted(rows, key=lambda item: (-item["score"], item["number"]))


def ssq_balance_score(number: int) -> float:
    odd_score = 100 if number % 2 == 1 else 92
    size_score = 100 if 9 <= number <= 24 else 84
    edge_penalty = 8 if number in {1, 2, 32, 33} else 0
    return round(max(0, (odd_score + size_score) / 2 - edge_penalty), 2)


def score_ssq_front_numbers(trends: dict) -> list[dict]:
    heat_by_number = {item["number"]: item["count"] for item in trends["hot_front"]}
    missing_by_number = {item["number"]: item["missing"] for item in trends["omissions"]}
    max_heat = max(heat_by_number.values() or [0])
    max_missing = max(missing_by_number.values() or [0])
    rows = []

    for number in range(1, 34):
        heat = normalize(heat_by_number.get(number, 0), max_heat)
        missing = normalize(missing_by_number.get(number, 0), max_missing)
        balanced = ssq_balance_score(number)
        total = round(heat * 0.4 + missing * 0.3 + balanced * 0.3, 2)
        explanation = (
            f"热度{heat}分、遗漏{missing}分、均衡{balanced}分；"
            f"综合评分按 0.4/0.3/0.3 加权得到 {total}。"
        )
        rows.append(
            {
                "number": number,
                "heat_count": heat_by_number.get(number, 0),
                "missing_periods": missing_by_number.get(number, 0),
                "heat_score": heat,
                "missing_score": missing,
                "balance_score": balanced,
                "total_score": total,
                "explanation": explanation,
            }
        )

    rows.sort(key=lambda item: (-item["total_score"], item["number"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def score_ssq_back_numbers(trends: dict) -> list[dict]:
    heat_by_number = {item["number"]: item["count"] for item in trends["hot_back"]}
    max_heat = max(heat_by_number.values() or [0])
    rows = []
    for number in range(1, 17):
        heat = normalize(heat_by_number.get(number, 0), max_heat)
        rows.append({"number": number, "score": heat})
    return sorted(rows, key=lambda item: (-item["score"], item["number"]))
