"""Phép thử "lỗi cố ý": mô hình đọc SỐ ĐO của rep hay chỉ theo KỊCH BẢN quay của hiệp?

Chạy từ gốc repo:
    python -m evaluation.protocol_check                       # rules, stump, rf
    python -m evaluation.protocol_check --models rules,rf

Mỗi hiệp được quay với một lỗi cố ý (`set_errors`), nên nhãn rep gần như trùng lỗi cố ý của hiệp.
Mô hình chỉ nhận ra "kiểu hiệp" vẫn được điểm cao nhưng sẽ hỏng khi người dùng tập thật. Cách thử:
- Nhóm A: nhãn thật = lỗi cố ý. Hai cách đọc cho cùng đáp án, chỉ báo exact match.
- Nhóm B: nhãn thật KHÁC lỗi cố ý. Đếm mỗi mô hình đoán theo nhãn thật hay theo lỗi cố ý.
Dùng đúng các lần chia và dự đoán của `compare`; không huấn luyện gì thêm. `set_errors` chỉ dùng ở
đây để chấm, không bao giờ vào đặc trưng của mô hình.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from evaluation.baseline import MAIN_ERRORS, _f
from evaluation.compare import parse_models
from evaluation.cross_validate import FoldResult, cross_validate
from evaluation.metrics import exact_match
from evaluation.split import GROUP_NAMES, evaluation_rows, group_keys
from formcoach.dataset import RepRow, build_dataset
from formcoach.exercises import get_exercise
from formcoach.models import make_classifier


def split_by_protocol(rows: Sequence[RepRow], main: Sequence[str]) -> tuple[list[int], list[int]]:
    """Chỉ số rep có nhãn trùng lỗi cố ý (A) và khác (B), chỉ xét các lỗi trong `main`."""
    considered = frozenset(main)
    same: list[int] = []
    differ: list[int] = []
    for i, row in enumerate(rows):
        (same if row.errors & considered == row.set_errors & considered else differ).append(i)
    return same, differ


def predictions_by_row(results: Sequence[FoldResult], n_rows: int) -> list[frozenset[str]]:
    """Dự đoán ngoài-fold đặt lại đúng chỉ số dòng; mỗi dòng phải được dự đoán đúng một lần."""
    preds: list[frozenset[str] | None] = [None] * n_rows
    for r in results:
        for i, p in zip(r.rows, r.y_pred, strict=True):
            preds[i] = p
    if any(p is None for p in preds):
        raise ValueError("Có rep chưa được dự đoán ở lần chia nào")
    return preds  # type: ignore[return-value]


def follow_counts(
    preds: Sequence[frozenset[str]],
    rows: Sequence[RepRow],
    idxs: Sequence[int],
    main: Sequence[str],
) -> tuple[int, int, int]:
    """(đoán = nhãn thật, đoán = lỗi cố ý, khác cả hai) trên các rep `idxs`.

    Chỉ có nghĩa trên nhóm B: ở đó nhãn thật khác lỗi cố ý nên hai đáp án loại trừ nhau."""
    considered = frozenset(main)
    n_true = n_script = 0
    for i in idxs:
        p = preds[i] & considered
        n_true += p == rows[i].errors & considered
        n_script += p == rows[i].set_errors & considered
    return n_true, n_script, len(idxs) - n_true - n_script


def protocol_report(
    preds_by_model: dict[str, Sequence[frozenset[str]]],
    rows: Sequence[RepRow],
    main: Sequence[str],
) -> str:
    same, differ = split_by_protocol(rows, main)
    considered = frozenset(main)
    script = [r.set_errors & considered for r in rows]  # mô hình mốc: luôn theo kịch bản
    models = {"set-only": script, **preds_by_model}

    def exact(name: str) -> float | None:
        idx = same
        return exact_match([rows[i].errors for i in idx], [models[name][i] for i in idx], main)

    lines = [
        f"Phép thử lỗi cố ý — {len(rows)} rep: nhóm A (nhãn thật = lỗi cố ý) {len(same)} rep, "
        f"nhóm B (nhãn thật khác lỗi cố ý) {len(differ)} rep.",
        "",
        f"Nhóm A ({len(same)} rep): exact match. Hai cách đọc cho cùng đáp án nên không phân biệt.",
    ]
    lines += [f"  {name:<10}{_f(exact(name)):>6}" for name in models]
    lines += [
        "",
        f"Nhóm B ({len(differ)} rep): đoán theo nhãn thật hay theo lỗi cố ý của hiệp?",
        f"  {'':<10}{'= nhãn thật':>13}{'= lỗi cố ý':>13}{'khác cả hai':>13}",
    ]
    for name in models:
        t, s, o = follow_counts(models[name], rows, differ, main)
        lines.append(f"  {name:<10}{t:>13}{s:>13}{o:>13}")
    lines += [
        "",
        "  Cách đọc: mô hình đọc số đo nghiêng về '= nhãn thật'; mô hình theo kịch bản nghiêng về",
        "  '= lỗi cố ý' (set-only là mốc: luôn theo kịch bản). Nhóm B ít rep: đọc bằng số đếm,",
        "  không bằng phần trăm; một hiệp lệch ý định kéo cả nhóm.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.protocol_check")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--group", choices=["day", "block"], default="block", help="cách nhóm")
    p.add_argument("--models", default="rules,stump,rf", help="danh sách tên, cách nhau bằng phẩy")
    p.add_argument("--seed", type=int, default=0, help="seed cho mô hình có ngẫu nhiên")
    args = p.parse_args(argv)

    names = parse_models(args.models)
    exercise = get_exercise(args.exercise)
    ds = build_dataset(args.data, args.exercise)
    for sid, reason in ds.skipped:
        print(f"bỏ qua {sid}: {reason}")
    rows = evaluation_rows(ds)  # bỏ hiệp quay thử, như compare
    groups = group_keys(rows, args.group)
    if len(set(groups)) < 2:
        print(f"Chưa đủ dữ liệu: {len(rows)} rep, {len(set(groups))} nhóm (cần ≥ 2 nhóm).")
        return

    print(
        f"{len(rows)} rep, {len(set(groups))} lần chia bỏ ra một nhóm "
        f"(nhóm theo {GROUP_NAMES[args.group]}); hiệp quay thử đã loại.\n"
    )
    preds = {}
    for name in names:
        results = cross_validate(
            lambda name=name: make_classifier(name, exercise, args.seed), rows, groups
        )
        preds[name] = predictions_by_row(results, len(rows))
    print(protocol_report(preds, rows, MAIN_ERRORS[args.exercise]))


if __name__ == "__main__":
    main()
