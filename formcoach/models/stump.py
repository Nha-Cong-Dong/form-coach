"""Ngưỡng học: giống luật tay (cùng đặc trưng, cùng chiều so sánh) nhưng CON SỐ ngưỡng do máy
học từ tập train.

Đặc trưng và chiều so sánh của từng lỗi lấy từ `Exercise.error_rules()` (kiến thức về bài tập nằm ở
config, không lặp lại ở đây); chỉ ngưỡng được học. Đây là mô hình học máy đơn giản nhất (một
"gốc cây" cho mỗi lỗi) và tách được câu hỏi: chỉ chỉnh lại ngưỡng đã đủ tốt chưa, hay cần học
cả tập đặc trưng (random forest).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from formcoach.exercises.base import ErrorRule, Exercise
from formcoach.models.base import FormClassifier
from formcoach.models.rule_based import rule_fires
from formcoach.types import Rep, RepResult

# Ít hơn ngần này rep dương (có giá trị đặc trưng) trong tập train thì không đủ để học: lỗi đó
# không bao giờ được báo. Tránh chọn ngưỡng theo một hai rep may rủi.
MIN_POSITIVES = 3


def learn_threshold(values: Sequence[float], labels: Sequence[bool], op: str) -> float | None:
    """Ngưỡng cho luật `giá trị <op> ngưỡng` có F1 cao nhất trên (values, labels).

    - Ứng viên: trung điểm giữa hai giá trị khác nhau liền kề (mọi ngưỡng giữa hai giá trị đó
      cho cùng kết quả trên train).
    - Hoà F1 → chọn ngưỡng BÁO ÍT HƠN (nghiêm hơn): báo nhầm gây khó chịu hơn bỏ sót khi dùng thật.
      Vẫn hoà → ngưỡng đầu tiên theo thứ tự quét (xác định, không ngẫu nhiên).
    - Giá trị không hữu hạn (NaN) bị bỏ. Dưới MIN_POSITIVES rep dương hoặc mọi giá trị bằng nhau
      → None (không học được).
    """
    # Quy chiều "<" về chiều ">" bằng cách đổi dấu giá trị, học xong đổi dấu ngưỡng lại.
    sign = 1.0 if op == ">" else -1.0
    pairs = [(sign * v, y) for v, y in zip(values, labels, strict=True) if math.isfinite(v)]
    n_pos = sum(y for _, y in pairs)
    xs = sorted({x for x, _ in pairs})
    if n_pos < MIN_POSITIVES or len(xs) < 2:
        return None

    best_t, best_key = None, None
    for lo, hi in zip(xs, xs[1:], strict=False):
        t = (lo + hi) / 2
        tp = sum(1 for x, y in pairs if x > t and y)
        fp = sum(1 for x, y in pairs if x > t and not y)
        f1 = 2 * tp / (2 * tp + fp + (n_pos - tp))
        key = (f1, -(tp + fp))  # F1 cao hơn; hoà thì báo ít hơn
        if best_key is None or key > best_key:  # ">" nghiêm ngặt: hoà hoàn toàn giữ ngưỡng đầu
            best_t, best_key = t, key
    return None if best_t is None else sign * best_t


class LearnedThreshold(FormClassifier):
    """Mỗi lỗi một ngưỡng học từ train; rep thiếu số đo thì không bị báo lỗi đó (như luật tay)."""

    def __init__(self, exercise: Exercise) -> None:
        rules = exercise.error_rules()
        unknown = set(rules) - set(exercise.error_labels)
        if unknown:
            raise ValueError(f"error_rules có lỗi không thuộc error_labels: {sorted(unknown)}")
        self._base = {e: r for e, r in rules.items() if r is not None}
        # Lỗi chưa có luật (None) thì không có đặc trưng để học ngưỡng: không bao giờ báo.
        self.missing = sorted(set(exercise.error_labels) - set(self._base))
        self.thresholds_: dict[str, float | None] = {}  # lỗi → ngưỡng đã học (None: không học được)
        self._rules: dict[str, ErrorRule] = {}
        self._fitted = False

    @property
    def skipped_(self) -> list[str]:
        """Lỗi có luật nhưng không học được ngưỡng (quá ít rep dương): không bao giờ báo."""
        return sorted(e for e, t in self.thresholds_.items() if t is None)

    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None:
        self.thresholds_, self._rules = {}, {}
        for error, base in self._base.items():
            values, labels = [], []
            for rep, rep_errors in zip(reps, errors, strict=True):
                value = rep.features.get(base.feature)
                if value is not None and math.isfinite(value):
                    values.append(value)
                    labels.append(error in rep_errors)
            threshold = learn_threshold(values, labels, base.op)
            self.thresholds_[error] = threshold
            if threshold is not None:
                self._rules[error] = ErrorRule(base.feature, base.op, threshold)
        self._fitted = True

    def predict(self, reps: list[Rep]) -> list[RepResult]:
        if not self._fitted:
            raise RuntimeError("LearnedThreshold chưa fit")
        return [
            RepResult(
                rep=rep,
                errors=frozenset(e for e, r in self._rules.items() if rule_fires(r, rep.features)),
                scores=None,
            )
            for rep in reps
        ]
