"""Vẽ các tín hiệu push-up theo thời gian và các rep đếm được, để kiểm tra bằng mắt.

Chạy MediaPipe trên video → FeatureExtractor → RepSegmenter → vẽ 4 đồ thị chung trục thời gian:
góc khuỷu (thô + đã làm mượt, 2 ngưỡng đếm rep, vùng tô từng rep), góc thân, độ nghiêng thân
(kèm ngưỡng sẵn sàng), visibility khuỷu hai bên. Lưu PNG, in thống kê và danh sách rep.

Chạy từ gốc repo, dạng module (để Python tìm thấy package formcoach):
    python -m tools.plot_signals data/videos/pushup_clean.mp4
(Bước 10 sẽ cho nhận thêm file JSON từ trang quay.)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure  # vẽ thẳng ra file, không cần mở cửa sổ (pyplot)

from formcoach.exercises import PushUp
from formcoach.features.extractor import FeatureExtractor, choose_side, side_visibility
from formcoach.features.segmenter import RepSegmenter
from formcoach.pose.mediapipe_estimator import MediaPipeEstimator


def describe(name: str, x: np.ndarray) -> str:
    v = x[np.isfinite(x)]
    if v.size == 0:
        return f"  {name:<12} không có giá trị"
    p5, p50, p95 = np.percentile(v, [5, 50, 95])
    return (
        f"  {name:<12} p5 {p5:6.1f}°  p50 {p50:6.1f}°  p95 {p95:6.1f}°  "
        f"(NaN {np.isnan(x).sum()}/{x.size} khung)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video", type=Path)
    parser.add_argument("--model", type=Path, default=Path("assets/pose_landmarker_full.task"))
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    args = parser.parse_args()

    exercise = PushUp()
    pose = MediaPipeEstimator(args.model).estimate(args.video)
    feats = FeatureExtractor().extract(pose, exercise)
    th = exercise.phase_thresholds()
    side = choose_side(pose, exercise)
    vis = side_visibility(pose, exercise)
    t = np.arange(len(pose.keypoints)) / pose.fps

    print(f"== {args.video.name}: {len(t)} khung, {t[-1]:.1f} s, {pose.fps:.2f} fps")
    print(f"Bên dùng: {side} (visibility TB trái {vis['left']:.2f}, phải {vis['right']:.2f})")
    for name, sig in feats.signals.items():
        if not name.endswith("_raw"):
            print(describe(name, sig))

    reps = RepSegmenter().segment(feats, exercise)
    print(f"\nĐếm được {len(reps)} rep:")
    for r in reps:
        f = r.features
        print(
            f"  rep {r.index + 1}: {r.start_frame / pose.fps:5.1f}–{r.end_frame / pose.fps:5.1f} s"
            f"  dài {f['duration_s']:.1f} s  khuỷu thấp nhất {f['min_elbow_angle']:5.1f}°"
            f"  thân thấp nhất {f['min_body_angle']:5.1f}°"
        )

    elbow_idx = {s: pose.joint_names.index(f"{s}_elbow") for s in ("left", "right")}
    fig = Figure(figsize=(14, 11))
    axes = fig.subplots(4, 1, sharex=True)

    for r in reps:  # tô vùng từng rep trên mọi đồ thị
        for ax in axes:
            ax.axvspan(
                r.start_frame / pose.fps, r.end_frame / pose.fps, color="tab:green", alpha=0.1
            )
        mid = (r.start_frame + r.end_frame) / 2 / pose.fps
        axes[0].text(mid, 175, str(r.index + 1), ha="center", fontsize=11, color="tab:green")

    ax = axes[0]
    ax.plot(t, feats.signals["elbow_angle_raw"], color="tab:blue", lw=0.8, alpha=0.35, label="thô")
    ax.plot(t, feats.signals["elbow_angle"], color="tab:blue", lw=1.4, label="đã làm mượt")
    ax.axhline(th["top_min"], color="tab:green", ls="--", label=f"top_min {th['top_min']:.0f}°")
    ax.axhline(
        th["descent_trigger"],
        color="tab:red",
        ls="--",
        label=f"descent_trigger {th['descent_trigger']:.0f}°",
    )
    ax.set_ylabel("góc khuỷu (°)")
    ax.legend(loc="lower right")
    ax.set_ylim(50, 185)
    ax.set_title(f"{args.video.name} — bên {side}, đếm được {len(reps)} rep (vùng xanh)")

    axes[1].plot(t, feats.signals["body_angle"], color="tab:purple", lw=1.2)
    axes[1].set_ylabel("góc thân vai–hông–cổ chân (°)")

    ax = axes[2]
    ax.plot(t, feats.signals["body_tilt"], color="tab:orange", lw=1.2)
    ax.axhline(
        th["ready_max_tilt_deg"],
        color="tab:red",
        ls="--",
        label=f"ready_max_tilt {th['ready_max_tilt_deg']:.0f}°",
    )
    ax.set_ylabel("độ nghiêng thân (°)")
    ax.set_ylim(0, 95)
    ax.legend(loc="upper right")

    ax = axes[3]
    for s, color in (("left", "tab:orange"), ("right", "tab:blue")):
        ax.plot(t, pose.keypoints[:, elbow_idx[s], 2], color=color, lw=1, label=f"khuỷu {s}")
    ax.set_ylabel("visibility")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("thời gian (s)")
    ax.legend(loc="lower right")

    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.video.stem}_signals.png"
    fig.savefig(path, dpi=110)
    print(f"Đồ thị: {path}")


if __name__ == "__main__":
    main()
