"""Chạy nhiều mô hình qua CÙNG một lần chấm (cùng dữ liệu, cùng các lần chia) và so sánh.

Chạy từ gốc repo:
    python -m evaluation.compare                          # mặc định: chỉ luật (kiểm tra tái hiện)
    python -m evaluation.compare --models rules,stump,rf  # nhiều mô hình một bảng

Mỗi mô hình in báo cáo y như `evaluation.baseline` (dùng chung `report`), rồi một bảng cuối: hàng =
mô hình, cột = F1 gộp từng lỗi, macro-F1 và exact match. `MAIN_ERRORS` giữ cố định để mọi mô hình
được so trên cùng một con số; `neck_drop` (thử nghiệm) báo riêng, không tính vào macro-F1.
Mô hình được tạo mới ở mỗi lần chia (qua registry) và chỉ fit trên tập train của lần đó.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from evaluation.baseline import EXPERIMENTAL, MAIN_ERRORS, _f, pooled, report, summarize
from evaluation.cross_validate import FoldResult, cross_validate
from evaluation.metrics import (
    Interval,
    bootstrap_macro_f1,
    macro_f1,
    paired_differences,
    percentile_interval,
    spread,
)
from evaluation.split import GROUP_NAMES, evaluation_rows, group_keys
from formcoach.dataset import build_dataset
from formcoach.exercises import get_exercise
from formcoach.exercises.base import Exercise
from formcoach.models import RuleBased, classifier_names, make_classifier

# Mô hình có thành phần ngẫu nhiên: chỉ những mô hình này cần chạy nhiều seed.
RANDOM_MODELS = ("rf",)


def parse_models(text: str) -> list[str]:
    """ "rules, rf" → ["rules", "rf"]: bỏ khoảng trắng và tên trùng, kiểm tra tên hợp lệ."""
    names: list[str] = []
    for part in text.split(","):
        name = part.strip()
        if name and name not in names:
            names.append(name)
    unknown = [n for n in names if n not in classifier_names()]
    if unknown or not names:
        raise ValueError(f"Mô hình không hỗ trợ: {unknown or text!r}. Hợp lệ: {classifier_names()}")
    return names


def notes_for(name: str, exercise_name: str, exercise: Exercise) -> dict[str, str]:
    """Lý do báo riêng một lỗi: thử nghiệm, hoặc (chỉ với luật) chưa có luật."""
    notes = {e: "chưa có luật" for e in RuleBased(exercise).missing} if name == "rules" else {}
    return notes | {e: "thử nghiệm" for e in EXPERIMENTAL.get(exercise_name, ())}


def threshold_table(exercise: Exercise, learned: dict[str, dict[str, float | None]]) -> str:
    """Ngưỡng học theo từng lần chia, cạnh ngưỡng chọn tay: nhìn độ ổn định và độ lệch."""
    errors = list(exercise.error_labels)
    hand = exercise.error_rules()

    def cell(error: str, value: float | None) -> str:
        rule = hand.get(error)
        return "—" if value is None or rule is None else f"{rule.op} {value:.3g}"

    width = {e: max(len(e), 9) + 2 for e in errors}
    lines = [
        "Ngưỡng học theo từng lần chia (so với ngưỡng chọn tay):",
        f"  {'lần chia':<24}" + "".join(f"{e:>{width[e]}}" for e in errors),
        f"  {'ngưỡng chọn tay':<24}"
        + "".join(
            f"{cell(e, hand[e].threshold if hand.get(e) else None):>{width[e]}}" for e in errors
        ),
    ]
    for group, thresholds in learned.items():
        cells = "".join(f"{cell(e, thresholds.get(e)):>{width[e]}}" for e in errors)
        lines.append(f"  {'test ' + group:<24}{cells}")
    return "\n".join(lines)


def summary_table(
    results_by_model: dict[str, Sequence[FoldResult]],
    main: Sequence[str],
    experimental: Sequence[str],
) -> str:
    """Hàng = mô hình; cột = F1 gộp từng lỗi chính, macro-F1 (gộp và theo lần chia), exact match."""
    cols = [*main, *(f"{e}*" for e in experimental)]
    width = {c: max(len(c), 6) + 2 for c in cols}
    header = f"  {'mô hình':<12}" + "".join(f"{c:>{width[c]}}" for c in cols)
    header += f"{'macro-F1 gộp':>14}{'theo lần chia':>17}{'exact':>8}"
    lines = [
        "So sánh mô hình (F1 gộp từng lỗi; macro-F1 và exact match tính trên lỗi chính;"
        " * = thử nghiệm, không tính vào macro-F1):",
        header,
    ]
    for name, results in results_by_model.items():
        spread_text, macro, exact = summarize(results, main)
        f1s = [_f(pooled(results, e).f1) for e in (*main, *experimental)]
        row = f"  {name:<12}" + "".join(f"{v:>{width[c]}}" for v, c in zip(f1s, cols, strict=True))
        lines.append(row + f"{_f(macro):>14}{spread_text!s:>17}{_f(exact):>8}")
    return "\n".join(lines)


def pooled_predictions(
    results: Sequence[FoldResult],
) -> tuple[list[frozenset[str]], list[frozenset[str]]]:
    """Nhãn thật và dự đoán của mọi lần chia, nối theo thứ tự lần chia."""
    return (
        [t for r in results for t in r.y_true],
        [p for r in results for p in r.y_pred],
    )


def _interval(iv: Interval | None) -> str:
    return "—" if iv is None else f"[{iv.low:+.2f}, {iv.high:+.2f}]"


def _per_fold_macro(results: Sequence[FoldResult], main: Sequence[str]) -> list[float | None]:
    return [macro_f1({e: r.confusion(e) for e in main}, main) for r in results]


def ci_table(
    results_by_model: dict[str, Sequence[FoldResult]],
    main: Sequence[str],
    n_boot: int,
    seed: int,
    reference: str,
) -> str:
    """Khoảng tin cậy 95% của macro-F1 từng mô hình và của HIỆU so với `reference` (ghép cặp).

    Kết luận theo quy tắc đăng ký trước: khác nhau khi khoảng của hiệu không chứa 0."""
    truth: list[frozenset[str]] | None = None
    preds: dict[str, list[frozenset[str]]] = {}
    for name, results in results_by_model.items():
        t, p = pooled_predictions(results)
        if truth is not None and t != truth:
            raise ValueError(f"{name}: nhãn thật khác mô hình trước: các lần chia không khớp nhau")
        truth, preds[name] = t, p
    assert truth is not None
    samples = bootstrap_macro_f1(truth, preds, main, n_boot=n_boot, seed=seed)

    lines = [
        f"Khoảng tin cậy 95% của macro-F1 gộp (bootstrap {n_boot} lần: lấy mẫu lại {len(truth)} "
        f"rep có hoàn lại, cùng một mẫu cho mọi mô hình; hiệu = mô hình − {reference}):",
        f"  {'mô hình':<12}{'macro-F1 gộp':>14}{'khoảng tin cậy':>20}"
        f"{'hiệu':>9}{'khoảng tin cậy của hiệu':>26}",
    ]
    verdicts = []
    for name, results in results_by_model.items():
        _, macro, _ = summarize(results, main)
        own = _interval(percentile_interval(samples[name]))
        if name == reference:
            lines.append(f"  {name:<12}{_f(macro):>14}{own:>20}{'':>9}{'(mốc so sánh)':>26}")
            continue
        _, ref_macro, _ = summarize(results_by_model[reference], main)
        diff = None if macro is None or ref_macro is None else macro - ref_macro
        iv = percentile_interval(paired_differences(samples[name], samples[reference]))
        shown = "—" if diff is None else f"{diff:+.2f}"
        lines.append(f"  {name:<12}{_f(macro):>14}{own:>20}{shown:>9}{_interval(iv):>26}")
        if iv is None:
            verdicts.append(f"  {name}: không đủ dữ liệu để kết luận.")
        elif iv.low > 0:
            verdicts.append(f"  {name}: cao hơn {reference} (khoảng của hiệu không chứa 0).")
        elif iv.high < 0:
            verdicts.append(f"  {name}: thấp hơn {reference} (khoảng của hiệu không chứa 0).")
        else:
            verdicts.append(
                f"  {name}: chưa có bằng chứng khác {reference} (khoảng của hiệu chứa 0)."
            )
    lines += ["", "Theo quy tắc đã đăng ký:", *verdicts]
    per_fold = _per_fold_macro(results_by_model[reference], main)
    lines += ["", f"Hiệu macro-F1 theo từng lần chia (mô hình − {reference}):"]
    for name, results in results_by_model.items():
        if name == reference:
            continue
        mine = _per_fold_macro(results, main)
        diffs = [
            None if a is None or b is None else a - b for a, b in zip(mine, per_fold, strict=True)
        ]
        shown = "  ".join(
            f"{r.test_group}: {'—' if d is None else f'{d:+.2f}'}"
            for r, d in zip(results, diffs, strict=True)
        )
        higher = sum(d is not None and d > 0 for d in diffs)
        lines.append(f"  {name}: {shown}  ({higher}/{len(diffs)} lần chia cao hơn)")
    lines.append(
        "\n  Cảnh báo: khoảng này LẠC QUAN. Các rep trong một buổi giống nhau hơn rep khác buổi, và"
        "\n  chỉ có một người quay, một người gán nhãn; lấy mẫu lại rep coi chúng độc lập. Cột"
        "\n  'theo lần chia' ở bảng trên (dao động giữa các buổi) là phép đo trung thực hơn."
    )
    return "\n".join(lines)


def seed_table(name: str, runs: Sequence[tuple[int, float | None, float | None]]) -> str:
    """Điểm của một mô hình có ngẫu nhiên khi đổi seed (dữ liệu và các lần chia giữ nguyên)."""
    macros = [m for _, m, _ in runs]
    exacts = [x for _, _, x in runs]
    lines = [f"Độ lệch do seed — {name} chạy seed {runs[0][0]}..{runs[-1][0]}:"]
    lines.append(f"  {'seed':<8}" + "".join(f"{s:>7}" for s, _, _ in runs))
    lines.append(f"  {'macro-F1':<8}" + "".join(f"{_f(m):>7}" for m in macros))
    lines.append(f"  {'exact':<8}" + "".join(f"{_f(x):>7}" for x in exacts))
    lines.append(f"  macro-F1 gộp: {spread(macros)} | exact gộp: {spread(exacts)}")
    lines.append("  (chỉ do rừng ngẫu nhiên, không do dữ liệu: dao động nhỏ = kết quả không phụ")
    lines.append("   thuộc may rủi của seed)")
    return "\n".join(lines)


def importance_table(
    per_fold: Sequence[dict[str, dict[str, float]]],
    errors: Sequence[str],
    top: int = 5,
    experimental: Sequence[str] = (),
) -> str:
    """Top `top` đặc trưng của mỗi lỗi, trung bình độ quan trọng (impurity) qua các lần chia."""
    lines = [f"Độ quan trọng đặc trưng (top {top}, trung bình qua {len(per_fold)} lần chia):"]
    for error in errors:
        label = f"{error}*" if error in experimental else error
        total: dict[str, float] = {}
        for imp in per_fold:
            for feature, value in imp.get(error, {}).items():
                total[feature] = total.get(feature, 0.0) + value / len(per_fold)
        if not total:
            lines.append(f"  {label:<20}(không có rừng nào được fit)")
            continue
        best = sorted(total.items(), key=lambda kv: kv[1], reverse=True)[:top]
        lines.append(f"  {label:<20}" + ", ".join(f"{f} {v:.2f}" for f, v in best))
    if experimental:
        lines.append("  * = thử nghiệm, không tính vào macro-F1.")
    lines.append("  Chỉ để MÔ TẢ rừng dùng gì; không phải bằng chứng đặc trưng đó gây ra lỗi.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.compare")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--group", choices=["day", "block"], default="block", help="cách nhóm")
    p.add_argument("--models", default="rules", help="danh sách tên, cách nhau bằng dấu phẩy")
    p.add_argument("--seed", type=int, default=0, help="seed cho mô hình có ngẫu nhiên")
    p.add_argument("--boot", type=int, default=1000, help="số lần lấy mẫu lại; 0 = bỏ khoảng")
    p.add_argument(
        "--seed-runs", type=int, default=5, help="số seed cho mô hình có ngẫu nhiên; 0 = bỏ qua"
    )
    args = p.parse_args(argv)

    names = parse_models(args.models)
    exercise = get_exercise(args.exercise)
    ds = build_dataset(args.data, args.exercise)
    for sid, reason in ds.skipped:
        print(f"bỏ qua {sid}: {reason}")
    rows = evaluation_rows(ds)  # bỏ hiệp quay thử
    groups = group_keys(rows, args.group)
    if len(set(groups)) < 2:
        print(f"Chưa đủ dữ liệu: {len(rows)} rep, {len(set(groups))} nhóm (cần ≥ 2 nhóm).")
        return

    main_errors = MAIN_ERRORS[args.exercise]
    experimental = EXPERIMENTAL.get(args.exercise, ())
    print(
        f"So sánh {', '.join(names)} — {len(rows)} rep, {len(set(groups))} lần chia bỏ ra một "
        f"nhóm (nhóm theo {GROUP_NAMES[args.group]}); hiệp quay thử đã loại.\n"
    )
    results_by_model: dict[str, list[FoldResult]] = {}
    for name in names:
        learned: dict[str, dict[str, float | None]] = {}
        importances: list[dict[str, dict[str, float]]] = []
        unfit: dict[str, list[str]] = {}

        def keep(
            group: str,
            model: object,
            learned: dict = learned,
            importances: list = importances,
            unfit: dict = unfit,
        ) -> None:
            skipped = list(getattr(model, "skipped_", ()))  # lỗi không đủ rep dương để fit
            if skipped:
                unfit[group] = skipped
            thresholds = getattr(model, "thresholds_", None)  # chỉ mô hình có ngưỡng học
            if thresholds is not None:
                learned[group] = dict(thresholds)
            fold_importances = getattr(model, "importances_", None)  # chỉ mô hình dạng rừng
            if fold_importances:
                importances.append(fold_importances)

        results = cross_validate(
            lambda name=name: make_classifier(name, exercise, args.seed), rows, groups, keep
        )
        results_by_model[name] = results
        print(f"=== Mô hình: {name} ===")
        for group, errors in unfit.items():
            print(
                f"CẢNH BÁO: lần chia test {group}: không fit được {', '.join(errors)} "
                "(quá ít rep dương trong train) → không bao giờ báo, F1 = 0 kéo macro-F1 xuống."
            )
        if name == "rules":
            for e in main_errors:
                if e in RuleBased(exercise).missing:
                    print(f"CẢNH BÁO: {e} nằm trong lỗi chính nhưng chưa có luật.")
        print(
            report(results, ds.error_labels, main_errors, notes_for(name, args.exercise, exercise))
        )
        if learned:
            print()
            print(threshold_table(exercise, learned))
        if importances:
            print()
            print(
                importance_table(
                    importances, list(exercise.error_labels), experimental=experimental
                )
            )
        print()
    print(summary_table(results_by_model, main_errors, experimental))

    if args.boot > 0:
        reference = "rules" if "rules" in results_by_model else names[0]
        print()
        print(ci_table(results_by_model, main_errors, args.boot, args.seed, reference))

    if args.seed_runs > 0:
        for name in (n for n in names if n in RANDOM_MODELS):
            runs = []
            for seed in range(args.seed, args.seed + args.seed_runs):
                results = cross_validate(
                    lambda name=name, seed=seed: make_classifier(name, exercise, seed),
                    rows,
                    groups,
                )
                _, macro, exact = summarize(results, main_errors)
                runs.append((seed, macro, exact))
            print()
            print(seed_table(name, runs))


if __name__ == "__main__":
    main()
