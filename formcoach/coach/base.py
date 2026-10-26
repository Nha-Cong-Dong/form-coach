"""Lớp gốc cho coach (Strategy: mẫu câu / LLM qua API / model local)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from formcoach.types import Session


@dataclass(frozen=True)
class CoachProgress:
    """Tiến độ trong ngày của hiệp, tính tới hết hiệp đó (backend dựng từ formcoach.progress)."""

    day_reps: int  # tổng rep trong ngày, gồm cả hiệp này
    daily_reps: int | None  # mục tiêu rep/ngày; None = chưa đặt
    streak: int  # số ngày đạt mục tiêu liên tiếp


class Coach(ABC):
    """Diễn giải kết quả một buổi tập thành nhận xét bằng chữ."""

    @abstractmethod
    def summarize(self, session: Session, progress: CoachProgress | None = None) -> str:
        """Tóm tắt buổi tập. Chỉ dựa trên số liệu trong `session` và `progress`, không bịa thêm.

        Dòng "Công cụ hỗ trợ, không thay huấn luyện viên." do giao diện luôn hiện, không nằm
        trong chữ trả về (để coach nào cũng không làm rơi mất nó).
        """
        ...
