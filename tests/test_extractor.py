import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.features.extractor import FeatureExtractor, choose_side, side_visibility
from formcoach.features.segmenter import RepSegmenter
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.types import PoseSequence
from tests.synthetic import plank_keypoints

SIZE = (1280, 720)
FPS = 30.0


def expected_elbow(t: np.ndarray) -> np.ndarray:
    """Góc khuỷu đáp án: 165° ở đỉnh, 90° ở đáy, 5 rep trong 10 giây.

    Dạng cos trơn như chuyển động thật (khuỷu không đổi chiều đột ngột như đỉnh nhọn của |sin|).
    """
    return 127.5 + 37.5 * np.cos(2 * np.pi * t / 2.0)


def make_pose(
    n: int = 300,
    visible_side: str = "right",
    standing: bool = False,
    hip_dy: float = 0.0,
    head_dy: float = 0.0,
) -> PoseSequence:
    """Push-up tổng hợp, dựng trong toạ độ pixel rồi chuẩn hoá về 0–1 như MediaPipe.

    Bên `visible_side` có hình học đúng và visibility 0,9; bên kia toạ độ rác, visibility 0,2.
    standing=True: thân dựng đứng (vai thẳng trên cổ chân) thay vì nằm ngang.
    hip_dy: dời hông theo trục y của ảnh (pixel; âm = lên trên = hông nhô, dương = võng).
    head_dy: dời tai theo trục y (pixel; dương = gục xuống, âm = ngửa lên); 0 = cổ thẳng theo thân.
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
        hip, ankle = shoulder + [300.0, hip_dy], shoulder + [600.0, 0.0]
    ear = shoulder + ([0.0, -80.0] if standing else [-80.0, head_dy])  # đầu nối dài thân
    points = {
        "ear": ear,
        "shoulder": shoulder,
        "elbow": elbow,
        "wrist": wrist,
        "hip": hip,
        "ankle": ankle,
    }

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


def test_raw_elbow_angle_matches_formula() -> None:
    pose = make_pose()
    feats = FeatureExtractor().extract(pose, PushUp())
    t = np.arange(len(pose.keypoints)) / FPS
    np.testing.assert_allclose(feats.signals["elbow_angle_raw"], expected_elbow(t), atol=0.5)
    assert feats.fps == FPS


def test_smoothed_elbow_stays_close_to_formula() -> None:
    # Tín hiệu đã trơn thì làm mượt gần như không đổi nó.
    pose = make_pose()
    feats = FeatureExtractor().extract(pose, PushUp())
    t = np.arange(len(pose.keypoints)) / FPS
    np.testing.assert_allclose(feats.signals["elbow_angle"], expected_elbow(t), atol=0.5)


def test_returns_smoothed_and_raw_signals() -> None:
    feats = FeatureExtractor().extract(make_pose(), PushUp())
    names = {"elbow_angle", "body_angle", "neck_angle", "body_tilt", "hip_offset"}
    assert set(feats.signals) == names | {f"{n}_raw" for n in names}
    for sig in feats.signals.values():
        assert sig.shape == (300,)


def test_straight_horizontal_body() -> None:
    feats = FeatureExtractor().extract(make_pose(), PushUp())
    np.testing.assert_allclose(feats.signals["body_angle"], 180.0, atol=1e-6)
    np.testing.assert_allclose(feats.signals["body_tilt"], 0.0, atol=1e-6)


@pytest.mark.parametrize(
    ("hip_dy", "expected"),
    [(-60.0, 0.1), (60.0, -0.1), (0.0, 0.0)],  # vai–cổ chân dài 600 px → 60 px = 0,1
)
def test_hip_offset_sign_and_size(hip_dy: float, expected: float) -> None:
    # Hông nhô (lên trên ảnh) → dương; võng → âm. Hai trường hợp có CÙNG body_angle:
    # đó là lý do cần hip_offset.
    feats = FeatureExtractor().extract(make_pose(hip_dy=hip_dy), PushUp())
    np.testing.assert_allclose(feats.signals["hip_offset"], expected, atol=1e-6)


def test_body_angle_cannot_tell_sag_from_high() -> None:
    up = FeatureExtractor().extract(make_pose(hip_dy=-60.0), PushUp()).signals
    down = FeatureExtractor().extract(make_pose(hip_dy=60.0), PushUp()).signals
    np.testing.assert_allclose(up["body_angle"], down["body_angle"], atol=1e-6)
    assert up["hip_offset"][0] > 0 > down["hip_offset"][0]


@pytest.mark.parametrize(
    ("head_dy", "expected"),
    [(0.0, 180.0), (80.0, 135.0), (-80.0, 135.0)],  # tai cách vai 80 px theo thân
)
def test_neck_angle(head_dy: float, expected: float) -> None:
    # Cổ thẳng theo thân 180°; gục xuống hay ngửa lên cùng mức → cùng một góc nhỏ hơn.
    feats = FeatureExtractor().extract(make_pose(head_dy=head_dy), PushUp())
    np.testing.assert_allclose(feats.signals["neck_angle"], expected, atol=1e-6)


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
    np.testing.assert_allclose(feats.signals["elbow_angle_raw"], expected_elbow(t), atol=0.5)


def test_short_nan_gap_is_filled_but_raw_keeps_nan() -> None:
    pose = make_pose()
    pose.keypoints[100] = np.nan  # khung 100 không thấy người
    feats = FeatureExtractor().extract(pose, PushUp())
    raw = feats.signals["elbow_angle_raw"]
    assert np.isnan(raw[100])
    assert np.isfinite(np.delete(raw, 100)).all()
    assert np.isfinite(feats.signals["elbow_angle"]).all()  # lỗ 1 khung < max_gap → được lấp
    assert choose_side(pose, PushUp()) == "right"  # khung NaN không làm hỏng việc chọn bên


def test_long_nan_gap_stays_nan() -> None:
    pose = make_pose()
    pose.keypoints[100:160] = np.nan  # mất người 2 giây, dài hơn max_gap_s
    feats = FeatureExtractor().extract(pose, PushUp())
    assert np.isnan(feats.signals["elbow_angle"][100:160]).all()


# --- bỏ khung có khớp mờ (min_joint_visibility) ---


def test_low_visibility_frames_are_dropped_but_raw_kept() -> None:
    pose = make_pose()
    elbow = MEDIAPIPE_JOINTS.index("right_elbow")
    pose.keypoints[100:160, elbow, 2] = 0.2  # khuỷu mờ 2 giây
    feats = FeatureExtractor().extract(pose, PushUp())
    assert np.isnan(feats.signals["elbow_angle"][100:160]).all()  # góc khuỷu bị loại
    assert np.isfinite(feats.signals["elbow_angle_raw"][100:160]).all()  # bản thô vẫn còn
    # Độ nghiêng thân không dùng khuỷu nên không bị ảnh hưởng.
    assert np.isfinite(feats.signals["body_tilt"][100:160]).all()


def test_brief_visibility_dip_is_filled() -> None:
    pose = make_pose()
    pose.keypoints[100:104, MEDIAPIPE_JOINTS.index("right_wrist"), 2] = 0.3  # ~0,13 s
    feats = FeatureExtractor().extract(pose, PushUp())
    assert np.isfinite(feats.signals["elbow_angle"]).all()  # lỗ ngắn < max_gap_s được lấp


def test_phantom_rep_from_blurry_joints_is_not_counted() -> None:
    # Như hiệp quay 2026-10-19T23-38-38: 5 rep thật (khớp rõ), rồi đi sát điện thoại bấm Xong,
    # khớp mờ (~0,2) và MediaPipe đoán ra một "rep" khuỷu gập sâu trong khi thân vẫn "nằm".
    period = int(2.4 * FPS)
    t = np.arange(5 * period) / FPS
    real = 117.5 + 47.5 * np.cos(2 * np.pi * t / 2.4)
    hold = np.full(30, 165.0)
    junk = 117.5 + 47.5 * np.cos(2 * np.pi * np.arange(period) / period)  # trông như một rep
    elbow = np.concatenate([hold, real, hold, hold, junk, hold])
    kp = plank_keypoints(elbow)
    junk_start = len(hold) + len(real) + 2 * len(hold)
    side_joints = [MEDIAPIPE_JOINTS.index(f"right_{j}") for j in ("shoulder", "elbow", "wrist")]
    kp[junk_start - 30 :, side_joints, 2] = 0.2  # từ lúc đứng dậy đi lại: khớp mờ
    pose = PoseSequence(keypoints=kp, joint_names=list(MEDIAPIPE_JOINTS), fps=FPS, frame_size=SIZE)

    feats = FeatureExtractor().extract(pose, PushUp())
    assert len(RepSegmenter().segment(feats, PushUp())) == 5


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
