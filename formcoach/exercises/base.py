"""Lớp gốc cho mọi bài tập. Thêm bài mới = thêm một lớp con, không sửa code chung."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Exercise(ABC):
    """Mô tả một bài tập: đo góc nào, cắt rep bằng tín hiệu nào, ngưỡng bao nhiêu.

    Mọi ngưỡng của bài tập nằm ở đây, không nằm trong code xử lý tín hiệu.

    Lớp con khai báo hai thuộc tính lớp:
        name: tên bài, ví dụ "pushup".
        error_labels: các lỗi hợp lệ, ví dụ ["shallow", "hip_sag", ...]. Không gồm "good":
            nhãn là multi-label, rep không có lỗi nào (tập rỗng) là good.
    """

    name: str
    error_labels: list[str]

    @abstractmethod
    def angle_definitions(self) -> dict[str, tuple[str, str, str]]:
        """Tên góc -> (khớp A, khớp đỉnh B, khớp C); góc được đo tại B.

        Tên khớp KHÔNG có tiền tố bên, ví dụ "elbow_angle": ("shoulder", "elbow", "wrist").
        FeatureExtractor tự chọn bên trái/phải (bên nhìn rõ hơn trong cả hiệp)
        rồi ghép tiền tố "left_"/"right_".
        """
        ...

    def tilt_definitions(self) -> dict[str, tuple[str, str]]:
        """Tên tín hiệu -> (khớp A, khớp B); góc của đoạn A→B so với phương ngang, độ.

        0° = nằm ngang, 90° = dựng đứng. Dùng để biết thân đang nằm (plank) hay đứng,
        điều mà góc 3 khớp không cho biết. Tên khớp không có tiền tố bên, như trên.
        Mặc định không có; bài nào cần thì ghi đè.
        """
        return {}

    @abstractmethod
    def primary_signal(self) -> str:
        """Tên tín hiệu dùng để cắt rep, phải là một khoá của `angle_definitions()`."""
        ...

    @abstractmethod
    def phase_thresholds(self) -> dict[str, float]:
        """Ngưỡng cho máy trạng thái cắt rep.

        Góc tính bằng độ. Ngưỡng thời gian tính bằng GIÂY và có hậu tố `_s`
        (ví dụ "min_rep_duration_s"), đổi sang số frame bằng fps lúc chạy.
        Gồm ngưỡng "chờ sẵn sàng" (giữ tư thế đầu đủ lâu mới bắt đầu đếm). Ngưỡng
        "đã về tư thế đầu" phải lỏng hơn ngưỡng lỗi tương ứng, để rep mắc lỗi vẫn được đếm.
        """
        ...

    @abstractmethod
    def rule_thresholds(self) -> dict[str, float]:
        """Ngưỡng cho baseline phát hiện lỗi bằng luật (dùng từ tuần 2)."""
        ...
