"""Baseline luật: mỗi lỗi một luật độc lập trên đặc trưng của rep (multi-label).

Luật lấy từ `Exercise.error_rules()`; lớp này không biết gì về push-up, thêm bài mới không phải sửa.
"""

from __future__ import annotations

import math

from formcoach.exercises.base import ErrorRule, Exercise
from formcoach.models.base import FormClassifier
from formcoach.types import Rep, RepResult


def rule_fires(rule: ErrorRule, features: dict[str, float]) -> bool:
    """Luật có bắt lỗi ở rep này không. Thiếu đặc trưng hoặc NaN → không bắt.

    Không có dữ liệu (vd cả rep không thấy tai) thì không đủ căn cứ để kết luận là lỗi.
    """
    value = features.get(rule.feature)
    if value is None or not math.isfinite(value):
        return False
    return value < rule.threshold if rule.op == "<" else value > rule.threshold


class RuleBased(FormClassifier):
    """Phân loại bằng ngưỡng cố định. Lỗi chưa có luật (None) không bao giờ được dự đoán."""

    def __init__(self, exercise: Exercise) -> None:
        rules = exercise.error_rules()
        unknown = set(rules) - set(exercise.error_labels)
        if unknown:
            raise ValueError(f"error_rules có lỗi không thuộc error_labels: {sorted(unknown)}")
        self.rules = {name: rule for name, rule in rules.items() if rule is not None}
        # Lỗi không có luật: in ra cho người dùng biết, thay vì lặng lẽ coi như "không lỗi".
        self.missing = sorted(set(exercise.error_labels) - set(self.rules))

    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None:
        """Luật không học gì: ngưỡng cố định, chọn từ buổi quay thử (không phải từ tập train)."""

    def predict(self, reps: list[Rep]) -> list[RepResult]:
        return [
            RepResult(
                rep=rep,
                errors=frozenset(
                    n for n, rule in self.rules.items() if rule_fires(rule, rep.features)
                ),
                scores=None,
            )
            for rep in reps
        ]
