import math

import numpy as np
import pytest

from formcoach.features.view import shoulder_separation
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.types import PoseSequence

SIZE = (1000, 1000)  # khung vuông: dễ tính tay


def _pose(points: dict[str, tuple[float, float]], n: int = 5) -> PoseSequence:
    """n khung giống nhau; points: tên khớp -> (x, y) pixel. Khớp khác để NaN."""
    kp = np.full((n, 33, 3), np.nan)
    for name, (x, y) in points.items():
        i = MEDIAPIPE_JOINTS.index(name)
        kp[:, i] = [x / SIZE[0], y / SIZE[1], 0.9]
    return PoseSequence(kp, list(MEDIAPIPE_JOINTS), 30.0, SIZE)


def test_side_view_shoulders_overlap_is_zero() -> None:
    pose = _pose(
        {
            "left_shoulder": (400, 300),
            "right_shoulder": (400, 300),
            "left_hip": (700, 300),
            "right_hip": (700, 300),
        }
    )
    assert shoulder_separation(pose) == pytest.approx(0.0)


def test_oblique_view_known_ratio() -> None:
    # Vai cách nhau 60 px, thân dài 300 px mỗi bên → 0,2.
    pose = _pose(
        {
            "left_shoulder": (400, 270),
            "right_shoulder": (400, 330),
            "left_hip": (700, 270),
            "right_hip": (700, 330),
        }
    )
    assert shoulder_separation(pose) == pytest.approx(0.2)


def test_uses_pixel_space_not_normalized() -> None:
    # Khung 2000x1000: tách vai 0,1 theo x chuẩn hoá = 200 px; thân 0,4 theo x = 800 px → 0,25.
    kp = np.full((3, 33, 3), np.nan)
    for name, x, y in [
        ("left_shoulder", 0.30, 0.5),
        ("right_shoulder", 0.40, 0.5),
        ("left_hip", 0.70, 0.5),
        ("right_hip", 0.80, 0.5),
    ]:
        kp[:, MEDIAPIPE_JOINTS.index(name)] = [x, y, 0.9]
    pose = PoseSequence(kp, list(MEDIAPIPE_JOINTS), 30.0, (2000, 1000))
    assert shoulder_separation(pose) == pytest.approx(0.25)


def test_median_ignores_frames_without_person() -> None:
    pose = _pose(
        {
            "left_shoulder": (400, 270),
            "right_shoulder": (400, 330),
            "left_hip": (700, 270),
            "right_hip": (700, 330),
        }
    )
    pose.keypoints[0] = np.nan  # khung đầu không thấy người
    assert shoulder_separation(pose) == pytest.approx(0.2)


def test_no_person_is_nan() -> None:
    assert math.isnan(shoulder_separation(_pose({})))
