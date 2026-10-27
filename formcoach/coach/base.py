"""Lớp gốc cho coach (Strategy: mẫu câu / LLM qua API / model local)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from formcoach.progress.goals import Goal, SetRecord, day_of, goal_on, streak
from formcoach.types import Session


@dataclass(frozen=True)
class CoachProgress:
    """Tiến độ trong ngày của hiệp, tính tới hết hiệp đó (backend dựng từ formcoach.progress)."""

    day_reps: int  # tổng rep trong ngày, gồm cả hiệp này
    daily_reps: int | None  # mục tiêu rep/ngày; None = chưa đặt
    streak: int  # số ngày đạt mục tiêu liên tiếp


def progress_after(
    records: Iterable[SetRecord], goals: Sequence[Goal], at: datetime
) -> CoachProgress:
    """Tiến độ ngày của hiệp ghi lúc `at`, chỉ tính các hiệp ghi tới hết hiệp đó.

    Mở lại kết quả cũ vẫn thấy đúng câu như lúc tập xong. `records` phải gồm cả hiệp này.
    Cùng ngày thì so giờ ghi trên đồng hồ (bỏ múi giờ): không so được chuỗi có và không có múi
    giờ với nhau, và các hiệp trong một ngày đều ghi bằng giờ của cùng điện thoại.
    """
    day, clock = at.date(), at.replace(tzinfo=None)
    before = [
        r
        for r in records
        if day_of(r) < day or (day_of(r) == day and r.recorded_at.replace(tzinfo=None) <= clock)
    ]
    goal = goal_on(day, goals)
    return CoachProgress(
        day_reps=sum(r.n_reps for r in before if day_of(r) == day),
        daily_reps=goal.daily_reps if goal else None,
        streak=streak(before, goals, day),
    )


class Coach(ABC):
    """Diễn giải kết quả một buổi tập thành nhận xét bằng chữ."""

    @abstractmethod
    def summarize(self, session: Session, progress: CoachProgress | None = None) -> str:
        """Tóm tắt buổi tập. Chỉ dựa trên số liệu trong `session` và `progress`, không bịa thêm.

        Dòng "Công cụ hỗ trợ, không thay huấn luyện viên." do giao diện luôn hiện, không nằm
        trong chữ trả về (để coach nào cũng không làm rơi mất nó).
        """
        ...
