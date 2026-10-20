"""Chấm baseline luật bằng kiểm định chéo bỏ ra một ngày (hoặc một buổi).

Chạy từ gốc repo:
    python -m evaluation.baseline                 # nhóm theo ngày: kết quả chính
    python -m evaluation.baseline --group block   # nhóm theo buổi: chỉ để so (rò rỉ cùng ngày?)

Báo hai cách: trung bình ± độ lệch qua các lần chia (kết quả dao động giữa các ngày bao nhiêu) và
gộp TP/FP/FN của mọi lần chia rồi mới tính (ổn định hơn khi mỗi ngày chỉ vài rep mỗi lỗi).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from evaluation.cross_validate import FoldResult, cross_validate
from evaluation.metrics import Confusion, exact_match, macro_f1, spread
from evaluation.split import evaluation_rows, group_keys
from formcoach.dataset import build_dataset
from formcoach.exercises import get_exercise
from formcoach.models import RuleBased

# Lỗi tính vào macro-F1 và exact match: có luật và không thử nghiệm (đã duyệt 2026-10-20).
# Giữ cố định để luật (tuần 2) và random forest (tuần 3) được so trên cùng một con số.
MAIN_ERRORS = {"pushup": ("shallow", "incomplete_lockout", "hip_high")}
EXPERIMENTAL = {"pushup": ("neck_drop",)}


def _f(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def pooled(results: Sequence[FoldResult], error: str) -> Confusion:
    total = Confusion()
    for r in results:
        total += r.confusion(error)
    return total


def report(results: Sequence[FoldResult], error_labels: Sequence[str], main: Sequence[str],
           notes: dict[str, str]) -> str:  # fmt: skip
    """Bảng kết quả dạng chữ. notes: lỗi báo riêng → lý do (vd "chưa có luật")."""
    lines = [
        f"  {'lỗi':<20}{'precision':>19}{'recall':>19}{'F1':>19}   "
        f"{'gộp P':>6}{'R':>6}{'F1':>6}   {'TP':>4}{'FP':>4}{'FN':>4}{'TN':>5}"
    ]

    def row(error: str) -> str:
        per_fold = [r.confusion(error) for r in results]
        total = pooled(results, error)
        cells = "".join(
            f"{spread([getattr(c, m) for c in per_fold])!s:>19}"
            for m in ("precision", "recall", "f1")
        )
        return (
            f"  {error:<20}{cells}   {_f(total.precision):>6}{_f(total.recall):>6}"
            f"{_f(total.f1):>6}   {total.tp:>4}{total.fp:>4}{total.fn:>4}{total.tn:>5}"
        )

    lines += [row(e) for e in main]
    per_fold_macro = [macro_f1({e: r.confusion(e) for e in main}, main) for r in results]
    pooled_macro = macro_f1({e: pooled(results, e) for e in main}, main)
    all_true = [t for r in results for t in r.y_true]
    all_pred = [p for r in results for p in r.y_pred]
    lines.append(
        f"\n  Macro-F1 (lỗi chính): {spread(per_fold_macro)} qua các lần chia | "
        f"gộp {_f(pooled_macro)}"
    )
    per_fold_exact = [exact_match(r.y_true, r.y_pred, main) for r in results]
    lines.append(
        f"  Exact match (lỗi chính): {spread(per_fold_exact)} | "
        f"gộp {_f(exact_match(all_true, all_pred, main))}"
    )

    others = [e for e in error_labels if e not in main]
    if others:
        lines.append("\n  Báo riêng (không tính vào macro-F1):")
        lines += [f"{row(e)}  ({notes.get(e, '')})" for e in others]

    lines.append(
        "\n  Cột trái: trung bình ± độ lệch qua các lần chia; [a/b] = chỉ a trên b lần có giá trị"
        "\n  (lần chia không có rep lỗi đó và cũng không báo → không xác định, không tính là 0)."
        "\n  Cột gộp: cộng TP/FP/FN của mọi lần chia rồi mới tính. —: không xác định."
    )
    lines.append("\n  Từng lần chia:")
    for r, m, x in zip(results, per_fold_macro, per_fold_exact, strict=True):
        positives = ", ".join(f"{e} {r.confusion(e).positives}" for e in main)
        # Lỗi có F1 không xác định ở lần này bị bỏ khỏi macro-F1 → nói rõ, vì khi đó macro-F1
        # của các lần chia được tính trên những tập lỗi khác nhau, không so trực tiếp được.
        dropped = [e for e in main if r.confusion(e).f1 is None]
        note = f" (không tính {', '.join(dropped)}: không có rep lỗi, không báo)" if dropped else ""
        lines.append(
            f"    test {r.test_group}: {len(r.rows)} rep (dương: {positives}) | "
            f"macro-F1 {_f(m)}{note} | exact {_f(x)}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.baseline")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--group", choices=["day", "block"], default="day", help="cách nhóm buổi")
    args = p.parse_args(argv)

    exercise = get_exercise(args.exercise)
    ds = build_dataset(args.data, args.exercise)
    # Hiệp bị bỏ qua (chưa gán nhãn, nhãn lệch rep...) làm một ngày bị chấm trên tập rep thiếu:
    # luôn in ra để không bỏ sót.
    for sid, reason in ds.skipped:
        print(f"bỏ qua {sid}: {reason}")
    rows = evaluation_rows(ds)  # bỏ hiệp quay thử: ngưỡng luật được chọn từ chúng
    groups = group_keys(rows, args.group)
    if len(set(groups)) < 2:
        print(f"Chưa đủ dữ liệu: {len(rows)} rep, {len(set(groups))} nhóm (cần ≥ 2 nhóm).")
        return

    missing = RuleBased(exercise).missing
    notes = {e: "chưa có luật" for e in missing}
    notes |= {e: "thử nghiệm" for e in EXPERIMENTAL.get(args.exercise, ())}
    main_errors = MAIN_ERRORS[args.exercise]

    results = cross_validate(lambda: RuleBased(exercise), rows, groups)
    print(
        f"Baseline luật — {len(rows)} rep, {len(results)} lần chia bỏ ra một nhóm "
        f"(nhóm theo {args.group}); hiệp quay thử đã loại.\n"
    )
    print(report(results, ds.error_labels, main_errors, notes))


if __name__ == "__main__":
    main()
