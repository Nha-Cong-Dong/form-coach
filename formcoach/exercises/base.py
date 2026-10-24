"""Lớp gốc cho mọi bài tập. Thêm bài mới = thêm một lớp con, không sửa code chung."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ErrorRule:
    """Luật bắt một lỗi: lỗi xảy ra khi `features[feature] <op> threshold`.

    Ví dụ ErrorRule("min_elbow_angle", ">", 67.0): chưa xuống dưới 67° → shallow.
    `feature` là một khoá của Rep.features (vd "min_elbow_angle", "median_neck_angle").
    """

    feature: str
    op: Literal["<", ">"]
    threshold: float


class Exercise(ABC):
    """Mô tả một bài tập: đo góc nào, cắt rep bằng tín hiệu nào, ngưỡng bao nhiêu.

    Mọi ngưỡng của bài tập nằm ở đây, không nằm trong code xử lý tín hiệu.

    Lớp con khai báo hai thuộc tính lớp:
        name: tên bài, ví dụ "pushup".
        error_labels: các lỗi hợp lệ, ví dụ ["shallow", "hip_sag", ...]. Không gồm "good":
            nhãn là multi-label, rep không có lỗi nào (tập rỗng) là good.
    Tuỳ chọn:
        error_display: mã lỗi -> tên hiển thị cho người dùng (vd "hip_sag" -> "Hông võng").
            Lỗi không có trong đây thì giao diện hiện mã lỗi.
        measure_display: đặc trưng -> (tên, đơn vị) hiện số đo từng rep cho người dùng, vd
            "min_elbow_angle" -> ("Góc khuỷu ở đáy", "°"). Chỉ khai báo số đo người tập hiểu
            được; mục tiêu lấy từ `error_rules()` của lỗi dùng đặc trưng đó.
    """

    name: str
    error_labels: list[str]
    error_display: dict[str, str] = {}
    measure_display: dict[str, tuple[str, str]] = {}

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

    def offset_definitions(self) -> dict[str, tuple[str, str, str]]:
        """Tên tín hiệu -> (khớp P, khớp A, khớp B); độ lệch có dấu của P khỏi đường A–B.

        Chia cho độ dài A–B (không có đơn vị). Dương = P nằm phía trên đường theo ảnh, âm =
        phía dưới. Dùng cho lỗi lệch về hai phía mà góc 3 khớp không phân biệt được (hông nhô
        hay võng). Tên khớp không có tiền tố bên. Mặc định không có; bài nào cần thì ghi đè.
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
    def error_rules(self) -> dict[str, ErrorRule | None]:
        """Luật cho baseline phát hiện lỗi: mỗi lỗi trong `error_labels` một luật.

        None = chưa có ngưỡng (vd chưa đo được): RuleBased bỏ qua lỗi đó. Ngưỡng lấy từ
        docs/labeling-criteria.md, do người dùng quyết định, không tự chọn trong code.
        """
        ...
