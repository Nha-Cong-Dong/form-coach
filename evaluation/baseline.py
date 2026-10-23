"""Chấm baseline luật bằng kiểm định chéo bỏ ra một buổi (hoặc một ngày).

Chạy từ gốc repo:
    python -m evaluation.baseline                 # nhóm theo buổi: kết quả chính (chốt 2026-10-21)
    python -m evaluation.baseline --group day     # nhóm theo ngày: cách bảo thủ hơn
Cuối báo cáo luôn có bảng so sánh hai cách nhóm: chênh nhiều → buổi cùng ngày rò rỉ sang nhau.

Báo hai cách: trung bình ± độ lệch qua các lần chia (kết quả dao động giữa các ngày bao nhiêu) và
gộp TP/FP/FN của mọi lần chia rồi mới tính (ổn định hơn khi mỗi ngày chỉ vài rep mỗi lỗi).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from evaluation.cross_validate import FoldResult, cross_validate
from evaluation.metrics import Confusion, Spread, exact_match, macro_f1, spread
from evaluation.split import GROUP_NAMES, evaluation_rows, group_keys
from formcoach.dataset import build_dataset
from formcoach.exercises import get_exercise
from formcoach.models import RuleBased

# Lỗi tính vào macro-F1 và exact match: có luật và không thử nghiệm (đã duyệt 2026-10-20).
# Giữ cố định để luật (tuần 2) và random forest (tuần 3) được so trên cùng một con số.
# 2026-10-23: thêm hip_sag (đã có hiệp quay thử võng rõ; chốt trước lần chấm đầu tiên).
MAIN_ERRORS = {"pushup": ("shallow", "incomplete_lockout", "hip_high", "hip_sag")}
EXPERIMENTAL = {"pushup": ("neck_drop",)}


def _f(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def pooled(results: Sequence[FoldResult], error: str) -> Confusion:
    total = Confusion()
    for r in results:
        total += r.confusion(error)
    return total


def summarize(
    results: Sequence[FoldResult], main: Sequence[str]
) -> tuple[Spread, float | None, float | None]:
    """(macro-F1 từng lần chia, macro-F1 gộp, exact match gộp) của các lỗi chính."""
    per_fold = [macro_f1({e: r.confusion(e) for e in main}, main) for r in results]
    pooled_macro = macro_f1({e: pooled(results, e) for e in main}, main)
    all_true = [t for r in results for t in r.y_true]
    all_pred = [p for r in results for p in r.y_pred]
    return spread(per_fold), pooled_macro, exact_match(all_true, all_pred, main)


def compare_groupings(rows, make_model, main: Sequence[str]) -> str:
    """So kết quả nhóm theo buổi và theo ngày, đặt cạnh nhau."""
    lines = ["\nSo sánh cách nhóm (lỗi chính; macro-F1 gộp | exact match gộp):"]
    for mode in ("block", "day"):
        groups = group_keys(rows, mode)
        n = len(set(groups))
        label = f"theo {GROUP_NAMES[mode]}"
        if n < 2:
            lines.append(f"  {label:<10} chỉ {n} nhóm: chưa chấm được")
            continue
        per_fold, pooled_macro, exact = summarize(cross_validate(make_model, rows, groups), main)
        lines.append(
            f"  {label:<10} {n} lần chia | macro-F1 {per_fold} | gộp {_f(pooled_macro)} "
            f"| exact {_f(exact)}"
        )
    lines.append(
        "  Theo buổi là kết quả chính (chốt trước khi có dữ liệu); theo ngày bảo thủ hơn.\n"
        "  Chênh nhiều → các buổi cùng ngày đang rò rỉ sang nhau: ghi vào phần hạn chế."
    )
    return "\n".join(lines)


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
    p.add_argument("--group", choices=["day", "block"], default="block", help="cách nhóm")
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
    # Lỗi chính mà chưa có luật thì luật không bao giờ báo nó → F1 = 0, kéo macro-F1 xuống
    # mà không phải vì luật kém: phải thấy ngay, không lặng lẽ chấm.
    for e in main_errors:
        if e in missing:
            print(f"CẢNH BÁO: {e} nằm trong lỗi chính nhưng chưa có luật → macro-F1 bị kéo xuống.")

    results = cross_validate(lambda: RuleBased(exercise), rows, groups)
    print(
        f"Baseline luật — {len(rows)} rep, {len(results)} lần chia bỏ ra một nhóm "
        f"(nhóm theo {GROUP_NAMES[args.group]}); hiệp quay thử đã loại.\n"
    )
    print(report(results, ds.error_labels, main_errors, notes))
    print(compare_groupings(rows, lambda: RuleBased(exercise), main_errors))


if __name__ == "__main__":
    main()
