"""Cắt chuỗi tín hiệu thành từng rep bằng máy trạng thái (State pattern), đếm theo BIÊN ĐỘ.

Máy trạng thái nhận TỪNG MẪU một (`RepStateMachine.step`), nên tuần 3 bộ đếm realtime
(OnlineRepCounter) dùng lại được nguyên; `RepSegmenter` chỉ là vòng lặp chạy nó trên cả hiệp.

Đếm theo biên độ thay cho ngưỡng cố định (đổi ngày 2026-10-20): rep chưa duỗi hết tay (đỉnh chỉ
~110–135°) và rep nông (đáy ~100–114°) đòi hai ngưỡng cố định ngược nhau; biên độ thì không.
Gọi D = min_amplitude_deg:

    WAITING_READY ──(góc > top_min và thân nằm, giữ ready_hold_s)──► UP
    UP   (theo dõi đỉnh) ──(góc ≤ đỉnh − D)──► DOWN       ; nếu đang có rep chờ → chốt rep đó
    DOWN (theo dõi đáy)  ──(góc ≥ đáy + D)──► UP, có "rep chờ" (đã đếm được, chưa biết đỉnh cuối)
    bất kỳ ──(thân dựng lên / mất tín hiệu)──► WAITING_READY  ; rep chờ (nếu có) được chốt

Ranh giới rep (sửa 2026-10-20): đỉnh tuyệt đối dễ rơi vào lúc giữ plank chờ hoặc lúc rời tư thế
(tay duỗi thêm khi đứng dậy), kéo rep lấn sang những đoạn đó. Nên ranh giới dựa vào độ ổn định
cục bộ, với T = top_tolerance_deg, W = top_settle_s:
- rep KẾT THÚC ở khung đầu tiên (sau đáy) mà trong W giây tới góc không tăng thêm quá T ("đã lên");
- rep BẮT ĐẦU ở khung cuối cùng (trước khi xuống) mà trong W giây trước đó góc chưa từng cao hơn
  nó quá T ("chưa tụt").
Thời gian nghỉ ở đỉnh giữa hai rep không tính vào rep nào.
Dao động nhỏ hơn D (nhiễu, giữ plank) không tạo rep: đây là hysteresis theo biên độ.
Rep chỉ xuống rồi dừng ở đáy (chưa lên lại D) không được đếm.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from formcoach.exercises.base import Exercise
from formcoach.types import FeatureSeries, Rep


class Phase(Enum):
    WAITING_READY = auto()
    UP = auto()
    DOWN = auto()


@dataclass(frozen=True)
class RepSpan:
    """Vị trí một rep trong chuỗi khung (chưa có đặc trưng)."""

    start_frame: int
    bottom_frame: int
    end_frame: int


class RepStateMachine:
    """Nhận từng mẫu (góc chính, độ nghiêng thân), trả rep khi nó được chốt."""

    def __init__(self, exercise: Exercise, fps: float) -> None:
        th = exercise.phase_thresholds()
        self.top_min = th["top_min"]
        self.amplitude = th["min_amplitude_deg"]
        self.tolerance = th["top_tolerance_deg"]
        self.settle_frames = max(1, int(round(th["top_settle_s"] * fps)))
        self.max_tilt = th["ready_max_tilt_deg"]
        self.ready_frames = max(1, int(round(th["ready_hold_s"] * fps)))
        self.min_rep_frames = int(round(th["min_rep_duration_s"] * fps))
        self.reset()

    def reset(self) -> None:
        self.phase = Phase.WAITING_READY
        self.ready_count = 0
        self.top_value = -np.inf  # đỉnh của pha UP hiện tại (chỉ dùng để phát hiện xuống)
        self.up_first = -1  # khung đầu của pha UP hiện tại
        self.up_angles: list[float] = []  # góc từng khung của pha UP: tìm ranh giới rep
        self.bottom_frame, self.bottom_value = -1, np.inf  # đáy đang theo dõi (pha DOWN)
        self.rep_start = -1
        self.pending: tuple[int, int] | None = None  # (start, bottom) của rep đã đếm, chờ đỉnh cuối

    @property
    def has_pending(self) -> bool:
        """Có rep đã đủ biên độ nhưng chưa chốt đỉnh cuối (bộ đếm realtime đếm luôn rep này)."""
        return self.pending is not None

    def _enter_up(self, i: int, angle: float) -> None:
        self.phase = Phase.UP
        self.top_value, self.up_first, self.up_angles = angle, i, [angle]

    def _settled_end(self) -> int:
        """Khung đầu tiên của pha UP mà W khung tới không tăng thêm quá T."""
        a, w = self.up_angles, self.settle_frames
        k = next(k for k in range(len(a)) if max(a[k : k + w + 1]) <= a[k] + self.tolerance)
        return self.up_first + k  # luôn có: khung cuối cùng tự thoả

    def _settled_start(self) -> int:
        """Khung cuối cùng của pha UP mà W khung trước đó không cao hơn nó quá T."""
        a, w = self.up_angles, self.settle_frames
        k = next(
            k
            for k in reversed(range(len(a)))
            if max(a[max(0, k - w) : k + 1]) <= a[k] + self.tolerance
        )
        return self.up_first + k  # luôn có: khung đầu tiên tự thoả

    def _close_pending(self) -> RepSpan | None:
        """Chốt rep chờ tại điểm "đã lên" của pha UP hiện tại; bỏ nếu quá ngắn."""
        if self.pending is None:
            return None
        start, bottom = self.pending
        self.pending = None
        end = self._settled_end()
        if end - start < self.min_rep_frames:
            return None
        return RepSpan(start, bottom, end)

    def step(self, i: int, angle: float, tilt: float) -> RepSpan | None:
        """Xử lý khung i. Trả RepSpan nếu khung này chốt xong một rep, ngược lại None."""
        lying = np.isfinite(tilt) and tilt <= self.max_tilt
        if not np.isfinite(angle) or not lying:
            # Mất tín hiệu, hoặc thân dựng lên (đứng, quỳ): không phải đang tập → chờ lại.
            # Rep đã lên lại đủ biên độ thì vẫn tính (vd đẩy lên rồi đứng dậy luôn).
            span = self._close_pending() if self.phase is Phase.UP else None
            self.reset()
            return span

        if self.phase is Phase.WAITING_READY:
            self.ready_count = self.ready_count + 1 if angle > self.top_min else 0
            if self.ready_count >= self.ready_frames:
                self._enter_up(i, angle)
            return None

        if self.phase is Phase.UP:
            if angle > self.top_value - self.amplitude:
                self.up_angles.append(angle)
                self.top_value = max(self.top_value, angle)
                return None
            # Đã xuống ≥ D so với đỉnh: chốt rep trước (nếu có), rep mới bắt đầu.
            span = self._close_pending()
            self.rep_start = self._settled_start()
            self.phase = Phase.DOWN
            self.bottom_frame, self.bottom_value = i, angle
            return span

        # Phase.DOWN
        if angle < self.bottom_value:
            self.bottom_frame, self.bottom_value = i, angle
        elif angle >= self.bottom_value + self.amplitude:
            self.pending = (self.rep_start, self.bottom_frame)
            self._enter_up(i, angle)
        return None

    def finish(self) -> RepSpan | None:
        """Hết tín hiệu: chốt rep chờ (nếu có). Rep đang xuống dở thì bỏ."""
        span = self._close_pending() if self.phase is Phase.UP else None
        self.reset()
        return span


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
            # Trung vị: tư thế giữ suốt rep (cổ gục, hông võng). min/max chỉ là MỘT khung nên bị
            # nhiễu kéo đi: góc cổ nhảy ±10° giữa các khung (buổi quay thử 2026-10-20).
            feats[f"median_{name}"] = float(np.nanmedian(values))
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
        spans = [
            machine.step(i, float(a), float(t))
            for i, (a, t) in enumerate(zip(angle, tilt, strict=True))
        ]
        spans.append(machine.finish())

        top_name = f"top_{exercise.primary_signal()}"

        def features_of(span: RepSpan) -> dict[str, float]:
            feats = _rep_features(span, signals, features.fps)
            # Đỉnh SAU rep (cho incomplete_lockout): rep kết thúc ở chỗ "đã lên gần hết", đỉnh
            # thật nằm trong top_settle_s ngay sau đó. max_<góc> trong rep không phải đỉnh này.
            after = angle[span.end_frame : span.end_frame + machine.settle_frames + 1]
            if np.isfinite(after).any():
                feats[top_name] = float(np.nanmax(after))
            return feats

        return [
            Rep(index=k, start_frame=s.start_frame, end_frame=s.end_frame, features=features_of(s))
            for k, s in enumerate(s for s in spans if s is not None)
        ]
