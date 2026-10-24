"""Huấn luyện bộ phân loại dùng trong app từ dataset đã gán nhãn.

Dùng cùng registry với `evaluation/` (cùng siêu tham số: mô hình được chấm chính là mô hình được
dùng). Khác đánh giá ở một điểm: app học trên MỌI rep hợp lệ đã gán nhãn, kể cả hiệp quay thử.
Loại hiệp quay thử là để chấm điểm không rò rỉ; mô hình dùng thật thì nên học từ toàn bộ dữ liệu.
"""

from __future__ import annotations

import logging

from formcoach.dataset import Dataset
from formcoach.exercises.base import Exercise
from formcoach.models.base import FormClassifier
from formcoach.models.registry import make_classifier
from formcoach.types import Rep

log = logging.getLogger(__name__)

FALLBACK = "rules"  # luật không cần dữ liệu


def train_classifier(
    name: str, exercise: Exercise, dataset: Dataset | None, seed: int = 0
) -> tuple[FormClassifier, str]:
    """(bộ phân loại đã fit, tên mô hình thật sự dùng).

    `rules` không cần dữ liệu. Mô hình học mà không có rep nào (server không có `data/`) hoặc fit
    lỗi → lùi về luật và trả tên `rules`, để kết quả lưu đúng mô hình đã chấm. Tên lạ → ValueError.
    """
    classifier = make_classifier(name, exercise, seed)  # tên lạ ném ngay, không lùi
    if name == FALLBACK:
        return classifier, name
    rows = dataset.rows if dataset is not None else ()
    if not rows:
        log.warning("Không có rep đã gán nhãn để huấn luyện %r: dùng %r.", name, FALLBACK)
        return make_classifier(FALLBACK, exercise), FALLBACK
    # Bộ phân loại chỉ đọc `features`; vị trí khung không cần.
    reps = [
        Rep(index=i, start_frame=0, end_frame=0, features=dict(r.features))
        for i, r in enumerate(rows)
    ]
    try:
        classifier.fit(reps, [r.errors for r in rows])
    except Exception:  # noqa: BLE001 - mọi lỗi huấn luyện đều lùi về luật, có ghi log
        log.exception("Huấn luyện %r lỗi: dùng %r.", name, FALLBACK)
        return make_classifier(FALLBACK, exercise), FALLBACK
    log.info("Đã huấn luyện %r trên %d rep.", name, len(rows))
    return classifier, name
