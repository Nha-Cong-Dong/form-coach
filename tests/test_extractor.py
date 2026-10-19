import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.features.extractor import FeatureExtractor, choose_side, side_visibility
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.types import PoseSequence

SIZE = (1280, 720)
FPS = 30.0


def expected_elbow(t: np.ndarray) -> np.ndarray:
    """Góc khuỷu đáp án: 165° ở đỉnh, 90° ở đáy, 5 rep trong 10 giây."""
    return 165.0 - 75.0 * np.abs(np.sin(np.pi * t / 2))


def make_pose(
    n: int = 300,
    visible_side: str = "right",
    standing: bool = False,
) -> PoseSequence:
    """Push-up tổng hợp, dựng trong toạ độ pixel rồi chuẩn hoá về 0–1 như MediaPipe.

    Bên `visible_side` có hình học đúng và visibility 0,9; bên kia toạ độ rác, visibility 0,2.
    standing=True: thân dựng đứng (vai thẳng trên cổ chân) thay vì nằm ngang.
    """
    t = np.arange(n) / FPS
    kp = np.full((n, 33, 3), 0.5)
    kp[:, :, 2] = 0.5

    shoulder = np.array([400.0, 300.0])
    elbow = shoulder + [0.0, 150.0]
    phi = np.radians(-90.0 + expected_elbow(t))  # hướng khuỷu→cổ tay tạo đúng góc với khuỷu→vai
    wrist = elbow + 150.0 * np.stack([np.cos(phi), np.sin(phi)], axis=1)
    if standing:
        hip, ankle = shoulder + [0.0, 300.0], shoulder + [0.0, 600.0]
    else:
        hip, ankle = shoulder + [300.0, 0.0], shoulder + [600.0, 0.0]
    points = {"shoulder": shoulder, "elbow": elbow, "wrist": wrist, "hip": hip, "ankle": ankle}

    other = "left" if visible_side == "right" else "right"
    rng = np.random.default_rng(0)
    for joint, px in points.items():
        good = MEDIAPIPE_JOINTS.index(f"{visible_side}_{joint}")
        bad = MEDIAPIPE_JOINTS.index(f"{other}_{joint}")
        kp[:, good, :2] = np.broadcast_to(px, (n, 2)) / np.array(SIZE)
        kp[:, good, 2] = 0.9
        kp[:, bad, :2] = rng.uniform(0, 1, (n, 2))
        kp[:, bad, 2] = 0.2
    return PoseSequence(keypoints=kp, joint_names=list(MEDIAPIPE_JOINTS), fps=FPS, frame_size=SIZE)


def test_elbow_angle_matches_formula() -> None:
    pose = make_pose()
    feats = FeatureExtractor().extract(pose, PushUp())
    t = np.arange(len(pose.keypoints)) / FPS
    np.testing.assert_allclose(feats.signals["elbow_angle"], expected_elbow(t), atol=0.5)
    assert feats.fps == FPS


def test_returns_all_defined_signals() -> None:
    feats = FeatureExtractor().extract(make_pose(), PushUp())
    assert set(feats.signals) == {"elbow_angle", "body_angle", "body_tilt"}
    for sig in feats.signals.values():
        assert sig.shape == (300,)


def test_straight_horizontal_body() -> None:
    feats = FeatureExtractor().extract(make_pose(), PushUp())
    np.testing.assert_allclose(feats.signals["body_angle"], 180.0, atol=1e-6)
    np.testing.assert_allclose(feats.signals["body_tilt"], 0.0, atol=1e-6)


def test_standing_body_is_vertical() -> None:
    feats = FeatureExtractor().extract(make_pose(standing=True), PushUp())
    np.testing.assert_allclose(feats.signals["body_tilt"], 90.0, atol=1e-6)


@pytest.mark.parametrize("side", ["left", "right"])
def test_chooses_the_more_visible_side(side: str) -> None:
    pose = make_pose(visible_side=side)
    assert choose_side(pose, PushUp()) == side
    vis = side_visibility(pose, PushUp())
    assert vis[side] == pytest.approx(0.9)


def test_left_visible_still_gives_correct_angle() -> None:
    # Quay từ phía bên kia: góc vẫn phải đúng, vì extractor tự đổi sang bên trái.
    pose = make_pose(visible_side="left")
    feats = FeatureExtractor().extract(pose, PushUp())
    t = np.arange(len(pose.keypoints)) / FPS
    np.testing.assert_allclose(feats.signals["elbow_angle"], expected_elbow(t), atol=0.5)


def test_nan_frame_gives_nan_only_at_that_frame() -> None:
    pose = make_pose()
    pose.keypoints[100] = np.nan  # khung 100 không thấy người
    feats = FeatureExtractor().extract(pose, PushUp())
    elbow = feats.signals["elbow_angle"]
    assert np.isnan(elbow[100])
    assert np.isfinite(np.delete(elbow, 100)).all()
    assert choose_side(pose, PushUp()) == "right"  # khung NaN không làm hỏng việc chọn bên


def test_all_nan_does_not_crash() -> None:
    pose = make_pose(n=10)
    pose.keypoints[:] = np.nan
    feats = FeatureExtractor().extract(pose, PushUp())
    assert np.isnan(feats.signals["elbow_angle"]).all()


def test_missing_joint_raises_clear_error() -> None:
    pose = make_pose(n=5)
    broken = PoseSequence(
        keypoints=pose.keypoints[:, :11],
        joint_names=MEDIAPIPE_JOINTS[:11],  # không có vai/khuỷu/...
        fps=FPS,
        frame_size=SIZE,
    )
    with pytest.raises(KeyError, match="shoulder"):
        FeatureExtractor().extract(broken, PushUp())
