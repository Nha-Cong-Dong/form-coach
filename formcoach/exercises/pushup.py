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
            # Cổ thẳng theo thân ~180°; gục đầu xuống hoặc rướn cổ lên đều làm góc nhỏ đi (cả hai
            # là neck_drop). Thử nghiệm: tai khi quay ngang có thể đặt kém chính xác.
            "neck_angle": ("ear", "shoulder", "hip"),
        }

    def tilt_definitions(self) -> dict[str, tuple[str, str]]:
        return {"body_tilt": ("shoulder", "ankle")}  # nhỏ khi plank, ~90° khi đứng

    def offset_definitions(self) -> dict[str, tuple[str, str, str]]:
        # Dương = hông cao hơn đường vai–cổ chân (hip_high), âm = võng (hip_sag); tính theo
        # phần độ dài vai–cổ chân. body_angle không biết cong lên hay xuống: góc thân của hiệp
        # hip_sag (158–170°) trùng với tập đúng (162–171°) ở buổi quay thử.
        return {"hip_offset": ("hip", "shoulder", "ankle")}

    def primary_signal(self) -> str:
        return "elbow_angle"

    def phase_thresholds(self) -> dict[str, float]:
        # Chỉnh theo đồ thị 3 clip thử (2026-10-19, `python -m formcoach analyze --plot`):
        # đỉnh khuỷu 150–170°, đáy rep sâu ~60–70°, rep nông ~100–114°, thân lúc plank 0–18°,
        # lúc đứng/quỳ 60–90°, một rep ~2,4–2,8 s. Dữ liệu từ trang quay (MediaPipe JS) có thể
        # cần chỉnh lại.
        return {
            # Chỉ dùng cho trạng thái sẵn sàng: phải giữ plank với khuỷu > top_min mới bắt đầu
            # đếm. Không còn dùng để biết "đã lên lại" (xem min_amplitude_deg).
            "top_min": 140.0,
            # Đếm theo biên độ (2026-10-20): bắt đầu xuống khi khuỷu giảm ≥ ngần này so với đỉnh,
            # tính rep khi tăng lại ≥ ngần này so với đáy. Biên độ đo được: rep đúng ~110°,
            # rep chưa duỗi hết tay 70–87° (đỉnh chỉ 110–135°), rep nông ~60°; nhiễu vài độ.
            # Ngưỡng cố định cũ (descent_trigger 125°, phải lên lại > 140°) gộp 4 rep chưa
            # duỗi hết tay thành 1 rep.
            "min_amplitude_deg": 35.0,
            # Ranh giới rep (2026-10-20): rep kết thúc ở khung đầu tiên mà trong top_settle_s tới
            # khuỷu không tăng thêm quá top_tolerance_deg ("đã lên"); bắt đầu ở khung cuối cùng mà
            # trong top_settle_s trước đó khuỷu chưa cao hơn nó quá ngần ấy ("chưa tụt"). Lấy đỉnh
            # tuyệt đối thì lúc giữ plank chờ (khuỷu dao động 155–176°) và lúc đứng dậy (tay duỗi
            # thêm tới 179°) bị tính vào rep 1 và rep cuối: rep 1 dài 10,2 s, góc thân rep cuối
            # tụt ~133° (buổi quay thử). T phải lớn hơn nhiễu và nhỏ hơn hẳn min_amplitude_deg.
            "top_tolerance_deg": 10.0,
            "top_settle_s": 0.5,
            # Phải giữ plank thẳng tay ít nhất ngần này mới bắt đầu đếm. 1,0 s làm mất rep đầu
            # của clip bắt đầu ngay ở plank (chỉ giữ 0,8 s rồi xuống).
            "ready_hold_s": 0.5,
            # Thân nghiêng quá góc này so với phương ngang = không phải plank (đứng, quỳ).
            "ready_max_tilt_deg": 35.0,
            # Rep ngắn hơn ngần này coi là nhiễu, bỏ qua. "Thời lượng" = từ đỉnh trước tới đỉnh
            # sau của rep (đếm theo biên độ); rep thật ~1,5–2,5 s, cú giật nhiễu ~0,3 s.
            "min_rep_duration_s": 0.4,
            # Cửa sổ làm mượt Savitzky–Golay.
            "smoothing_window_s": 0.25,
            # Lỗ NaN (mất người) ngắn hơn ngần này thì nội suy lấp; dài hơn giữ NaN.
            "max_gap_s": 0.3,
            # Khớp nào của một góc có visibility dưới ngưỡng này thì góc ở khung đó = NaN
            # (MediaPipe đoán bừa). Lúc tập thật bên gần camera ~0,95; lúc đi lại sát điện thoại
            # để bấm Xong tụt ~0,2 và đã tạo một rep ma (2026-10-19).
            "min_joint_visibility": 0.5,
        }

    def rule_thresholds(self) -> dict[str, float]:
        # Tuần 2: ngưỡng lỗi lấy từ docs/labeling-criteria.md, do người dùng quyết định.
        return {}
