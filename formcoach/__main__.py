"""Dòng lệnh của Form Coach. Chạy từ gốc repo:

python -m formcoach analyze data/sessions/pushup/<session_id>.json
python -m formcoach analyze data/videos/pushup_clean.mp4 --plot
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from formcoach.features.extractor import choose_side, side_visibility
from formcoach.labels import LabelFormatError, SessionLabels, check_alignment, load_labels
from formcoach.models import RuleBased
from formcoach.pipeline import DEFAULT_MODEL, Source, analyze, frame_timing, load_source
from formcoach.types import Rep


def _fmt(value: float, is_offset: bool) -> str:
    # Góc in bằng độ; độ lệch (hip_offset) là tỉ lệ theo độ dài thân, không có đơn vị.
    return f"{value:+6.3f}" if is_offset else f"{value:6.1f}°"


def _percentiles(x: np.ndarray, is_offset: bool) -> str:
    v = x[np.isfinite(x)]
    if v.size == 0:
        return "không có giá trị"
    p5, p50, p95 = (_fmt(p, is_offset) for p in np.percentile(v, [5, 50, 95]))
    return f"p5 {p5}  p50 {p50}  p95 {p95}  (NaN {np.isnan(x).sum()}/{x.size})"


def _errors(errors: frozenset[str]) -> str:
    return ", ".join(sorted(errors)) or "không lỗi"


def _saved_labels(path: Path, src: Source, reps: list[Rep]) -> SessionLabels | None:
    """Nhãn đã gán của hiệp (nếu file nằm trong <data>/sessions/<bài>/ và nhãn còn khớp rep)."""
    if src.meta is None or path.parent.parent.name != "sessions":
        return None
    try:
        labels = load_labels(path.parents[2], src.meta.exercise, src.meta.session_id)
    except LabelFormatError as e:
        print(f"File nhãn hỏng, bỏ qua: {e}")
        return None
    if labels is None:
        return None
    problems = check_alignment(labels, reps, src.times_s)
    if problems:
        print(f"Nhãn đã lưu không khớp rep hiện tại, bỏ qua: {'; '.join(problems)}")
        return None
    return labels


def _print_rule_predictions(path: Path, src: Source, reps: list[Rep]) -> None:
    model = RuleBased(src.exercise)
    results = model.predict(reps)
    labels = _saved_labels(path, src, reps)
    print("\nLỗi theo luật" + (" (so với nhãn đã gán):" if labels else ":"))
    if model.missing:
        print(f"  chưa có luật cho: {', '.join(model.missing)}")
    matched = valid = 0
    for res in results:
        line = f"  rep {res.rep.index + 1}: luật {_errors(res.errors)}"
        if labels is not None:
            lab = labels.reps[res.rep.index]
            if not lab.valid:
                line += " | nhãn: không phải rep"
            else:
                valid += 1
                # So trên các lỗi có luật: lỗi chưa có luật thì luật không thể đoán.
                truth = lab.errors - set(model.missing)
                ok = res.errors == truth
                matched += ok
                line += f" | nhãn {_errors(lab.errors)}  {'khớp' if ok else 'KHÁC'}"
                skipped = sorted(lab.errors & set(model.missing))
                if skipped:
                    line += f" (không so {', '.join(skipped)}: chưa có luật)"
        print(line)
    if labels is not None:
        print(f"  khớp hoàn toàn {matched}/{valid} rep (chỉ để kiểm tra luật, không phải đánh giá)")


def cmd_analyze(args: argparse.Namespace) -> None:
    src = load_source(args.path, args.model)
    pose, exercise, t = src.pose, src.exercise, src.times_s
    features, reps = analyze(pose, exercise)
    vis = side_visibility(pose, exercise)

    print(
        f"== {args.path.name}: {exercise.name}, {len(t)} khung, {t[-1]:.1f} s, {pose.fps:.1f} fps"
    )
    if src.meta is not None:
        tm = frame_timing(src.meta.timestamps_ms)
        print(
            f"Khoảng cách khung: trung vị {tm.median_ms:.1f} ms, lệch chuẩn {tm.std_ms:.1f} ms "
            f"({100 * tm.jitter_ratio:.0f}%), p95 {tm.p95_ms:.1f} ms, lớn nhất {tm.max_ms:.0f} ms, "
            f"{tm.long_gaps} lần khựng > 3× trung vị"
        )
        errors = ", ".join(sorted(src.meta.set_errors)) or "không (tập đúng)"
        print(f"Lỗi cố ý của hiệp: {errors}")
    print(
        f"Bên dùng: {choose_side(pose, exercise)} "
        f"(visibility TB trái {vis['left']:.2f}, phải {vis['right']:.2f})"
    )
    offsets = set(exercise.offset_definitions())
    for name, sig in features.signals.items():
        if not name.endswith("_raw"):
            print(f"  {name:<12} {_percentiles(sig, name in offsets)}")

    print(f"\nĐếm được {len(reps)} rep:")
    for r in reps:
        f = r.features
        line = f"  rep {r.index + 1}: {t[r.start_frame]:5.1f}–{t[r.end_frame]:5.1f} s"
        line += f"  dài {f['duration_s']:.1f} s"
        # Mỗi góc: nhỏ nhất trong rep (một khung) và trung vị (tư thế giữ suốt rep, "tv").
        line += "".join(
            f"  {k} {v:5.1f}° (tv {f[f'median_{k[4:]}']:5.1f}°)"
            for k, v in f.items()
            if k.startswith("min_") and "tilt" not in k and k[4:] not in offsets
        )
        # Đỉnh sau rep (incomplete_lockout).
        line += "".join(f"  {k} {v:5.1f}°" for k, v in f.items() if k.startswith("top_"))
        # Độ lệch có hai phía (nhô/võng) nên in cả nhỏ nhất và lớn nhất.
        for name in offsets:
            if f"min_{name}" in f:
                line += (
                    f"  {name} {f[f'min_{name}']:+.3f}…{f[f'max_{name}']:+.3f}"
                    f" (tv {f[f'median_{name}']:+.3f})"
                )
        print(line)

    _print_rule_predictions(args.path, src, reps)

    if args.plot:
        from formcoach.plot import plot_session  # matplotlib chỉ tải khi cần vẽ

        out = args.out / f"{args.path.stem}_signals.png"
        print(f"\nĐồ thị: {plot_session(src, features, reps, args.path.name, out)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m formcoach", description="Form Coach")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="đếm rep của một hiệp (file JSON từ trang quay hoặc video)")
    p.add_argument("path", type=Path, help="data/sessions/<bài>/<id>.json hoặc video .mp4")
    p.add_argument("--plot", action="store_true", help="vẽ đồ thị tín hiệu ra --out")
    p.add_argument("--out", type=Path, default=Path("outputs"), help="thư mục lưu đồ thị")
    p.add_argument(
        "--model", type=Path, default=DEFAULT_MODEL, help="model MediaPipe (chỉ cho video)"
    )
    p.set_defaults(func=cmd_analyze)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
