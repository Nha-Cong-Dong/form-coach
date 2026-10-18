"""Push-up: góc khuỷu để đếm rep, góc thân để bắt lỗi hông, độ nghiêng thân để biết đang plank."""

from __future__ import annotations

from formcoach.exercises.base import Exercise


class PushUp(Exercise):
    name = "pushup"
    error_labels = ["shallow", "incomplete_lockout", "hip_sag", "hip_high", "neck_drop"]

    def angle_definitions(self) -> dict[str, tuple[str, str, str]]:
        return {
            "elbow_angle": ("shoulder", "elbow", "wrist"),  # ~160–170° thẳng tay, ~60–70° đáy
            "body_angle": ("shoulder", "hip", "ankle"),  # ~180° thân thẳng
        }

    def tilt_definitions(self) -> dict[str, tuple[str, str]]:
        return {"body_tilt": ("shoulder", "ankle")}  # nhỏ khi plank, ~90° khi đứng

    def primary_signal(self) -> str:
        return "elbow_angle"

    def phase_thresholds(self) -> dict[str, float]:
        # Số TẠM, ước từ probe bước 1 (góc khuỷu p5 ≈ 66–68°, p95 ≈ 158–169°).
        # Chỉnh lại ở bước 5 sau khi nhìn đồ thị góc theo thời gian.
        return {
            # Khuỷu > top_min = đã về tư thế trên. Thấp hơn hẳn góc đỉnh đo được (~160°)
            # để rep chưa duỗi hết tay (incomplete_lockout) vẫn được đếm.
            "top_min": 145.0,
            # Khuỷu < descent_trigger = bắt đầu xuống. Cách top_min 20° (hysteresis) để
            # nhiễu quanh một ngưỡng không bị đếm thành nhiều rep; đủ cao để rep nông vẫn đếm.
            "descent_trigger": 125.0,
            # Phải giữ plank thẳng tay ít nhất ngần này mới bắt đầu đếm.
            "ready_hold_s": 1.0,
            # Thân nghiêng quá góc này so với phương ngang = không phải plank (đứng, quỳ).
            "ready_max_tilt_deg": 35.0,
            # Rep ngắn hơn ngần này coi là nhiễu, bỏ qua.
            "min_rep_duration_s": 0.6,
            # Cửa sổ làm mượt Savitzky–Golay.
            "smoothing_window_s": 0.25,
        }

    def rule_thresholds(self) -> dict[str, float]:
        # Tuần 2: ngưỡng lỗi lấy từ docs/labeling-criteria.md, do người dùng quyết định.
        return {}
