"""Hình học khung xương: đổi toạ độ, góc tại khớp, độ nghiêng của một đoạn.

Mọi hàm nhận mảng có trục cuối là (x, y) và tính theo từng phần tử của các trục còn lại,
ví dụ shape (T, 2) cho T khung hình → kết quả shape (T,). Không vòng lặp Python.
Điểm có NaN (khung không thấy người) hoặc đoạn dài 0 → kết quả NaN, không báo lỗi.
"""

from __future__ import annotations

import numpy as np


def to_pixel_space(xy: np.ndarray, frame_size: tuple[int, int]) -> np.ndarray:
    """Đổi toạ độ chuẩn hoá 0–1 sang pixel: x nhân chiều rộng, y nhân chiều cao.

    Bắt buộc trước khi tính góc: MediaPipe chuẩn hoá x theo chiều rộng và y theo chiều cao,
    nên trên khung không vuông (vd 1280x720) một đơn vị x khác độ dài một đơn vị y.
    """
    width, height = frame_size
    return np.asarray(xy, dtype=float) * np.array([width, height], dtype=float)


def joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Góc tại b (độ, 0–180) giữa đoạn b→a và b→c. a, b, c shape (..., 2)."""
    ba = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    bc = np.asarray(c, dtype=float) - np.asarray(b, dtype=float)
    denom = np.linalg.norm(ba, axis=-1) * np.linalg.norm(bc, axis=-1)
    dot = np.sum(ba * bc, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos = np.where(denom > 0, dot / denom, np.nan)
    # Sai số làm tròn có thể cho cos = 1.0000000002 → arccos ra NaN; clip về [-1, 1].
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def segment_tilt(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Góc của đoạn a→b so với phương ngang (độ, 0–90). a, b shape (..., 2).

    0° = nằm ngang, 90° = dựng đứng. Lấy trị tuyệt đối nên không phụ thuộc chiều đoạn
    (vai→chân hay chân→vai) và không bị ảnh hưởng việc trục y của ảnh hướng xuống.
    """
    d = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    dx, dy = np.abs(d[..., 0]), np.abs(d[..., 1])
    tilt = np.degrees(np.arctan2(dy, dx))
    return np.where((dx == 0) & (dy == 0), np.nan, tilt)
