"""Ghi chú điều kiện quay của hiệp thí nghiệm (evaluation/capture_conditions.py).

Hiệp thí nghiệm quay bằng màn Quay dữ liệu, cố ý tập đúng, ô ghi chú theo mẫu (thứ tự tuỳ ý):
    ao:khong goc:0 rep:10      (cởi trần, máy ngang hông, tập 10 rep)
    ao:co goc:20 rep:10        (mặc áo, máy lệch ~20°)
Đặt ở formcoach/ (không ở evaluation/) vì `build_dataset` cần nhận ra để loại các hiệp này.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SHIRT = re.compile(r"\bao:(co|khong)\b")
_ANGLE = re.compile(r"\bgoc:(\d{1,2})\b")
_REPS = re.compile(r"\brep:(\d{1,3})\b")


@dataclass(frozen=True)
class Condition:
    shirt: bool
    angle: int  # độ lệch ước lượng so với ngang hông
    reps_done: int | None  # số rep thật sự tập (người quay ghi), để kiểm tra bộ đếm

    @property
    def key(self) -> tuple[bool, int]:
        return (self.shirt, self.angle)


def parse_condition(notes: str) -> Condition | None:
    """Ghi chú theo mẫu `ao:co|khong goc:<độ> [rep:<số>]` → điều kiện; thiếu ao/goc → None."""
    shirt, angle = _SHIRT.search(notes), _ANGLE.search(notes)
    if not shirt or not angle:
        return None
    reps = _REPS.search(notes)
    return Condition(
        shirt.group(1) == "co", int(angle.group(1)), int(reps.group(1)) if reps else None
    )
