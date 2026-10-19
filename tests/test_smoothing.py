import numpy as np
import pytest

from formcoach.features.smoothing import interpolate_gaps, smooth, window_frames

# --- interpolate_gaps ---


def test_short_gap_filled_linearly() -> None:
    x = np.array([0.0, 1.0, np.nan, np.nan, np.nan, 5.0, 6.0])
    np.testing.assert_allclose(interpolate_gaps(x, max_gap=3), [0, 1, 2, 3, 4, 5, 6])


def test_long_gap_kept_nan() -> None:
    x = np.array([0.0, np.nan, np.nan, np.nan, np.nan, 5.0])
    out = interpolate_gaps(x, max_gap=3)
    assert np.isnan(out[1:5]).all()
    assert out[0] == 0 and out[5] == 5


def test_leading_and_trailing_nan_not_filled() -> None:
    x = np.array([np.nan, 1.0, 2.0, np.nan])
    out = interpolate_gaps(x, max_gap=10)
    assert np.isnan(out[0]) and np.isnan(out[3])


def test_no_nan_unchanged_and_input_not_modified() -> None:
    x = np.array([1.0, np.nan, 3.0])
    original = x.copy()
    interpolate_gaps(x, max_gap=2)
    np.testing.assert_array_equal(x, original)  # không sửa mảng gốc
    y = np.arange(5.0)
    np.testing.assert_array_equal(interpolate_gaps(y, 2), y)


def test_all_nan() -> None:
    assert np.isnan(interpolate_gaps(np.full(5, np.nan), max_gap=10)).all()


# --- window_frames ---


@pytest.mark.parametrize(
    ("fps", "window_s", "expected"),
    [(30, 0.25, 9), (60, 0.25, 15), (24, 0.25, 7), (30, 0.01, 3)],
)
def test_window_is_odd_and_scales_with_fps(fps, window_s, expected) -> None:
    n = window_frames(fps, window_s)
    assert n == expected
    assert n % 2 == 1


# --- smooth ---


def wave(fps: float = 30.0, seconds: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    t = np.arange(int(seconds * fps)) / fps
    return t, 115 + 50 * np.cos(2 * np.pi * t / 2.4)  # bắt đầu ở đỉnh 165°, đáy 65° lúc 1,2 s


def test_constant_stays_constant() -> None:
    np.testing.assert_allclose(smooth(np.full(50, 160.0), 30, 0.25), 160.0)


def test_reduces_noise() -> None:
    _, clean = wave()
    noisy = clean + np.random.default_rng(0).normal(0, 3, clean.size)
    smoothed = smooth(noisy, 30, 0.25)
    assert np.std(smoothed - clean) < 0.6 * np.std(noisy - clean)


def test_bottom_position_shifts_at_most_two_frames() -> None:
    t, clean = wave()
    noisy = clean + np.random.default_rng(1).normal(0, 3, clean.size)
    smoothed = smooth(noisy, 30, 0.25)
    period = int(2.4 * 30)
    first_rep = slice(0, period)  # một đáy trong chu kỳ đầu
    assert abs(int(np.argmin(smoothed[first_rep])) - int(np.argmin(clean[first_rep]))) <= 2


def test_keeps_nan_positions() -> None:
    _, x = wave()
    x[100:140] = np.nan
    out = smooth(x, 30, 0.25)
    assert np.isnan(out[100:140]).all()
    assert np.isfinite(out[:100]).all() and np.isfinite(out[140:]).all()


def test_segment_shorter_than_window_left_as_is() -> None:
    x = np.array([np.nan, 1.0, 5.0, 2.0, np.nan])  # đoạn 3 điểm < cửa sổ 9
    np.testing.assert_array_equal(smooth(x, 30, 0.25), x)
