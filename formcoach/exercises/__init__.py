"""Bài tập: Exercise (lớp gốc), PushUp, Squat (mở rộng)."""

from formcoach.exercises.base import ErrorRule, Exercise
from formcoach.exercises.pushup import PushUp

# Tên bài (dùng trong file JSON và URL API) -> lớp. Thêm bài mới = thêm một dòng ở đây.
EXERCISES: dict[str, type[Exercise]] = {PushUp.name: PushUp}


def get_exercise(name: str) -> Exercise:
    """Tạo Exercise theo tên. Tên lạ → KeyError liệt kê các tên hợp lệ."""
    try:
        return EXERCISES[name]()
    except KeyError:
        raise KeyError(f"Bài tập không hỗ trợ: {name!r}. Hợp lệ: {sorted(EXERCISES)}") from None


__all__ = ["EXERCISES", "ErrorRule", "Exercise", "PushUp", "get_exercise"]
