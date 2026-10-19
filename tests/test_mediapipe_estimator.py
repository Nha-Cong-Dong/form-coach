"""Test tích hợp: cần MediaPipe và file model trong assets/ (không có thì bỏ qua)."""

from pathlib import Path

import numpy as np
import pytest

MODEL = Path("assets/pose_landmarker_full.task")
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="chưa tải model vào assets/")


def test_video_without_person_gives_all_nan(make_video) -> None:
    from formcoach.pose.mediapipe_estimator import MediaPipeEstimator

    video = make_video("trong.mp4", n_frames=10, size=(96, 64))
    pose = MediaPipeEstimator(MODEL).estimate(video)

    assert pose.keypoints.shape == (10, 33, 3)  # T = số khung đọc được, đủ 33 khớp
    assert np.isnan(pose.keypoints).all()  # không có người → toàn NaN, không bỏ khung
    assert pose.frame_size == (96, 64)  # (width, height)
    assert pose.fps == pytest.approx(24.0)
    assert len(pose.joint_names) == 33


def test_missing_model_raises(tmp_path: Path) -> None:
    from formcoach.pose.mediapipe_estimator import MediaPipeEstimator

    with pytest.raises(FileNotFoundError):
        MediaPipeEstimator(tmp_path / "khong_co.task")
