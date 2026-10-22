from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


FRONT_MIN, FRONT_MAX, FRONT_PICK = 1, 35, 5
BACK_MIN, BACK_MAX, BACK_PICK = 1, 12, 2


class DltValidationError(ValueError):
    pass


def sorted_unique(
    nums: Sequence[int],
    lo: int,
    hi: int,
    *,
    expected: int | None = None,
    label: str = "号码",
) -> tuple[int, ...]:
    values = tuple(sorted(int(value) for value in nums))
    if len(set(values)) != len(values):
        raise DltValidationError(f"{label}不能重复")
    if any(value < lo or value > hi for value in values):
        raise DltValidationError(f"{label}必须在 {lo} 至 {hi} 之间")
    if expected is not None and len(values) != expected:
        raise DltValidationError(f"{label}需要选择 {expected} 个，当前为 {len(values)} 个")
    return values


def number_mask(nums: Iterable[int]) -> int:
    result = 0
    for number in nums:
        if number < 1 or number > 63:
            raise DltValidationError("位掩码只支持 1 至 63")
        result |= 1 << (number - 1)
    return result


@dataclass(frozen=True)
class Draw:
    issue: str
    front: tuple[int, ...]
    back: tuple[int, ...]
    draw_date: str | None = None

    @classmethod
    def create(
        cls,
        issue: str,
        front: Sequence[int],
        back: Sequence[int],
        draw_date: str | None = None,
    ) -> "Draw":
        if not str(issue).strip():
            raise DltValidationError("期号不能为空")
        return cls(
            issue=str(issue).strip(),
            front=sorted_unique(front, FRONT_MIN, FRONT_MAX, expected=FRONT_PICK, label="前区号码"),
            back=sorted_unique(back, BACK_MIN, BACK_MAX, expected=BACK_PICK, label="后区号码"),
            draw_date=draw_date,
        )

    @classmethod
    def from_mapping(cls, row: dict) -> "Draw":
        return cls.create(row["issue"], row["front"], row["back"], row.get("date") or row.get("draw_date"))

    @property
    def front_mask(self) -> int:
        return number_mask(self.front)

    @property
    def back_mask(self) -> int:
        return number_mask(self.back)

    def to_dict(self) -> dict:
        return {"issue": self.issue, "date": self.draw_date, "front": list(self.front), "back": list(self.back)}


@dataclass(frozen=True)
class Ticket:
    front: tuple[int, ...]
    back: tuple[int, ...]

    @classmethod
    def create(cls, front: Sequence[int], back: Sequence[int]) -> "Ticket":
        return cls(
            front=sorted_unique(front, FRONT_MIN, FRONT_MAX, expected=FRONT_PICK, label="前区号码"),
            back=sorted_unique(back, BACK_MIN, BACK_MAX, expected=BACK_PICK, label="后区号码"),
        )

    @property
    def front_mask(self) -> int:
        return number_mask(self.front)

    @property
    def back_mask(self) -> int:
        return number_mask(self.back)

    def to_dict(self) -> dict:
        return {"front": list(self.front), "back": list(self.back)}
