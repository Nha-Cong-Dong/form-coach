"""Chạy một bộ phân loại qua mọi lần chia bỏ ra một nhóm. Dùng chung cho luật (tuần 2) và
random forest (tuần 3), để hai cái được chấm y hệt nhau.

Chống rò rỉ: mỗi lần chia tạo MỘT MODEL MỚI (qua `make_model`) và chỉ `fit` trên tập train của
lần đó. Mọi thứ học từ dữ liệu (ngưỡng tự chọn, cây quyết định...) không bao giờ thấy nhóm test.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from evaluation.metrics import Confusion, confusion
from evaluation.split import leave_one_group_out
from formcoach.dataset import RepRow
from formcoach.models.base import FormClassifier
from formcoach.types import Rep


@dataclass(frozen=True)
class FoldResult:
    test_group: str
    rows: tuple[int, ...]  # chỉ số dòng của tập test
    y_true: tuple[frozenset[str], ...]
    y_pred: tuple[frozenset[str], ...]

    def confusion(self, error: str) -> Confusion:
        return confusion(self.y_true, self.y_pred, error)


def to_rep(i: int, row: RepRow) -> Rep:
    """Dòng dataset → Rep cho bộ phân loại. index = chỉ số dòng (để test kiểm tra rò rỉ);
    bộ phân loại chỉ đọc `features`."""
    return Rep(index=i, start_frame=0, end_frame=0, features=dict(row.features))


def cross_validate(
    make_model: Callable[[], FormClassifier],
    rows: Sequence[RepRow],
    groups: Sequence[str],
    on_fold: Callable[[str, FormClassifier], None] | None = None,
) -> list[FoldResult]:
    """`on_fold(nhóm_test, mô_hình_đã_fit)` (tuỳ chọn) được gọi sau mỗi lần chia: để xem thứ mô
    hình đã học (vd ngưỡng) mà không làm đổi cách chấm."""
    results = []
    for fold in leave_one_group_out(groups):
        model = make_model()  # model mới mỗi lần: không mang gì từ lần chia trước
        model.fit([to_rep(i, rows[i]) for i in fold.train], [rows[i].errors for i in fold.train])
        predicted = model.predict([to_rep(i, rows[i]) for i in fold.test])
        if on_fold is not None:
            on_fold(fold.test_group, model)
        results.append(
            FoldResult(
                test_group=fold.test_group,
                rows=fold.test,
                y_true=tuple(rows[i].errors for i in fold.test),
                y_pred=tuple(r.errors for r in predicted),
            )
        )
    return results
