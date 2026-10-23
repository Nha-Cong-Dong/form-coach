"""Phân tích lỗi của baseline luật: báo nhầm / bỏ sót nằm ở đâu. CHỈ ĐỂ HIỂU.

Chạy từ gốc repo (sau khi đã chốt nhãn và chạy `evaluation.baseline`):
    python -m evaluation.error_analysis             # tóm tắt theo lỗi
    python -m evaluation.error_analysis --list      # liệt kê từng rep báo nhầm / bỏ sót
    python -m evaluation.error_analysis --csv outputs/errors.csv   # cùng danh sách, ra bảng

Đừng dùng kết quả này để chỉnh ngưỡng rồi chấm lại trên chính các rep này: điểm mới sẽ cao
nhưng không còn trung thực (rò rỉ). Dùng nó để viết phần phân tích; còn muốn cải thiện thì học
ngưỡng / random forest trên tập train của từng lần chia (tuần 3).
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from evaluation.baseline import EXPERIMENTAL, MAIN_ERRORS
from evaluation.split import GROUP_NAMES, evaluation_rows, group_keys
from formcoach.dataset import RepRow, build_dataset
from formcoach.exercises import get_exercise
from formcoach.exercises.base import ErrorRule
from formcoach.models.rule_based import rule_fires

KINDS = ("tp", "fp", "fn", "tn")


def session_kind(row: RepRow) -> str:
    """Loại hiệp theo lỗi cố ý đã chọn lúc quay: "tập đúng" hoặc "neck_drop+shallow"."""
    return "+".join(sorted(row.set_errors)) or "tập đúng"


def outcomes(rows: Sequence[RepRow], error: str, rule: ErrorRule) -> dict[str, list[int]]:
    """Chỉ số dòng rơi vào TP / FP / FN / TN của một lỗi (luật cố định, không học gì)."""
    result: dict[str, list[int]] = {k: [] for k in KINDS}
    for i, row in enumerate(rows):
        predicted, actual = rule_fires(rule, row.features), error in row.errors
        result[("tp" if actual else "fp") if predicted else ("fn" if actual else "tn")].append(i)
    return result


def _feature_line(rows: Sequence[RepRow], idx: list[int], feature: str) -> str:
    values = [rows[i].features[feature] for i in idx if feature in rows[i].features]
    if not values:
        return "không có giá trị"
    return (
        f"trung vị {statistics.median(values):+.3f} [nhỏ nhất {min(values):+.3f}, "
        f"lớn nhất {max(values):+.3f}] (n={len(values)})"
    )


def _counts(rows: Sequence[RepRow], idx: list[int], key) -> str:
    counter = Counter(key(i) for i in idx)
    return ", ".join(f"{k} {n}" for k, n in sorted(counter.items(), key=lambda kv: -kv[1]))


def analyze_error(
    rows: Sequence[RepRow], groups: Sequence[str], error: str, rule: ErrorRule
) -> str:
    out = outcomes(rows, error, rule)
    n = {k: len(v) for k, v in out.items()}
    lines = [
        f"{error}  ({rule.feature} {rule.op} {rule.threshold:g}): "
        f"TP {n['tp']}  FP {n['fp']}  FN {n['fn']}  TN {n['tn']}"
    ]
    for kind, label in (("fp", "Báo nhầm"), ("fn", "Bỏ sót")):
        if not out[kind]:
            continue
        lines.append(f"  {label} ({n[kind]}) theo loại hiệp: " + _counts(
            rows, out[kind], lambda i: session_kind(rows[i])))  # fmt: skip
        lines.append(f"  {label} ({n[kind]}) theo {'nhóm'}: " + _counts(
            rows, out[kind], lambda i: groups[i]))  # fmt: skip
    lines.append(f"  Giá trị {rule.feature} (ngưỡng {rule.threshold:+g}, lỗi khi {rule.op}):")
    for kind, label in (
        ("tp", "báo đúng"),
        ("fp", "báo nhầm"),
        ("fn", "bỏ sót"),
        ("tn", "đúng, không báo"),
    ):
        lines.append(f"    {label:<16}{_feature_line(rows, out[kind], rule.feature)}")  # noqa: E501
    return "\n".join(lines)


WRONG = (("fp", "báo nhầm"), ("fn", "bỏ sót"))


def _label_text(row: RepRow) -> str:
    return ", ".join(sorted(row.errors)) or "không lỗi"


def list_cases(rows: Sequence[RepRow], error: str, rule: ErrorRule) -> str:
    """Từng rep luật báo sai, kèm thời điểm trong hiệp để tìm lại ở màn gán nhãn."""
    out = outcomes(rows, error, rule)
    lines = []
    for kind, label in WRONG:
        for i in out[kind]:
            r = rows[i]
            value = r.features.get(rule.feature)
            shown = "thiếu" if value is None else f"{value:+.3f}"
            lines.append(
                f"    {label:<9}{r.session_id} rep {r.rep_index + 1} "
                f"[{r.start_s:.1f}–{r.end_s:.1f} s] (hiệp: {session_kind(r)}; "
                f"nhãn: {_label_text(r)}): {rule.feature} = {shown}"
            )
    return "\n".join(lines)


CASE_COLUMNS = [
    "lỗi", "loại", "session_id", "recorded_at", "nhóm", "rep", "start_s", "end_s",
    "hiệp quay cho", "nhãn rep", "đặc trưng của luật", "giá trị", "ngưỡng", "cách ngưỡng",
]  # fmt: skip


def write_cases_csv(
    path: Path,
    rows: Sequence[RepRow],
    groups: Sequence[str],
    rules: dict[str, ErrorRule | None],
    errors: Sequence[str],
) -> int:
    """Ghi MỌI rep luật báo nhầm / bỏ sót (mọi lỗi) ra bảng, kèm toàn bộ số đo của rep.

    Để kiểm tra từng hàm đo: lọc theo lỗi, mở rep ở màn gán nhãn (session_id + start_s), so hình
    với số đo. Cột "cách ngưỡng" = giá trị trừ ngưỡng (nhỏ → sát ngưỡng, lớn → xa ngưỡng).
    Trả về số dòng ghi ra.
    """
    feature_names = sorted({k for r in rows for k in r.features})
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:  # utf-8-sig: Excel đọc đúng tiếng Việt
        w = csv.writer(f)
        w.writerow([*CASE_COLUMNS, *feature_names])
        for error in errors:
            rule = rules.get(error)
            if rule is None:
                continue
            out = outcomes(rows, error, rule)
            for kind, label in WRONG:
                for i in out[kind]:
                    r = rows[i]
                    v = r.features.get(rule.feature)
                    w.writerow(
                        [
                            error, label, r.session_id, r.recorded_at.isoformat(), groups[i],
                            r.rep_index + 1, f"{r.start_s:.2f}", f"{r.end_s:.2f}",
                            session_kind(r), _label_text(r), rule.feature,
                            "" if v is None else f"{v:.4f}", f"{rule.op} {rule.threshold:g}",
                            "" if v is None else f"{v - rule.threshold:+.4f}",
                            *("" if r.features.get(n) is None else f"{r.features[n]:.4f}"
                              for n in feature_names),
                        ]
                    )  # fmt: skip
                    count += 1
    return count


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.error_analysis")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--group", choices=["day", "block"], default="block", help="cách nhóm")
    p.add_argument("--list", action="store_true", help="liệt kê từng rep báo nhầm / bỏ sót")
    p.add_argument("--csv", type=Path, help="ghi mọi rep báo sai, kèm số đo, ra file CSV này")
    args = p.parse_args(argv)

    exercise = get_exercise(args.exercise)
    rows = evaluation_rows(build_dataset(args.data, args.exercise))  # bỏ hiệp quay thử
    groups = group_keys(rows, args.group)
    rules = exercise.error_rules()
    errors = (*MAIN_ERRORS[args.exercise], *EXPERIMENTAL.get(args.exercise, ()))
    print(
        f"Phân tích lỗi của luật: {len(rows)} rep, nhóm theo {GROUP_NAMES[args.group]}. "
        "Chỉ để hiểu, không chỉnh ngưỡng trên dữ liệu này.\n"
    )
    for error in errors:
        rule = rules.get(error)
        if rule is None:
            print(f"{error}: chưa có luật\n")
            continue
        print(analyze_error(rows, groups, error, rule))
        if args.list:
            print(list_cases(rows, error, rule))
        print()
    if args.csv:
        n = write_cases_csv(args.csv, rows, groups, rules, errors)
        print(f"Đã ghi {n} rep báo sai (báo nhầm + bỏ sót, mọi lỗi) → {args.csv}")


if __name__ == "__main__":
    main()
