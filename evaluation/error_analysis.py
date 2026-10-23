"""Phân tích lỗi của baseline luật: báo nhầm / bỏ sót nằm ở đâu. CHỈ ĐỂ HIỂU.

Chạy từ gốc repo (sau khi đã chốt nhãn và chạy `evaluation.baseline`):
    python -m evaluation.error_analysis             # tóm tắt theo lỗi
    python -m evaluation.error_analysis --list      # liệt kê từng rep báo nhầm / bỏ sót

Đừng dùng kết quả này để chỉnh ngưỡng rồi chấm lại trên chính các rep này: điểm mới sẽ cao
nhưng không còn trung thực (rò rỉ). Dùng nó để viết phần phân tích; còn muốn cải thiện thì học
ngưỡng / random forest trên tập train của từng lần chia (tuần 3).
"""

from __future__ import annotations

import argparse
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


def list_cases(rows: Sequence[RepRow], error: str, rule: ErrorRule) -> str:
    out = outcomes(rows, error, rule)
    lines = []
    for kind, label in (("fp", "báo nhầm"), ("fn", "bỏ sót")):
        for i in out[kind]:
            r = rows[i]
            value = r.features.get(rule.feature)
            shown = "thiếu" if value is None else f"{value:+.3f}"
            lines.append(
                f"    {label:<9}{r.session_id} rep {r.rep_index + 1} "
                f"({session_kind(r)}): {rule.feature} = {shown}"
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.error_analysis")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--group", choices=["day", "block"], default="block", help="cách nhóm")
    p.add_argument("--list", action="store_true", help="liệt kê từng rep báo nhầm / bỏ sót")
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


if __name__ == "__main__":
    main()
