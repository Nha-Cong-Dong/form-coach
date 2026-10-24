"""Đo góc đặt máy từ chính khung xương (không cần phần cứng): máy quay ngang hông hay chéo.

Quay đúng ngang hông thì hai vai gần như chồng lên nhau trong hình (vai xa bị che); máy càng
chéo thì hai vai càng tách ra. Chia cho chiều dài thân (vai–hông) để không phụ thuộc người đứng
gần hay xa máy.
"""

from __future__ import annotations

import numpy as np

from formcoach.features.geometry import to_pixel_space
from formcoach.types import PoseSequence


def shoulder_separation(pose: PoseSequence) -> float:
    """Trung vị qua các khung: khoảng cách vai trái–vai phải / chiều dài thân (vai–hông TB 2 bên).

    0 = hai vai trùng nhau (quay đúng ngang hông). Không lọc theo visibility: khi quay ngang, vai
    xa luôn bị che nên visibility thấp, lọc đi sẽ bỏ đúng những khung quay chuẩn nhất; MediaPipe
    vẫn ước lượng vị trí của nó. Không khung nào đủ 4 khớp (hoặc thân dài 0) → NaN.
    """
    names = pose.joint_names
    pts = to_pixel_space(pose.keypoints[:, :, :2], pose.frame_size)

    def at(name: str) -> np.ndarray:
        return pts[:, names.index(name)]

    ls, rs = at("left_shoulder"), at("right_shoulder")
    lh, rh = at("left_hip"), at("right_hip")
    shoulders = np.linalg.norm(ls - rs, axis=-1)
    torso = (np.linalg.norm(ls - lh, axis=-1) + np.linalg.norm(rs - rh, axis=-1)) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(torso > 0, shoulders / torso, np.nan)
    ratio = ratio[np.isfinite(ratio)]
    return float(np.median(ratio)) if ratio.size else float("nan")
