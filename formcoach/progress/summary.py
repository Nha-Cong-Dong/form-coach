"""Tóm tắt một hiệp đã phân loại: số rep, số rep đúng kỹ thuật, số rep mỗi lỗi."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from formcoach.types import Session


def summarize(session: Session, error_labels: Sequence[str]) -> dict[str, Any]:
    """`error_counts` có đủ mọi lỗi của bài (kể cả 0), theo thứ tự `error_labels`.

    Rep đúng = tập lỗi rỗng. Một rep nhiều lỗi được đếm ở mỗi lỗi đó, nên tổng `error_counts`
    có thể lớn hơn số rep sai. Hiệp 0 rep: `good_ratio` là None (không chia cho 0).
    """
    n_reps = len(session.results)
    n_good = sum(1 for r in session.results if not r.errors)
    return {
        "n_reps": n_reps,
        "n_good": n_good,
        "good_ratio": n_good / n_reps if n_reps else None,
        "error_counts": {e: sum(e in r.errors for r in session.results) for e in error_labels},
    }
