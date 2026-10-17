"""Lớp gốc cho pose estimator (Strategy: đổi model pose mà không sửa pipeline)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from formcoach.types import PoseSequence


class PoseEstimator(ABC):
    """Biến một video thành chuỗi khung xương."""

    @abstractmethod
    def estimate(self, video_path: Path) -> PoseSequence:
        """Chạy pose trên mọi khung hình của video.

        Trả về PoseSequence có đúng T hàng (T = số khung đọc được). Khung không
        phát hiện người là hàng NaN, không bị bỏ đi, để index luôn khớp số frame.
        """
        ...
