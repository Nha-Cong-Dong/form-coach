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
from formcoach.pipeline import DEFAULT_MODEL, analyze, frame_timing, load_source


def _percentiles(x: np.ndarray) -> str:
    v = x[np.isfinite(x)]
    if v.size == 0:
        return "không có giá trị"
    p5, p50, p95 = np.percentile(v, [5, 50, 95])
    return f"p5 {p5:6.1f}°  p50 {p50:6.1f}°  p95 {p95:6.1f}°  (NaN {np.isnan(x).sum()}/{x.size})"


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
    for name, sig in features.signals.items():
        if not name.endswith("_raw"):
            print(f"  {name:<12} {_percentiles(sig)}")

    print(f"\nĐếm được {len(reps)} rep:")
    for r in reps:
        f = r.features
        line = f"  rep {r.index + 1}: {t[r.start_frame]:5.1f}–{t[r.end_frame]:5.1f} s"
        line += f"  dài {f['duration_s']:.1f} s"
        line += "".join(
            f"  {k} {v:5.1f}°" for k, v in f.items() if k.startswith("min_") and "tilt" not in k
        )
        print(line)

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
