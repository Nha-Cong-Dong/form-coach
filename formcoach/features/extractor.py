"""Từ khung xương (PoseSequence) ra các tín hiệu theo thời gian (FeatureSeries).

Mỗi tín hiệu có hai bản: `<tên>` đã bỏ khung có khớp mờ (visibility < min_joint_visibility),
lấp lỗ NaN ngắn và làm mượt (dùng để đếm rep); `<tên>_raw` là góc thô từng khung, không lọc
(để vẽ so sánh).
"""

from __future__ import annotations

import numpy as np

from formcoach.exercises.base import Exercise
from formcoach.features.geometry import joint_angle, segment_tilt, to_pixel_space
from formcoach.features.smoothing import interpolate_gaps, smooth
from formcoach.types import FeatureSeries, PoseSequence

SIDES = ("left", "right")


def used_joints(exercise: Exercise) -> list[str]:
    """Tên khớp (không có bên) mà bài tập dùng, theo thứ tự xuất hiện, không trùng."""
    names: list[str] = []
    for joints in (*exercise.angle_definitions().values(), *exercise.tilt_definitions().values()):
        for j in joints:
            if j not in names:
                names.append(j)
    return names


def _index(pose: PoseSequence, name: str) -> int:
    try:
        return pose.joint_names.index(name)
    except ValueError:
        raise KeyError(f"PoseSequence không có khớp '{name}'") from None


def side_visibility(pose: PoseSequence, exercise: Exercise) -> dict[str, float]:
    """Visibility trung bình của các khớp bài tập dùng, cho từng bên, trên cả hiệp.

    Bỏ qua khung NaN (không có người). Không có khung nào có người → NaN.
    """
    result: dict[str, float] = {}
    for side in SIDES:
        idx = [_index(pose, f"{side}_{j}") for j in used_joints(exercise)]
        vis = pose.keypoints[:, idx, 2]
        result[side] = float(np.nanmean(vis)) if np.isfinite(vis).any() else float("nan")
    return result


def choose_side(pose: PoseSequence, exercise: Exercise) -> str:
    """Bên nhìn rõ hơn trên CẢ hiệp (không đổi bên giữa chừng). Hoà hoặc không có dữ liệu → trái."""
    vis = side_visibility(pose, exercise)
    if np.isnan(vis["right"]):
        return "left"
    if np.isnan(vis["left"]) or vis["right"] > vis["left"]:
        return "right"
    return "left"


class FeatureExtractor:
    """Tính mọi góc trong `angle_definitions` và độ nghiêng trong `tilt_definitions`."""

    def extract(self, pose: PoseSequence, exercise: Exercise) -> FeatureSeries:
        side = choose_side(pose, exercise)

        th = exercise.phase_thresholds()

        def xy(joint: str) -> np.ndarray:
            # Lấy (T, 2) của một khớp ở bên đã chọn, đổi sang pixel trước khi tính góc.
            return to_pixel_space(
                pose.keypoints[:, _index(pose, f"{side}_{joint}"), :2], pose.frame_size
            )

        def reliable(joints: tuple[str, ...]) -> np.ndarray:
            # (T,) True khi MỌI khớp tạo nên góc đều nhìn rõ. Khớp mờ = MediaPipe đoán bừa,
            # góc tính từ đó là rác (vd lúc đi sát điện thoại để bấm Xong).
            vis = pose.keypoints[:, [_index(pose, f"{side}_{j}") for j in joints], 2]
            return np.nan_to_num(vis, nan=0.0).min(axis=1) >= th["min_joint_visibility"]

        raw: dict[str, np.ndarray] = {}
        masks: dict[str, np.ndarray] = {}
        for name, (a, b, c) in exercise.angle_definitions().items():
            raw[name] = joint_angle(xy(a), xy(b), xy(c))
            masks[name] = reliable((a, b, c))
        for name, (a, b) in exercise.tilt_definitions().items():
            raw[name] = segment_tilt(xy(a), xy(b))
            masks[name] = reliable((a, b))

        max_gap = int(round(th["max_gap_s"] * pose.fps))
        signals: dict[str, np.ndarray] = {}
        for name, values in raw.items():
            # Bỏ khung không tin được → NaN; lỗ ngắn được lấp, lỗ dài giữ NaN (bộ đếm về chờ).
            trusted = np.where(masks[name], values, np.nan)
            filled = interpolate_gaps(trusted, max_gap)
            signals[name] = smooth(filled, pose.fps, th["smoothing_window_s"])
            signals[f"{name}_raw"] = values  # bản thô giữ nguyên, kể cả khung bị loại
        return FeatureSeries(signals=signals, fps=pose.fps)
