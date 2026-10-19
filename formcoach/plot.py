"""Vẽ tín hiệu của một hiệp theo thời gian, tô vùng từng rep: để kiểm tra bằng mắt.

Dùng Figure trực tiếp (không qua pyplot) nên vẽ thẳng ra file, không cần cửa sổ.
"""

from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure

from formcoach.pipeline import Source
from formcoach.types import FeatureSeries, Rep


def plot_session(
    source: Source, features: FeatureSeries, reps: list[Rep], title: str, out_path: Path
) -> Path:
    """Một hàng cho tín hiệu chính (thô + làm mượt + 2 ngưỡng đếm rep), một hàng cho mỗi tín hiệu
    còn lại (tín hiệu nghiêng kèm ngưỡng sẵn sàng), hàng cuối là visibility khớp đỉnh của
    tín hiệu chính ở hai bên."""
    exercise, t, signals = source.exercise, source.times_s, features.signals
    th = exercise.phase_thresholds()
    primary = exercise.primary_signal()
    others = [n for n in signals if not n.endswith("_raw") and n != primary]
    tilts = set(exercise.tilt_definitions())

    fig = Figure(figsize=(14, 3 * (len(others) + 2)))
    axes = fig.subplots(len(others) + 2, 1, sharex=True)

    for r in reps:  # tô vùng từng rep trên mọi hàng
        for ax in axes:
            ax.axvspan(t[r.start_frame], t[r.end_frame], color="tab:green", alpha=0.1)
        mid = (t[r.start_frame] + t[r.end_frame]) / 2
        axes[0].text(mid, 175, str(r.index + 1), ha="center", fontsize=11, color="tab:green")

    ax = axes[0]
    ax.plot(t, signals[f"{primary}_raw"], color="tab:blue", lw=0.8, alpha=0.35, label="thô")
    ax.plot(t, signals[primary], color="tab:blue", lw=1.4, label="đã lọc + làm mượt")
    ax.axhline(th["top_min"], color="tab:green", ls="--", label=f"top_min {th['top_min']:.0f}°")
    ax.axhline(
        th["descent_trigger"],
        color="tab:red",
        ls="--",
        label=f"descent_trigger {th['descent_trigger']:.0f}°",
    )
    ax.set_ylabel(f"{primary} (°)")
    ax.set_ylim(0, 185)
    ax.legend(loc="lower right")
    ax.set_title(f"{title} — đếm được {len(reps)} rep (vùng xanh)")

    for ax, name in zip(axes[1:-1], others, strict=True):
        ax.plot(t, signals[name], lw=1.2, color="tab:orange" if name in tilts else "tab:purple")
        ax.set_ylabel(f"{name} (°)")
        if name in tilts:
            limit = th["ready_max_tilt_deg"]
            ax.axhline(limit, color="tab:red", ls="--", label=f"ready_max_tilt {limit:.0f}°")
            ax.set_ylim(0, 95)
            ax.legend(loc="upper right")

    vertex = exercise.angle_definitions()[primary][1]  # khớp đỉnh, vd "elbow"
    ax = axes[-1]
    pose = source.pose
    for side, color in (("left", "tab:orange"), ("right", "tab:blue")):
        idx = pose.joint_names.index(f"{side}_{vertex}")
        ax.plot(t, pose.keypoints[:, idx, 2], color=color, lw=1, label=f"{vertex} {side}")
    ax.axhline(th["min_joint_visibility"], color="tab:red", ls=":", lw=1)
    ax.set_ylabel("visibility")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("thời gian (s)")
    ax.legend(loc="lower right")

    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    return out_path
