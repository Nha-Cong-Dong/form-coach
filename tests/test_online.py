"""OnlineRepCounter: đếm trực tiếp từng khung phải khớp bộ đếm cả hiệp (analyze), lệch tối đa 1."""

import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.features.extractor import FeatureExtractor
from formcoach.features.online import OnlineRepCounter
from formcoach.pipeline import analyze
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.types import PoseSequence
from tests.synthetic import SIZE, plank_keypoints

FPS = 30.0
EX = PushUp()


def reps_signal(n_reps: int, bottom: float = 60.0, period_s: float = 2.4) -> np.ndarray:
    """Góc khuỷu: giữ plank 1 s → n rep (165° ↔ bottom) → giữ plank 1 s."""
    t = np.arange(int(period_s * FPS)) / FPS
    mid, amp = (165 + bottom) / 2, (165 - bottom) / 2
    rep = mid + amp * np.cos(2 * np.pi * t / period_s)
    return np.concatenate([np.full(30, 165.0), np.tile(rep, n_reps), np.full(30, 165.0)])


def run_online(kp: np.ndarray) -> tuple[OnlineRepCounter, list[int]]:
    counter = OnlineRepCounter(EX, FPS, SIZE)
    counts = [counter.update(frame) for frame in kp]
    return counter, counts


def offline_count(kp: np.ndarray) -> int:
    pose = PoseSequence(kp, list(MEDIAPIPE_JOINTS), FPS, SIZE)
    return len(analyze(pose, EX)[1])


@pytest.mark.parametrize("n", [1, 3, 5])
def test_counts_n_reps_from_keypoints(n: int) -> None:
    kp = plank_keypoints(reps_signal(n))
    counter, counts = run_online(kp)
    assert counter.finish() == n == offline_count(kp)
    assert counts == sorted(counts)  # số đếm không bao giờ giảm
    assert counts[-1] == n  # rep cuối đã được đếm trước khi gọi finish (rep chờ)


def test_same_spans_as_offline_when_fed_offline_signals() -> None:
    # Bảo vệ lớp bọc: đưa đúng tín hiệu đã làm mượt của đường cả hiệp → cùng số rep.
    kp = plank_keypoints(reps_signal(4, bottom=95))  # rep nông vẫn được đếm (theo biên độ)
    pose = PoseSequence(kp, list(MEDIAPIPE_JOINTS), FPS, SIZE)
    signals = FeatureExtractor().extract(pose, EX).signals
    counter = OnlineRepCounter(EX, FPS, SIZE)
    for a, t in zip(signals["elbow_angle"], signals["body_tilt"], strict=True):
        counter.update_signals(a, t)
    assert counter.finish() == len(analyze(pose, EX)[1]) == 4


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_noisy_keypoints_within_one_of_offline(seed: int) -> None:
    rng = np.random.default_rng(seed)
    kp = plank_keypoints(reps_signal(6))
    kp[:, :, :2] += rng.normal(0, 0.004, kp[:, :, :2].shape)  # ~5 px rung trên khung 1280
    counter, _ = run_online(kp)
    assert abs(counter.finish() - offline_count(kp)) <= 1


def test_count_rises_before_rep_is_closed() -> None:
    # Rep được đếm ngay khi đã lên lại đủ biên độ (rep chờ), không đợi chốt đỉnh cuối.
    kp = plank_keypoints(reps_signal(1))
    counter, counts = run_online(kp)
    assert counts[-1] == 1  # màn hình đã hiện 1 rep...
    assert counter.completed == 0  # ...dù rep đó vẫn đang chờ chốt đỉnh cuối
    assert counts.index(1) < len(counts) - 1  # số 1 hiện ra từ trước khung cuối
    assert counter.finish() == 1  # hết hiệp mới chốt


def test_long_gap_resets_short_gap_is_bridged() -> None:
    kp = plank_keypoints(reps_signal(2))
    # Lỗ ngắn (0,1 s) giữa rep: vẫn đếm đủ.
    short = kp.copy()
    short[60:63] = np.nan
    counter, _ = run_online(short)
    assert counter.finish() == 2
    # Mất người 1 s giữa rep 1: rep đó bị bỏ (máy về chờ), như bản cả hiệp với lỗ dài.
    long_gap = kp.copy()
    long_gap[50:80] = np.nan
    counter, _ = run_online(long_gap)
    assert counter.finish() == offline_count(long_gap)


def test_shows_more_visible_side() -> None:
    kp = plank_keypoints(reps_signal(1))  # bên phải rõ (0,95), bên trái mờ (0,2)
    counter, _ = run_online(kp)
    assert counter.side == "right"
    # Đảo: làm bên trái rõ, bên phải mờ → hiển thị bên trái.
    counter, _ = run_online(_swap_sides(kp))
    assert counter.side == "left" and counter.finish() == 1


def test_no_count_while_standing() -> None:
    # Đứng (thân dựng ~90°): không phải đang tập, không đếm dù tay co duỗi.
    kp = plank_keypoints(reps_signal(3))
    ankle = MEDIAPIPE_JOINTS.index("right_ankle")
    shoulder = MEDIAPIPE_JOINTS.index("right_shoulder")
    kp[:, ankle, 0] = kp[:, shoulder, 0]  # cổ chân thẳng dưới vai
    kp[:, ankle, 1] = kp[:, shoulder, 1] + 0.6
    counter, _ = run_online(kp)
    assert counter.finish() == 0


def test_phase_and_no_person() -> None:
    counter = OnlineRepCounter(EX, FPS, SIZE)
    assert counter.phase == "waiting_ready" and counter.count == 0
    nan_frame = np.full((33, 3), np.nan)
    for _ in range(200):  # không thấy người lâu: không lỗi, không đếm
        assert counter.update(nan_frame) == 0
    assert counter.finish() == 0


def _swap_sides(kp: np.ndarray) -> np.ndarray:
    """Đổi trái ↔ phải: bên trái rõ, bên phải mờ."""
    out = kp.copy()
    for j in ("shoulder", "elbow", "wrist", "hip", "ankle", "ear", "knee"):
        li, ri = MEDIAPIPE_JOINTS.index(f"left_{j}"), MEDIAPIPE_JOINTS.index(f"right_{j}")
        out[:, [li, ri]] = kp[:, [ri, li]]
    return out


def test_side_seen_first_is_not_locked_in() -> None:
    # Lỗi gặp trên dữ liệu thật (9/44 hiệp đếm 0): 1 s đầu còn đứng gần máy, bên PHẢI rõ; khi
    # nằm tập thì bên TRÁI mới rõ. Bản khoá bên sau 1 s chọn sai bên và không bao giờ đếm.
    near_phone = plank_keypoints(np.full(40, 165.0))  # 40 khung đầu: phải rõ
    tap = np.concatenate([near_phone, _swap_sides(plank_keypoints(reps_signal(4)))])  # rồi trái rõ
    counter, _ = run_online(tap)
    assert counter.side == "left"
    assert counter.finish() == offline_count(tap) == 4
