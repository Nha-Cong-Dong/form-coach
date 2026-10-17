"""Lớp gốc cho bộ phân loại lỗi kỹ thuật (Strategy: luật / random forest / mạng chuỗi)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from formcoach.types import Rep, RepResult


class FormClassifier(ABC):
    """Tìm tập lỗi của từng rep (multi-label): mỗi lỗi một quyết định có/không."""

    @abstractmethod
    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None:
        """Học từ các rep hợp lệ đã gán nhãn; errors[i] là tập lỗi của reps[i].

        Bộ phân loại bằng luật không cần làm gì.
        """
        ...

    @abstractmethod
    def predict(self, reps: list[Rep]) -> list[RepResult]:
        """Dự đoán tập lỗi cho từng rep, trả về cùng thứ tự với `reps`."""
        ...
