"""Đọc video bằng OpenCV cho đường thử nghiệm offline."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DEFAULT_FPS = 30.0


@dataclass(frozen=True)
class VideoInfo:
    """Thông tin metadata của video. frame_count chỉ là số khai báo, có thể lệch số thật."""

    fps: float
    width: int
    height: int
    frame_count: int


def _open(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Không mở được video: {path}")
    return cap


def video_info(path: Path) -> VideoInfo:
    """Đọc metadata. fps = 0 (file hỏng metadata) thì dùng DEFAULT_FPS."""
    cap = _open(path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
        return VideoInfo(
            fps=float(fps),
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        )
    finally:
        cap.release()


def iter_frames(path: Path) -> Iterator[np.ndarray]:
    """Lần lượt trả từng khung BGR (H, W, 3), đã xoay theo metadata (OpenCV tự xoay).

    Generator: chỉ giữ một khung trong RAM mỗi lúc, nên đọc được video dài.
    """
    cap = _open(path)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield frame
    finally:
        cap.release()
