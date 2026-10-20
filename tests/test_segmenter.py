"""Test bộ đếm rep bằng tín hiệu tổng hợp có đáp án biết trước.

Ngưỡng lấy từ PushUp thật (top_min 140 cho sẵn sàng, min_amplitude 35°, ready_hold 0,5 s,
ready_max_tilt 35°, min_rep 0,4 s) để test bám đúng cấu hình đang dùng.
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


def extremes(points: list[float], half_period_s: float = 1.2) -> np.ndarray:
    """Đi qua lần lượt các đỉnh/đáy cho trước bằng nửa chu kỳ cos (trơn như chuyển động thật)."""
    n = int(round(half_period_s * FPS))
    u = (1 - np.cos(np.pi * np.arange(n) / n)) / 2  # 0 → 1 trơn
    parts = [a + (b - a) * u for a, b in zip(points, points[1:], strict=False)]
    return np.concatenate([*parts, [points[-1]]])


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
        # Chu kỳ 2,4 s trừ đoạn sát đỉnh (trong 10° dưới đỉnh ≈ ±0,25 s) ở hai đầu.
        assert r.features["duration_s"] == pytest.approx(1.9, abs=0.15)
    for a, b in zip(result, result[1:], strict=False):
        assert a.end_frame <= b.start_frame  # không chồng nhau
    assert [r.index for r in result] == list(range(5))


def test_long_wobbly_hold_before_first_rep_not_included() -> None:
    # Như hiệp shallow quay thử: giữ plank 6 s, khuỷu dao động 155–176°, cao nhất ở ĐẦU lúc giữ.
    t = np.arange(int(6 * FPS)) / FPS
    wait = 165 + 10 * np.cos(2 * np.pi * t / 1.5)
    wait[: int(0.5 * FPS)] = 176
    elbow = np.concatenate([wait, reps(3), hold(165, 1.0)])
    result = count(elbow)
    assert len(result) == 3
    assert result[0].start_frame / FPS > 5.0  # bắt đầu ngay trước khi xuống, không phải lúc 0,5 s
    assert result[0].features["duration_s"] < 2.5


def test_arm_extension_while_getting_up_not_included() -> None:
    # Như hiệp neck_drop quay thử: rep cuối lên tới ~160° rồi nghỉ 1,5 s; lúc đứng dậy tay duỗi
    # thẳng tới 179° (thân vẫn còn nằm), sau đó thân dựng lên.
    last = extremes([165, 60, 160])
    rest = hold(160, 1.5)
    exit_arm = np.linspace(160, 179, int(0.3 * FPS))
    elbow = np.concatenate([hold(165, 1.0), reps(2), last, rest, exit_arm, hold(179, 0.5)])
    tilt = np.full(elbow.size, PLANK_TILT)
    tilt[-int(0.5 * FPS) :] = STAND_TILT
    result = count(elbow, tilt)
    assert len(result) == 3
    rest_start = elbow.size - int(0.5 * FPS) - exit_arm.size - rest.size
    assert result[-1].end_frame < rest_start  # kết thúc khi vừa lên tới 160°, trước lúc nghỉ


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
    # Đỉnh chỉ 148° (chưa duỗi hết tay) → vẫn đếm.
    elbow = np.concatenate([hold(165, 1.0), reps(4, top=148.0), hold(165, 1.0)])
    assert len(count(elbow)) == 4


def test_incomplete_lockout_tops_below_top_min_are_counted() -> None:
    # Tái hiện hiệp quay 2026-10-20T10-15-32: 4 rep, đỉnh giữa chỉ 110°, 133°, 135° (dưới cả
    # top_min 140°). Bộ đếm ngưỡng cố định cũ gộp cả 4 thành 1 rep dài 10,6 s.
    elbow = np.concatenate(
        [hold(165, 1.0), extremes([165, 40, 110, 50, 133, 48, 135, 48, 165]), hold(165, 1.0)]
    )
    result = count(elbow)
    assert len(result) == 4
    assert [round(r.features["min_elbow_angle"]) for r in result] == [40, 50, 48, 48]


# --- không đếm thừa ---


def test_wobble_at_bottom_counts_once() -> None:
    # Xuống tới ~125 rồi dao động 120–130 (nhỏ hơn biên độ 35°) một lúc mới lên: chỉ là 1 rep.
    wobble = 125 + 5 * np.sin(np.linspace(0, 8 * np.pi, 60))
    elbow = np.concatenate(
        [hold(165, 1.0), np.linspace(165, 125, 20), wobble, np.linspace(125, 165, 20), hold(165, 1)]
    )
    assert len(count(elbow)) == 1


def test_slow_wobble_smaller_than_amplitude_counts_nothing() -> None:
    # Giữ plank, khuỷu dao động CHẬM 138–162° (chu kỳ 2 s, biên độ 24° < 35°) → 0 rep.
    # Chu kỳ dài hơn min_rep_duration để chỉ còn ngưỡng biên độ chặn được; dao động nhanh thì
    # min_rep_duration cũng chặn, test sẽ không phân biệt được hai cơ chế.
    t = np.arange(int(8 * FPS)) / FPS
    wobble = 150 + 12 * np.sin(2 * np.pi * t / 2.0)
    assert 165 - wobble.min() < 35  # tiền đề: kể cả từ đỉnh giữ plank xuống cũng < biên độ
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
    # Thân dựng lên nhanh (1/3 giây đầu), trước khi khuỷu kịp duỗi đủ 35°.
    tilt[-len(rise) :] = STAND_TILT
    tilt[-len(rise) : -len(rise) + 10] = np.linspace(PLANK_TILT, STAND_TILT, 10)
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


def test_session_ending_at_bottom_does_not_count_partial() -> None:
    # Video dừng khi đang ở đáy, chưa đẩy lên: rep dở không đếm.
    partial = reps(1)[: int(1.2 * FPS)]
    elbow = np.concatenate([hold(165, 1.0), reps(3), partial])
    assert len(count(elbow)) == 3


def test_session_ending_mid_ascent_counts_rep() -> None:
    # Như clip clean thật: video dừng khi đang đẩy lên, khuỷu ~130° (đã lên lại > 35° từ đáy 70°).
    # Người tập đã làm rep này: đếm (đáp án thật của clip clean là 7).
    partial = reps(1)[: int(1.9 * FPS)]
    assert partial[-1] - 70 > 35  # tiền đề
    elbow = np.concatenate([hold(165, 1.0), reps(3), partial])
    assert len(count(elbow)) == 4


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
    for key in ("min_elbow_angle", "max_elbow_angle", "median_elbow_angle", "min_body_tilt"):
        assert key in feats
    assert feats["descent_time_s"] < feats["duration_s"]


def test_median_ignores_single_noisy_frame() -> None:
    # Tín hiệu phụ (vd góc cổ) giữ 130° suốt rep nhưng có MỘT khung nhiễu 100°:
    # min bị kéo theo khung đó, trung vị thì không.
    elbow = session(2)
    neck = np.full(elbow.size, 130.0)
    rep = count(elbow)[0]
    neck[(rep.start_frame + rep.end_frame) // 2] = 100.0
    fs = features(elbow)
    fs.signals["neck_angle"] = neck
    feats = RepSegmenter().segment(fs, PushUp())[0].features
    assert feats["min_neck_angle"] == 100.0
    assert feats["median_neck_angle"] == 130.0


def test_median_skips_nan_frames() -> None:
    elbow = session(2)
    neck = np.full(elbow.size, 130.0)
    neck[: elbow.size // 2] = np.nan  # nửa đầu không thấy tai
    fs = features(elbow)
    fs.signals["neck_angle"] = neck
    feats = RepSegmenter().segment(fs, PushUp())[-1].features
    assert feats["median_neck_angle"] == 130.0


def test_top_after_rep_measures_lockout() -> None:
    # Như hiệp incomplete_lockout quay thử: đỉnh giữa các rep chỉ 110°, 133°, 135°; rep cuối lên
    # hết 165°. top_elbow_angle = đỉnh ngay sau mỗi rep.
    elbow = np.concatenate(
        [hold(165, 1.0), extremes([165, 40, 110, 50, 133, 48, 135, 48, 165]), hold(165, 1.0)]
    )
    result = count(elbow)
    tops = [r.features["top_elbow_angle"] for r in result]
    np.testing.assert_allclose(tops, [110, 133, 135, 165], atol=1.0)
    # Vì sao không dùng max trong rep: rep bắt đầu ngay sau đỉnh TRƯỚC nó, nên max của rep 1 là
    # 165° (plank trước rep) dù sau rep 1 chỉ lên tới 110°.
    assert result[0].features["max_elbow_angle"] > 155


def test_top_after_last_rep_at_end_of_signal() -> None:
    # Video dừng ngay khi vừa lên: cửa sổ sau rep bị cắt ngắn nhưng vẫn có giá trị.
    elbow = np.concatenate([hold(165, 1.0), reps(2)])
    result = count(elbow)
    assert len(result) == 2
    assert result[-1].features["top_elbow_angle"] == pytest.approx(165.0, abs=1.0)
