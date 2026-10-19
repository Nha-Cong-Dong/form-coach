"""Làm sạch tín hiệu trước khi đếm rep: lấp lỗ NaN ngắn, rồi làm mượt.

Thứ tự dùng: interpolate_gaps → smooth. Lỗ NaN dài (mất người lâu) được giữ nguyên NaN:
bịa dữ liệu cho cả giây là không đáng tin.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter

POLYORDER = 2  # đa thức bậc 2 khớp được đáy sóng cong, không làm bẹt đáy như trung bình trượt


def _finite_runs(x: np.ndarray) -> list[tuple[int, int]]:
    """Các đoạn liên tiếp không NaN, dạng [start, stop)."""
    finite = np.isfinite(x)
    edges = np.diff(np.concatenate([[False], finite, [False]]).astype(int))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True))


def interpolate_gaps(x: np.ndarray, max_gap: int) -> np.ndarray:
    """Lấp các lỗ NaN dài tối đa `max_gap` khung bằng nội suy tuyến tính.

    Chỉ lấp lỗ nằm GIỮA hai giá trị thật. NaN ở đầu/cuối và lỗ dài hơn max_gap giữ nguyên.
    """
    x = np.asarray(x, dtype=float)
    out = x.copy()
    runs = _finite_runs(x)
    for (_, prev_stop), (next_start, _) in zip(runs, runs[1:], strict=False):
        gap = next_start - prev_stop
        if gap <= max_gap:
            left, right = prev_stop - 1, next_start
            out[prev_stop:next_start] = np.interp(
                np.arange(prev_stop, next_start), [left, right], [x[left], x[right]]
            )
    return out


def window_frames(fps: float, window_s: float) -> int:
    """Đổi cửa sổ từ giây sang số khung LẺ (Savitzky–Golay cần cửa sổ lẻ), tối thiểu 3."""
    n = int(round(window_s * fps))
    if n % 2 == 0:
        n += 1
    return max(n, 3)  # cửa sổ phải lớn hơn POLYORDER (= 2)


def smooth(x: np.ndarray, fps: float, window_s: float) -> np.ndarray:
    """Làm mượt Savitzky–Golay, cửa sổ tính theo giây nên không phụ thuộc fps.

    savgol_filter không chịu được NaN, nên làm mượt riêng từng đoạn liên tục; NaN giữ nguyên.
    Đoạn ngắn hơn cửa sổ thì để nguyên (quá ít điểm để khớp đa thức).
    """
    x = np.asarray(x, dtype=float)
    out = x.copy()
    win = window_frames(fps, window_s)
    for start, stop in _finite_runs(x):
        if stop - start >= win:
            out[start:stop] = savgol_filter(x[start:stop], win, POLYORDER)
    return out
