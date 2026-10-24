"""Metric cho phân loại multi-label: mỗi lỗi chấm riêng như một câu hỏi có/không.

Không dùng accuracy từng lỗi: phần lớn rep KHÔNG mắc một lỗi cụ thể, nên luật "không bao giờ báo
lỗi" vẫn có accuracy cao. Precision/recall/F1 không bị đánh lừa như vậy.

Giá trị "không xác định" (chia cho 0) trả None, không đổi thành 0 hay 1: vd một buổi không có rep
dương nào của lỗi X và luật cũng không báo X → không có gì để chấm X ở buổi đó.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Confusion:
    """Ma trận 2×2 của một lỗi."""

    tp: int = 0  # có lỗi, báo đúng
    fp: int = 0  # không lỗi, báo nhầm ("la oan")
    fn: int = 0  # có lỗi, bỏ sót
    tn: int = 0  # không lỗi, không báo

    def __add__(self, other: Confusion) -> Confusion:
        return Confusion(
            self.tp + other.tp, self.fp + other.fp, self.fn + other.fn, self.tn + other.tn
        )

    @property
    def precision(self) -> float | None:
        """Trong các lần báo lỗi, bao nhiêu phần là lỗi thật. Không báo lần nào → None."""
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        """Trong các lỗi thật, bắt được bao nhiêu phần. Không có lỗi thật nào → None."""
        return _ratio(self.tp, self.tp + self.fn)

    @property
    def f1(self) -> float | None:
        """2TP / (2TP + FP + FN) = trung bình điều hoà của precision và recall.

        Viết theo TP/FP/FN để có nghĩa cả khi một trong hai không xác định: không có lỗi thật mà
        báo nhầm → 0 (phạt la oan); có lỗi mà không báo → 0. Chỉ None khi không có lỗi thật và
        cũng không báo lần nào.
        """
        return _ratio(2 * self.tp, 2 * self.tp + self.fp + self.fn)

    @property
    def positives(self) -> int:
        return self.tp + self.fn


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def confusion(
    y_true: Sequence[frozenset[str]], y_pred: Sequence[frozenset[str]], error: str
) -> Confusion:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true và y_pred phải cùng độ dài")
    tp = fp = fn = tn = 0
    for t, p in zip(y_true, y_pred, strict=True):
        actual, predicted = error in t, error in p
        if actual and predicted:
            tp += 1
        elif predicted:
            fp += 1
        elif actual:
            fn += 1
        else:
            tn += 1
    return Confusion(tp, fp, fn, tn)


def exact_match(
    y_true: Sequence[frozenset[str]], y_pred: Sequence[frozenset[str]], errors: Iterable[str]
) -> float | None:
    """Tỉ lệ rep đoán đúng TOÀN BỘ tập lỗi (chỉ xét các lỗi trong `errors`). Không có rep → None."""
    considered = frozenset(errors)
    if not y_true:
        return None
    hits = sum((t & considered) == (p & considered) for t, p in zip(y_true, y_pred, strict=True))
    return hits / len(y_true)


def macro_f1(confusions: dict[str, Confusion], errors: Iterable[str]) -> float | None:
    """Trung bình F1 của các lỗi (lỗi nào cũng nặng như nhau); bỏ lỗi có F1 không xác định."""
    values = [f for e in errors if (f := confusions[e].f1) is not None]
    return statistics.fmean(values) if values else None


@dataclass(frozen=True)
class Spread:
    """Trung bình ± độ lệch chuẩn qua các lần chia, bỏ lần không xác định (ghi lại số lần)."""

    mean: float | None
    std: float | None  # độ lệch chuẩn mẫu; None nếu < 2 giá trị
    n: int  # số lần chia có giá trị
    skipped: int  # số lần chia không xác định

    def __str__(self) -> str:
        """ "0.75 ± 0.35 [2/3]": có giá trị ở 2 trên 3 lần chia. "—": không lần nào có giá trị."""
        if self.mean is None:
            return "—"
        std = "" if self.std is None else f" ± {self.std:.2f}"
        skip = f" [{self.n}/{self.n + self.skipped}]" if self.skipped else ""
        return f"{self.mean:.2f}{std}{skip}"


@dataclass(frozen=True)
class Interval:
    low: float
    high: float
    n: int  # số lần lấy mẫu lại có giá trị (những lần không xác định bị bỏ)


def bootstrap_macro_f1(
    y_true: Sequence[frozenset[str]],
    y_preds: Mapping[str, Sequence[frozenset[str]]],
    errors: Iterable[str],
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, list[float | None]]:
    """Macro-F1 của từng mô hình trên `n_boot` tập rep lấy mẫu lại có hoàn lại.

    Mỗi lần bốc, MỘT bộ chỉ số rep được dùng chung cho mọi mô hình: đó là "ghép cặp", nhờ vậy
    hiệu giữa hai mô hình không bị nhiễu bởi việc tập giả dễ hay khó. Giá trị không xác định
    (không có rep lỗi nào trong tập giả và không báo) là None, như `macro_f1`.
    """
    errors = tuple(errors)
    n = len(y_true)
    if n == 0:
        raise ValueError("Không có rep để lấy mẫu lại")
    for name, preds in y_preds.items():
        if len(preds) != n:
            raise ValueError(f"{name}: số dự đoán ({len(preds)}) khác số nhãn ({n})")
    rng = random.Random(seed)
    samples: dict[str, list[float | None]] = {name: [] for name in y_preds}
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        truth = [y_true[i] for i in idx]
        for name, preds in y_preds.items():
            picked = [preds[i] for i in idx]
            samples[name].append(macro_f1({e: confusion(truth, picked, e) for e in errors}, errors))
    return samples


def paired_differences(a: Sequence[float | None], b: Sequence[float | None]) -> list[float]:
    """a − b theo từng lần lấy mẫu lại; bỏ lần nào một trong hai không xác định."""
    if len(a) != len(b):
        raise ValueError("a và b phải cùng số lần lấy mẫu lại")
    return [x - y for x, y in zip(a, b, strict=True) if x is not None and y is not None]


def percentile_interval(values: Sequence[float | None], level: float = 0.95) -> Interval | None:
    """Khoảng giữa (1−level)/2 và (1+level)/2 của `values` (nội suy tuyến tính); không có → None."""
    defined = sorted(v for v in values if v is not None)
    if not defined:
        return None

    def at(q: float) -> float:
        pos = q * (len(defined) - 1)
        lo = int(pos)
        hi = min(lo + 1, len(defined) - 1)
        return defined[lo] + (defined[hi] - defined[lo]) * (pos - lo)

    return Interval(at((1 - level) / 2), at((1 + level) / 2), len(defined))


def spread(values: Sequence[float | None]) -> Spread:
    defined = [v for v in values if v is not None]
    return Spread(
        mean=statistics.fmean(defined) if defined else None,
        std=statistics.stdev(defined) if len(defined) >= 2 else None,
        n=len(defined),
        skipped=len(values) - len(defined),
    )
