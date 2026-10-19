"""Fixture dùng chung cho các test."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def make_video(tmp_path: Path) -> Callable[..., Path]:
    """Tạo video tổng hợp trong tmp_path: một chấm trắng chạy ngang trên nền xám, 24 fps."""
    import cv2

    def _make(name: str = "v.mp4", n_frames: int = 12, size: tuple[int, int] = (64, 48)) -> Path:
        w, h = size
        path = tmp_path / name
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (w, h))
        for i in range(n_frames):
            frame = np.full((h, w, 3), 80, np.uint8)
            cv2.circle(frame, (4 * i % w, h // 2), 3, (255, 255, 255), -1)
            writer.write(frame)
        writer.release()
        return path

    return _make
