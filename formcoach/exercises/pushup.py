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
        # Chỉnh theo đồ thị 3 clip thử (2026-10-19, tools/plot_signals.py): đỉnh khuỷu 150–170°,
        # đáy rep sâu ~60–70°, rep nông ~100–114°, thân lúc plank 0–18°, lúc đứng/quỳ 60–90°,
        # một rep ~2,4–2,8 s. Dữ liệu từ trang quay (MediaPipe JS) có thể cần chỉnh lại.
        return {
            # Khuỷu > top_min = đã về tư thế trên. Đỉnh thấp nhất đo được ~150°; để 140°
            # nên rep chưa duỗi hết tay (incomplete_lockout) vẫn được đếm.
            "top_min": 140.0,
            # Khuỷu < descent_trigger = bắt đầu xuống. Rep nông nhất xuống 114° vẫn dưới ngưỡng;
            # cách top_min 15° (hysteresis) để nhiễu quanh một ngưỡng không thành nhiều rep.
            "descent_trigger": 125.0,
            # Phải giữ plank thẳng tay ít nhất ngần này mới bắt đầu đếm. 1,0 s làm mất rep đầu
            # của clip bắt đầu ngay ở plank (chỉ giữ 0,8 s rồi xuống).
            "ready_hold_s": 0.5,
            # Thân nghiêng quá góc này so với phương ngang = không phải plank (đứng, quỳ).
            "ready_max_tilt_deg": 35.0,
            # Rep ngắn hơn ngần này coi là nhiễu, bỏ qua. "Thời lượng" = lúc khuỷu rời khỏi
            # vùng trên top_min tới lúc quay lại (không phải chu kỳ đáy-đáy ~2,4 s). Đo được:
            # rep thường 1,1–1,7 s, rep nông/nhanh (hông nhô cao) chỉ ~0,7 s → 0,8 s làm sót rep.
            "min_rep_duration_s": 0.4,
            # Cửa sổ làm mượt Savitzky–Golay.
            "smoothing_window_s": 0.25,
            # Lỗ NaN (mất người) ngắn hơn ngần này thì nội suy lấp; dài hơn giữ NaN.
            "max_gap_s": 0.3,
        }

    def rule_thresholds(self) -> dict[str, float]:
        # Tuần 2: ngưỡng lỗi lấy từ docs/labeling-criteria.md, do người dùng quyết định.
        return {}
