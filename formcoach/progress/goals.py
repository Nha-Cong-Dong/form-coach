"""Mục tiêu rep mỗi ngày và streak, tính lúc đọc từ các hiệp đã chấm (không lưu cờ "đã xong").

Ngày của một hiệp là ngày trong `recorded_at` theo múi giờ của chính chuỗi đó: web ghi giờ địa
phương của điện thoại kèm offset, nên server không cần biết múi giờ người dùng.
Hàm không đọc đồng hồ: `today` truyền vào, để test được.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class SetRecord:
    """Một hiệp đã chấm (backend dựng từ bảng sessions/reps)."""

    recorded_at: datetime  # có múi giờ
    n_reps: int
    n_good: int


@dataclass(frozen=True)
class Goal:
    """Mục tiêu áp dụng từ `from_date` tới khi có mục tiêu mới hơn."""

    daily_reps: int
    from_date: date
    min_good_ratio: float | None = None  # None = không xét tỉ lệ rep đúng

    def __post_init__(self) -> None:
        if self.daily_reps <= 0:
            raise ValueError("daily_reps phải > 0")
        if self.min_good_ratio is not None and not 0 <= self.min_good_ratio <= 1:
            raise ValueError("min_good_ratio phải trong [0, 1]")


@dataclass(frozen=True)
class DayProgress:
    day: date
    n_reps: int
    n_good: int
    good_ratio: float | None  # None khi 0 rep
    goal: Goal | None
    met: bool


def day_of(record: SetRecord) -> date:
    """Ngày theo giờ địa phương đã ghi trong `recorded_at` (không đổi sang UTC)."""
    return record.recorded_at.date()


def goal_on(day: date, goals: Iterable[Goal]) -> Goal | None:
    """Mục tiêu có hiệu lực ngày `day`: `from_date` ≤ day, mới nhất."""
    valid = [g for g in goals if g.from_date <= day]
    return max(valid, key=lambda g: g.from_date) if valid else None


def _is_met(n_reps: int, n_good: int, goal: Goal | None) -> bool:
    if goal is None:  # chưa đặt mục tiêu: có tập là đạt
        return n_reps > 0
    if n_reps < goal.daily_reps:
        return False
    return goal.min_good_ratio is None or n_good / n_reps >= goal.min_good_ratio


def _totals(records: Iterable[SetRecord]) -> dict[date, tuple[int, int]]:
    totals: dict[date, tuple[int, int]] = {}
    for r in records:
        reps, good = totals.get(day_of(r), (0, 0))
        totals[day_of(r)] = (reps + r.n_reps, good + r.n_good)
    return totals


def daily_progress(
    records: Iterable[SetRecord], goals: Sequence[Goal], start: date, end: date
) -> list[DayProgress]:
    """Mỗi ngày từ `start` tới `end` (gồm cả hai đầu) một dòng, kể cả ngày không tập."""
    if start > end:
        raise ValueError("start phải ≤ end")
    totals = _totals(records)
    days = []
    for i in range((end - start).days + 1):
        day = start + timedelta(days=i)
        n_reps, n_good = totals.get(day, (0, 0))
        goal = goal_on(day, goals)
        days.append(
            DayProgress(
                day,
                n_reps,
                n_good,
                n_good / n_reps if n_reps else None,
                goal,
                _is_met(n_reps, n_good, goal),
            )
        )
    return days


def streak(records: Iterable[SetRecord], goals: Sequence[Goal], today: date) -> int:
    """Số ngày đạt mục tiêu liên tiếp tính lùi tới `today`.

    Hôm nay chưa đạt thì chuỗi chưa đứt (ngày chưa hết): đếm từ hôm qua.
    """
    totals = _totals(records)

    def met(day: date) -> bool:
        return _is_met(*totals.get(day, (0, 0)), goal_on(day, goals))

    day = today if met(today) else today - timedelta(days=1)
    count = 0
    while met(day):
        count += 1
        day -= timedelta(days=1)
    return count
