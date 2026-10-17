"""Lớp gốc cho coach (Strategy: mẫu câu / LLM qua API / model local)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from formcoach.types import Session


class Coach(ABC):
    """Diễn giải kết quả một buổi tập thành nhận xét bằng chữ."""

    @abstractmethod
    def summarize(self, session: Session) -> str:
        """Tóm tắt buổi tập. Chỉ dựa trên số liệu trong `session`, không bịa thêm."""
        ...
