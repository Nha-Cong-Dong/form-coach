"""Một nơi tạo bộ phân loại theo tên, dùng chung cho đánh giá (evaluation/) và app (backend/).

Siêu tham số của mô hình (không phải ngưỡng lỗi: ngưỡng lỗi nằm ở `Exercise.error_rules`) đặt
ở đây, một chỗ duy nhất, để mô hình được chấm điểm chính là mô hình được dùng trong app. Thêm mô
hình mới = thêm một dòng vào `_FACTORIES`.
"""

from __future__ import annotations

from collections.abc import Callable

from formcoach.exercises.base import Exercise
from formcoach.models.base import FormClassifier
from formcoach.models.rule_based import RuleBased
from formcoach.models.stump import LearnedThreshold


def _random_forest(exercise: Exercise, seed: int) -> FormClassifier:
    # Import trễ: scikit-learn nặng, chỉ cần khi thật sự dùng random forest (backend chạy luật
    # không phải trả giá import).
    from formcoach.models.random_forest import RandomForest

    return RandomForest(exercise, seed=seed)


# tên -> (bài tập, seed) -> bộ phân loại. `seed` chỉ có tác dụng với mô hình có ngẫu nhiên.
_FACTORIES: dict[str, Callable[[Exercise, int], FormClassifier]] = {
    "rules": lambda exercise, seed: RuleBased(exercise),
    "stump": lambda exercise, seed: LearnedThreshold(exercise),
    "rf": _random_forest,
}


def classifier_names() -> list[str]:
    return list(_FACTORIES)


def make_classifier(name: str, exercise: Exercise, seed: int = 0) -> FormClassifier:
    """Bộ phân loại MỚI (chưa fit) theo tên. Tên lạ → ValueError liệt kê các tên hợp lệ."""
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(f"Mô hình không hỗ trợ: {name!r}. Hợp lệ: {classifier_names()}") from None
    return factory(exercise, seed)
