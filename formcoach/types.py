"""Kiểu dữ liệu truyền giữa các bước của pipeline (docs/ARCHITECTURE.md §2).

Chỉ chứa dữ liệu, không có logic. Mọi bước nhận và trả các kiểu này,
nên phần ở giữa pipeline test được bằng dữ liệu tổng hợp mà không cần video.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PoseSequence:
    """Khung xương của một hiệp (từ trang quay) hoặc một video (thử nghiệm offline).

    keypoints: shape (T, K, 3), mỗi khớp là [x, y, visibility].
        x chuẩn hoá theo chiều rộng, y theo chiều cao (0–1, có thể ra ngoài
        khoảng này khi khớp nằm ngoài khung). Hai trục khác thang đo, nên phải
        đổi sang pixel bằng `frame_size` trước khi tính góc.
        Khung không phát hiện người: cả hàng là NaN (giữ index = số frame).
    joint_names: K tên khớp, theo thứ tự trục thứ hai của `keypoints`.
    fps: số khung hình mỗi giây của video gốc.
    frame_size: (width, height) của video, tính bằng pixel.
    """

    keypoints: np.ndarray
    joint_names: list[str]
    fps: float
    frame_size: tuple[int, int]


@dataclass(frozen=True)
class FeatureSeries:
    """Các tín hiệu theo thời gian, mỗi tín hiệu shape (T,).

    Ví dụ {"elbow_angle": ..., "elbow_angle_raw": ...}. Hậu tố `_raw` là bản chưa
    làm mượt, giữ lại để vẽ so sánh. Có thể chứa NaN.
    """

    signals: dict[str, np.ndarray]
    fps: float


@dataclass(frozen=True)
class Rep:
    """Một lần lặp động tác, xác định bằng khoảng frame [start_frame, end_frame]."""

    index: int
    start_frame: int
    end_frame: int
    features: dict[str, float]  # ví dụ {"min_elbow_angle": 82.0, "descent_time_s": 1.1}


@dataclass(frozen=True)
class RepResult:
    """Kết quả phân loại một rep (multi-label).

    errors: tập lỗi dự đoán, ví dụ frozenset({"shallow", "hip_sag"}). Rỗng = good.
    scores: độ tin cậy cho từng lỗi; None nếu bộ phân loại không có (ví dụ luật).
    """

    rep: Rep
    errors: frozenset[str]
    scores: dict[str, float] | None


@dataclass
class Session:
    """Một buổi tập: mọi rep đã phân loại của một hiệp."""

    session_id: str
    exercise: str
    results: list[RepResult]
