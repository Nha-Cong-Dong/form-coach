"""Cắt chuỗi tín hiệu thành từng rep bằng máy trạng thái (State pattern).

Máy trạng thái nhận TỪNG MẪU một (`RepStateMachine.step`), nên tuần 3 bộ đếm realtime
(OnlineRepCounter) dùng lại được nguyên; `RepSegmenter` chỉ là vòng lặp chạy nó trên cả hiệp.

Trạng thái:
    WAITING_READY ──(khuỷu > top_min và thân nằm, giữ ready_hold_s)──► TOP
    TOP ──(khuỷu < descent_trigger)──► DOWN
    DOWN ──(khuỷu > top_min, rep đủ dài)──► TOP, +1 rep
    bất kỳ ──(thân dựng lên, hoặc mất tín hiệu)──► WAITING_READY, bỏ rep đang dở
Hai ngưỡng khác nhau (top_min > descent_trigger) là hysteresis: dao động nhiễu quanh một
ngưỡng không tạo ra rep giả.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from formcoach.exercises.base import Exercise
from formcoach.types import FeatureSeries, Rep


class Phase(Enum):
    WAITING_READY = auto()
    TOP = auto()
    DOWN = auto()


@dataclass(frozen=True)
class RepSpan:
    """Vị trí một rep trong chuỗi khung (chưa có đặc trưng)."""

    start_frame: int
    bottom_frame: int
    end_frame: int


class RepStateMachine:
    """Nhận từng mẫu (góc chính, độ nghiêng thân), báo khi vừa xong một rep."""

    def __init__(self, exercise: Exercise, fps: float) -> None:
        th = exercise.phase_thresholds()
        self.top_min = th["top_min"]
        self.descent_trigger = th["descent_trigger"]
        self.max_tilt = th["ready_max_tilt_deg"]
        self.ready_frames = max(1, int(round(th["ready_hold_s"] * fps)))
        self.min_rep_frames = int(round(th["min_rep_duration_s"] * fps))
        self.reset()

    def reset(self) -> None:
        self.phase = Phase.WAITING_READY
        self.ready_count = 0
        self.last_top = -1  # khung gần nhất còn ở tư thế trên, dùng làm điểm bắt đầu rep
        self.rep_start = -1
        self.bottom = -1
        self.bottom_value = np.inf

    def step(self, i: int, angle: float, tilt: float) -> RepSpan | None:
        """Xử lý khung i. Trả RepSpan nếu khung này kết thúc một rep hợp lệ, ngược lại None."""
        lying = np.isfinite(tilt) and tilt <= self.max_tilt
        if not np.isfinite(angle) or not lying:
            # Mất tín hiệu, hoặc thân dựng lên (đứng, quỳ): không phải đang tập → chờ lại.
            self.reset()
            return None

        if self.phase is Phase.WAITING_READY:
            self.ready_count = self.ready_count + 1 if angle > self.top_min else 0
            if self.ready_count >= self.ready_frames:
                self.phase = Phase.TOP
                self.last_top = i
            return None

        if self.phase is Phase.TOP:
            if angle >= self.top_min:
                self.last_top = i
            elif angle < self.descent_trigger:
                self.phase = Phase.DOWN
                self.rep_start = self.last_top
                self.bottom, self.bottom_value = i, angle
            return None

        # Phase.DOWN
        if angle < self.bottom_value:
            self.bottom, self.bottom_value = i, angle
        if angle > self.top_min:
            span = RepSpan(self.rep_start, self.bottom, i)
            self.phase = Phase.TOP
            self.last_top = i
            if i - self.rep_start >= self.min_rep_frames:
                return span
        return None


def _rep_features(span: RepSpan, signals: dict[str, np.ndarray], fps: float) -> dict[str, float]:
    window = slice(span.start_frame, span.end_frame + 1)
    feats: dict[str, float] = {
        "bottom_frame": float(span.bottom_frame),
        "duration_s": (span.end_frame - span.start_frame) / fps,
        "descent_time_s": (span.bottom_frame - span.start_frame) / fps,
    }
    for name, sig in signals.items():
        if name.endswith("_raw"):
            continue
        values = sig[window]
        if np.isfinite(values).any():
            feats[f"min_{name}"] = float(np.nanmin(values))
            feats[f"max_{name}"] = float(np.nanmax(values))
    return feats


class RepSegmenter:
    """Cắt cả hiệp thành list[Rep]. Tín hiệu đầu vào nên đã được làm mượt (FeatureExtractor)."""

    def segment(self, features: FeatureSeries, exercise: Exercise) -> list[Rep]:
        signals = features.signals
        angle = signals[exercise.primary_signal()]
        tilt_names = list(exercise.tilt_definitions())
        if tilt_names:
            # Nhiều tín hiệu nghiêng thì lấy cái lớn nhất: chỉ cần một đoạn dựng lên là không nằm.
            tilt = np.max(np.stack([signals[n] for n in tilt_names]), axis=0)
        else:
            tilt = np.zeros_like(angle)

        machine = RepStateMachine(exercise, features.fps)
        reps: list[Rep] = []
        for i, (a, t) in enumerate(zip(angle, tilt, strict=True)):
            span = machine.step(i, float(a), float(t))
            if span is not None:
                reps.append(
                    Rep(
                        index=len(reps),
                        start_frame=span.start_frame,
                        end_frame=span.end_frame,
                        features=_rep_features(span, signals, features.fps),
                    )
                )
        return reps
