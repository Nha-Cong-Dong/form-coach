"""Test bộ đếm rep bằng tín hiệu tổng hợp có đáp án biết trước.

Ngưỡng lấy từ PushUp thật (top_min 140, descent_trigger 125, ready_hold 0,5 s,
ready_max_tilt 35°, min_rep 0,8 s) để test bám đúng cấu hình đang dùng.
"""

import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.features.segmenter import RepSegmenter
from formcoach.types import FeatureSeries

FPS = 30.0
PLANK_TILT = 12.0
STAND_TILT = 85.0


def hold(value: float, seconds: float, fps: float = FPS) -> np.ndarray:
    return np.full(int(round(seconds * fps)), value)


def reps(
    n: int,
    bottom: float = 70.0,
    top: float = 165.0,
    period_s: float = 2.4,
    fps: float = FPS,
) -> np.ndarray:
    """n rep liên tiếp dạng cos trơn: bắt đầu và kết thúc ở `top`, đáy `bottom`."""
    t = np.arange(int(round(n * period_s * fps))) / fps
    return bottom + (top - bottom) * (1 + np.cos(2 * np.pi * t / period_s)) / 2


def features(elbow: np.ndarray, tilt: np.ndarray | float = PLANK_TILT, fps: float = FPS):
    tilt_arr = np.broadcast_to(np.asarray(tilt, dtype=float), elbow.shape).copy()
    return FeatureSeries(signals={"elbow_angle": elbow, "body_tilt": tilt_arr}, fps=fps)


def count(elbow: np.ndarray, tilt: np.ndarray | float = PLANK_TILT, fps: float = FPS) -> list:
    return RepSegmenter().segment(features(elbow, tilt, fps), PushUp())


def session(n: int = 5, **kw) -> np.ndarray:
    """Giữ plank 1 s → n rep → giữ plank 1 s."""
    fps = kw.get("fps", FPS)
    return np.concatenate([hold(165, 1.0, fps), reps(n, **kw), hold(165, 1.0, fps)])


# --- đếm đúng ---


def test_five_clean_reps() -> None:
    result = count(session(5))
    assert len(result) == 5
    for r in result:
        bottom = r.features["bottom_frame"]
        assert r.start_frame < bottom < r.end_frame
        assert r.features["min_elbow_angle"] == pytest.approx(70.0, abs=0.5)
        assert 1.5 < r.features["duration_s"] < 2.4
    for a, b in zip(result, result[1:], strict=False):
        assert a.end_frame <= b.start_frame  # không chồng nhau
    assert [r.index for r in result] == list(range(5))


def test_noise_does_not_create_extra_reps() -> None:
    elbow = session(5) + np.random.default_rng(42).normal(0, 3, session(5).size)
    assert len(count(elbow)) == 5


def test_shallow_reps_are_counted() -> None:
    # Rep nông (đáy 110°) vẫn phải được đếm; việc gắn nhãn shallow là của tuần 2.
    assert len(count(session(4, bottom=110.0))) == 4


def test_fast_shallow_reps_are_counted() -> None:
    # Như 2 rep hông nhô cao của clip mixed: đáy ~110°, chỉ ~0,7 s nằm dưới top_min.
    # Lần đầu min_rep_duration 0,8 s đã loại nhầm chúng như nhiễu.
    fast = reps(2, bottom=108.0, top=160.0, period_s=1.3)
    below = fast[: int(1.3 * FPS)] < 140
    assert 0.5 < below.sum() / FPS < 0.8  # tiền đề: rep ngắn thật
    elbow = np.concatenate([hold(160, 1.0), fast, hold(160, 1.0)])
    assert len(count(elbow)) == 2


def test_incomplete_lockout_reps_are_counted() -> None:
    # Đỉnh chỉ 148° (chưa duỗi hết tay) nhưng vẫn trên top_min 140 → vẫn đếm.
    elbow = np.concatenate([hold(165, 1.0), reps(4, top=148.0), hold(165, 1.0)])
    assert len(count(elbow)) == 4


# --- không đếm thừa ---


def test_oscillation_near_descent_trigger_counts_once() -> None:
    # Xuống tới ~125 rồi dao động 120–130 một lúc mới lên: chỉ là 1 rep.
    wobble = 125 + 5 * np.sin(np.linspace(0, 8 * np.pi, 60))
    elbow = np.concatenate(
        [hold(165, 1.0), np.linspace(165, 125, 20), wobble, np.linspace(125, 165, 20), hold(165, 1)]
    )
    assert len(count(elbow)) == 1


def test_slow_oscillation_near_top_min_counts_nothing() -> None:
    # Giữ plank, khuỷu dao động CHẬM quanh 140 (chu kỳ 2 s) nhưng không xuống dưới 125 → 0 rep.
    # Chu kỳ dài hơn min_rep_duration để chỉ còn hysteresis chặn được; dao động nhanh thì
    # min_rep_duration cũng chặn, test sẽ không phân biệt được hai cơ chế.
    t = np.arange(int(8 * FPS)) / FPS
    wobble = 140 + 8 * np.sin(2 * np.pi * t / 2.0)
    assert wobble.min() > 125
    elbow = np.concatenate([hold(165, 1.0), wobble])
    assert len(count(elbow)) == 0


def test_standing_and_bending_arms_counts_nothing() -> None:
    # Đứng (thân dựng 85°), gập duỗi tay như rep: không phải push-up.
    assert len(count(session(3), tilt=STAND_TILT)) == 0


def test_standing_up_from_bottom_does_not_count() -> None:
    # 2 rep, rep thứ 3 xuống đáy rồi đứng dậy: thân dựng lên giữa rep → bỏ rep dở.
    third = reps(1)[: int(1.2 * FPS)]  # xuống tới đáy
    rise = np.linspace(70, 175, 30)  # chống tay đứng dậy, khuỷu duỗi ra
    elbow = np.concatenate([hold(165, 1.0), reps(2), third, rise])
    tilt = np.full(elbow.size, PLANK_TILT)
    tilt[-len(rise) :] = np.linspace(PLANK_TILT, STAND_TILT, len(rise))
    assert len(count(elbow, tilt)) == 2


def test_fast_dip_shorter_than_min_rep_is_ignored() -> None:
    dip = np.concatenate([np.linspace(165, 110, 4), np.linspace(110, 165, 4)])  # ~0,27 s
    elbow = np.concatenate([hold(165, 1.0), dip, hold(165, 1.0)])
    assert len(count(elbow)) == 0


# --- đầu / cuối hiệp ---


def test_not_ready_long_enough_misses_first_rep_only() -> None:
    # Tay ở trên top_min chỉ ~0,3 s (< ready_hold 0,5 s) rồi xuống ngay: rep đầu không đếm.
    # Sau đó giữ plank 1 s rồi tập 3 rep: các rep này đếm bình thường.
    rushed = np.concatenate([hold(150, 0.2), np.linspace(150, 70, 24), np.linspace(70, 165, 24)])
    assert (rushed[: int(0.5 * FPS)] > 140).sum() < 0.5 * FPS  # tiền đề: chưa đủ ready_hold
    elbow = np.concatenate([rushed, hold(165, 1.0), reps(3), hold(165, 1.0)])
    assert len(count(elbow)) == 3


def test_session_ending_mid_rep_does_not_count_partial() -> None:
    # Như clip clean thật: video dừng khi đang đẩy lên, khuỷu mới ~135°.
    partial = reps(1)[: int(1.9 * FPS)]
    elbow = np.concatenate([hold(165, 1.0), reps(3), partial])
    assert partial[-1] < 140
    assert len(count(elbow)) == 3


def test_session_starting_at_bottom_has_no_ghost_rep() -> None:
    # Bắt đầu quay khi đang ở đáy, đẩy lên rồi mới tập 3 rep.
    elbow = np.concatenate([np.linspace(70, 165, 30), hold(165, 1.0), reps(3), hold(165, 1.0)])
    assert len(count(elbow)) == 3


def test_entering_from_standing() -> None:
    # Đứng → vào plank → 4 rep → đứng dậy (như clip enter_exit).
    elbow = np.concatenate([hold(170, 1.0), hold(165, 1.0), reps(4), hold(165, 0.5), hold(170, 1)])
    tilt = np.concatenate(
        [hold(STAND_TILT, 1.0), hold(PLANK_TILT, 1.0 + 4 * 2.4 + 0.5), hold(STAND_TILT, 1.0)]
    )
    assert len(count(elbow, tilt)) == 4


# --- NaN và fps ---


def test_all_nan_gives_no_reps() -> None:
    assert count(np.full(300, np.nan)) == []


def test_long_nan_gap_aborts_current_rep_only() -> None:
    # Mất người giữa rep thứ 3 → bỏ rep đó, sau khi thấy lại và sẵn sàng thì đếm tiếp.
    elbow = np.concatenate([hold(165, 1.0), reps(5), hold(165, 1.0)])
    gap = slice(int((1.0 + 2 * 2.4 + 0.8) * FPS), int((1.0 + 2 * 2.4 + 1.6) * FPS))
    elbow[gap] = np.nan
    assert len(count(elbow)) == 4


@pytest.mark.parametrize("fps", [24.0, 60.0])
def test_same_reps_at_different_fps(fps: float) -> None:
    result = count(session(5, fps=fps), fps=fps)
    assert len(result) == 5
    # Thời lượng tính bằng giây phải như nhau dù fps khác.
    assert result[2].features["duration_s"] == pytest.approx(
        count(session(5))[2].features["duration_s"], abs=0.1
    )


def test_rep_features_include_every_signal() -> None:
    feats = count(session(2))[0].features
    for key in ("min_elbow_angle", "max_elbow_angle", "min_body_tilt", "max_body_tilt"):
        assert key in feats
    assert feats["descent_time_s"] < feats["duration_s"]
