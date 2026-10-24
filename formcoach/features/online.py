"""Đếm rep TRỰC TIẾP, từng khung một, khi đang tập (Track C). Chỉ để hiển thị.

Dùng lại nguyên `RepStateMachine` và ngưỡng của `Exercise` như bộ đếm cả hiệp (`analyze`), chỉ
khác ở những chỗ không thể nhìn tương lai:
- Bên trái/phải: chạy SONG SONG một máy trạng thái cho mỗi bên, hiển thị bên nhìn rõ hơn tính
  tới khung hiện tại (visibility trung bình từ đầu hiệp, cùng cách `choose_side` tính trên cả
  hiệp). Không khoá bên sớm: 1 s đầu thường là lúc còn đứng gần máy, bên gần máy rõ hơn nhưng
  khi nằm xuống tập thì bên kia mới rõ (đo trên dữ liệu thật 2026-10-24: khoá sau 1 s sai bên ở
  9/44 hiệp, đếm ra 0).
- Lỗ mất tín hiệu ngắn: giữ giá trị cuối tối đa `max_gap_s` (cả hiệp thì nội suy hai đầu lỗ).
- Làm mượt: trung vị của vài khung gần nhất (nhân quả) thay Savitzky–Golay (nhìn cả hai phía).

Số đếm = rep đã chốt + 1 nếu đang có rep chờ (đã lên lại đủ biên độ, chưa chốt đỉnh cuối): số
tăng ngay khi vừa đẩy lên. Có thể lệch ±1 so với `analyze` (rep sát ngưỡng, lúc kết thúc hiệp);
kết quả từng rep luôn lấy từ `analyze` trên hiệp đã lưu, không lấy từ bộ đếm này.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from formcoach.exercises.base import Exercise
from formcoach.features.extractor import SIDES, used_joints
from formcoach.features.geometry import joint_angle, segment_tilt, to_pixel_space
from formcoach.features.segmenter import RepStateMachine
from formcoach.pose.joints import MEDIAPIPE_JOINTS


class _SideTrack:
    """Máy trạng thái + bộ lọc nhân quả cho MỘT bên (trái hoặc phải)."""

    def __init__(self, exercise: Exercise, fps: float) -> None:
        th = exercise.phase_thresholds()
        self.max_gap = int(round(th["max_gap_s"] * fps))
        # Trung vị nhân quả trễ ~nửa cửa sổ: dùng nửa cửa sổ của bộ lọc cả hiệp cho đỡ trễ.
        self.window = max(1, int(round(th["smoothing_window_s"] / 2 * fps)))
        self.machine = RepStateMachine(exercise, fps)
        self.completed = 0
        self.i = 0
        self.vis_sum, self.vis_n = 0.0, 0  # visibility các khớp bài tập dùng, cộng dồn
        # Mỗi tín hiệu: giá trị đáng tin gần nhất + số khung đã giữ, và cửa sổ trung vị.
        self._last: dict[str, tuple[float, int]] = {}
        self._recent: dict[str, deque[float]] = {}

    @property
    def count(self) -> int:
        return self.completed + (1 if self.machine.has_pending else 0)

    @property
    def mean_visibility(self) -> float:
        return self.vis_sum / self.vis_n if self.vis_n else float("nan")

    def clean(self, name: str, value: float, reliable: bool) -> float:
        """Bỏ giá trị không tin được, giữ giá trị cuối qua lỗ ngắn, rồi trung vị nhân quả."""
        if reliable and np.isfinite(value):
            self._last[name] = (value, 0)
        elif name in self._last and self._last[name][1] < self.max_gap:
            held, age = self._last[name]
            self._last[name] = (held, age + 1)
            value = held
        else:
            self._last.pop(name, None)
            self._recent.pop(name, None)
            return float("nan")  # mất tín hiệu quá lâu: máy trạng thái về chờ
        recent = self._recent.setdefault(name, deque(maxlen=self.window))
        recent.append(value)
        return float(np.median(recent))

    def step(self, angle: float, tilt: float) -> None:
        if self.machine.step(self.i, float(angle), float(tilt)) is not None:
            self.completed += 1
        self.i += 1

    def finish(self) -> int:
        if self.machine.finish() is not None:
            self.completed += 1
        return self.completed


class OnlineRepCounter:
    """Nhận từng khung keypoint (K, 3) = [x, y, visibility] chuẩn hoá 0–1, trả số rep hiện tại."""

    def __init__(
        self,
        exercise: Exercise,
        fps: float,
        frame_size: tuple[int, int],
        joint_names: list[str] | None = None,
    ) -> None:
        self.exercise = exercise
        self.frame_size = frame_size
        names = joint_names or list(MEDIAPIPE_JOINTS)
        self._index = {n: i for i, n in enumerate(names)}
        self.min_visibility = exercise.phase_thresholds()["min_joint_visibility"]
        self._used = used_joints(exercise)
        self.tracks = {s: _SideTrack(exercise, fps) for s in SIDES}

    # --- công khai ---

    @property
    def side(self) -> str:
        """Bên đang hiển thị: rõ hơn tính tới giờ (như `choose_side`: hoà / chưa thấy → trái)."""
        left, right = (self.tracks[s].mean_visibility for s in SIDES)
        if np.isfinite(right) and (not np.isfinite(left) or right > left):
            return "right"
        return "left"

    @property
    def count(self) -> int:
        """Rep đã chốt + rep đang chờ chốt (đã lên lại đủ biên độ), của bên đang hiển thị."""
        return self.tracks[self.side].count

    @property
    def completed(self) -> int:
        """Rep đã chốt (không tính rep đang chờ), của bên đang hiển thị."""
        return self.tracks[self.side].completed

    @property
    def phase(self) -> str:
        """Pha của bên đang hiển thị: "waiting_ready" | "up" | "down" (để hiển thị)."""
        return self.tracks[self.side].machine.phase.name.lower()

    def update(self, keypoints: np.ndarray) -> int:
        """Một khung (K, 3); không thấy người thì đưa mảng NaN. Trả số rep hiện tại."""
        kp = np.asarray(keypoints, dtype=float)
        for side, track in self.tracks.items():
            self._process(kp, side, track)
        return self.count

    def update_signals(self, angle: float, tilt: float) -> int:
        """Đưa thẳng góc chính và độ nghiêng (đã làm mượt) vào máy trạng thái (cả hai bên như
        nhau). Dùng cho test lớp bọc và cho nguồn đã tính sẵn tín hiệu."""
        for track in self.tracks.values():
            track.step(angle, tilt)
        return self.count

    def finish(self) -> int:
        """Hết hiệp: chốt rep đang chờ (nếu có), trả số rep cuối của bên rõ hơn cả hiệp."""
        side = self.side  # chọn trước khi finish (finish không đổi visibility, chỉ cho chắc)
        for track in self.tracks.values():
            track.finish()
        return self.tracks[side].completed

    # --- bên trong ---

    def _xy(self, kp: np.ndarray, side: str, joint: str) -> np.ndarray:
        return to_pixel_space(kp[self._index[f"{side}_{joint}"], :2], self.frame_size)

    def _reliable(self, kp: np.ndarray, side: str, joints: tuple[str, ...]) -> bool:
        v = kp[[self._index[f"{side}_{j}"] for j in joints], 2]
        return float(np.nan_to_num(v, nan=0.0).min()) >= self.min_visibility

    def _process(self, kp: np.ndarray, side: str, track: _SideTrack) -> None:
        vis = kp[[self._index[f"{side}_{j}"] for j in self._used], 2]
        vis = vis[np.isfinite(vis)]
        track.vis_sum += float(vis.sum())
        track.vis_n += int(vis.size)

        ex = self.exercise
        a, b, c = ex.angle_definitions()[ex.primary_signal()]
        angle = float(
            joint_angle(self._xy(kp, side, a), self._xy(kp, side, b), self._xy(kp, side, c))
        )
        angle = track.clean("angle", angle, self._reliable(kp, side, (a, b, c)))
        tilts = []
        for name, (p, q) in ex.tilt_definitions().items():
            t = float(segment_tilt(self._xy(kp, side, p), self._xy(kp, side, q)))
            tilts.append(track.clean(name, t, self._reliable(kp, side, (p, q))))
        # Như RepSegmenter: nhiều tín hiệu nghiêng thì lấy lớn nhất (np.max: một NaN thì NaN);
        # không có tín hiệu nghiêng thì coi như đang nằm.
        tilt = float(np.max(tilts)) if tilts else 0.0
        track.step(angle, tilt)
