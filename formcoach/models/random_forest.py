"""Random forest: mỗi lỗi một "rừng" nhị phân học từ NHIỀU đặc trưng của rep cùng lúc.

Khác luật và ngưỡng học (chỉ nhìn MỘT số đo cho mỗi lỗi): rừng kết hợp mọi đặc trưng (khuỷu, hông,
cổ, thời lượng...) nên có thể bắt thứ một số đo bỏ sót, ví dụ lỗi hay đi cùng nhau.

Đa nhãn bằng MỘT RỪNG NHỊ PHÂN CHO MỖI LỖI (không dùng MultiOutput): các lỗi có nguyên nhân độc
lập, mỗi lỗi có mất cân bằng lớp riêng (`class_weight` theo từng lỗi), và cách này khớp cách luật
và `exact_match` đã xử lý từng lỗi.

Siêu tham số CỐ ĐỊNH TRƯỚC khi chạy lần đầu (đăng ký trước, README §8): không chỉnh theo điểm.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from formcoach.exercises.base import Exercise
from formcoach.models.base import FormClassifier
from formcoach.types import Rep, RepResult

log = logging.getLogger(__name__)

# --- Đăng ký trước (README §8). Đổi những số này = đổi giả thuyết đã đăng ký: phải ghi lý do. ---
N_ESTIMATORS = 300
MAX_DEPTH = 4  # cây nông: ~24–50 rep dương mỗi lỗi, cây sâu sẽ học thuộc lòng
MIN_SAMPLES_LEAF = 5
CLASS_WEIGHT = "balanced_subsample"  # lỗi chiếm ~15–30% số rep
THRESHOLD = 0.5  # báo lỗi khi xác suất ≥ 0,5; không chỉnh ngưỡng xác suất theo điểm
# Dưới ngần này rep dương trong train thì không fit: không học được gì ngoài may rủi.
MIN_POSITIVES = 2


def _matrix(reps: Sequence[Rep], columns: Sequence[str]) -> np.ndarray:
    """(số rep, số cột); thiếu khoá hoặc giá trị không hữu hạn → NaN (rừng nhận NaN trực tiếp)."""
    x = np.full((len(reps), len(columns)), np.nan)
    for i, rep in enumerate(reps):
        for j, name in enumerate(columns):
            value = rep.features.get(name)
            if value is not None and math.isfinite(value):
                x[i, j] = value
    return x


class RandomForest(FormClassifier):
    def __init__(self, exercise: Exercise, seed: int = 0) -> None:
        self._errors = list(exercise.error_labels)
        self._seed = seed
        self.columns_: list[str] = []  # cột đặc trưng, lấy theo TẬP TRAIN
        self.importances_: dict[str, dict[str, float]] = {}  # lỗi → đặc trưng → độ quan trọng
        self.skipped_: list[str] = []  # lỗi không fit được (quá ít rep dương): không bao giờ báo
        self._models: dict[str, RandomForestClassifier] = {}
        self._fitted = False

    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None:
        # Cột = hợp các khoá của rep train, bỏ cột không có giá trị hữu hạn nào. Khoá chỉ có ở rep
        # test (hoặc khoá như bottom_frame mà bảng train không có) không bao giờ vào mô hình.
        names = sorted({k for rep in reps for k in rep.features})
        x_all = _matrix(reps, names)
        keep = [j for j in range(len(names)) if np.isfinite(x_all[:, j]).any()]
        self.columns_ = [names[j] for j in keep]
        x = x_all[:, keep]

        self._models, self.importances_, self.skipped_ = {}, {}, []
        for error in self._errors:
            y = np.array([error in rep_errors for rep_errors in errors], dtype=int)
            n_pos = int(y.sum())
            if n_pos < MIN_POSITIVES or n_pos == len(y) or x.shape[1] == 0:
                log.info("RandomForest: bỏ qua %s (%d rep dương / %d rep)", error, n_pos, len(y))
                self.skipped_.append(error)
                continue
            forest = RandomForestClassifier(
                n_estimators=N_ESTIMATORS,
                max_depth=MAX_DEPTH,
                min_samples_leaf=MIN_SAMPLES_LEAF,
                class_weight=CLASS_WEIGHT,
                random_state=self._seed,
                n_jobs=1,  # cố định cách tính để cùng seed cho cùng kết quả
            )
            forest.fit(x, y)
            self._models[error] = forest
            self.importances_[error] = dict(
                zip(self.columns_, map(float, forest.feature_importances_), strict=True)
            )
        self._fitted = True

    def predict(self, reps: list[Rep]) -> list[RepResult]:
        if not self._fitted:
            raise RuntimeError("RandomForest chưa fit")
        if not reps:
            return []
        x = _matrix(reps, self.columns_)
        # Lỗi không có rừng (quá ít rep dương trong train): không bao giờ báo, điểm 0.
        proba = {e: np.zeros(len(reps)) for e in self._errors}
        for error, forest in self._models.items():
            proba[error] = forest.predict_proba(x)[:, list(forest.classes_).index(1)]
        return [
            RepResult(
                rep=rep,
                errors=frozenset(e for e in self._errors if proba[e][i] >= THRESHOLD),
                scores={e: float(proba[e][i]) for e in self._errors},
            )
            for i, rep in enumerate(reps)
        ]
