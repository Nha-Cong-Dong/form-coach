"""Dựng dữ liệu cho màn hình gán nhãn: một hiệp → thời gian, góc, khung xương rút gọn, rep, nhãn.

Hàm thuần (không đụng HTTP hay ổ đĩa) để backend chỉ việc đọc file và trả kết quả.
NaN được đổi thành None vì JSON không có NaN.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from formcoach.exercises.base import Exercise
from formcoach.labels import SessionLabels, check_alignment, default_labels, to_dict
from formcoach.pipeline import analyze
from formcoach.pose.session_json import SessionMeta
from formcoach.types import PoseSequence

# Khớp đủ để vẽ người que nhìn từ bên hông (bỏ ngón tay, mắt, miệng cho nhẹ).
STICK_JOINTS = [
    "nose",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


def _num(x: float, digits: int) -> float | None:
    return None if not math.isfinite(x) else round(float(x), digits)


def _series(x: np.ndarray, digits: int = 1) -> list[float | None]:
    return [_num(v, digits) for v in x]


def build_review(
    pose: PoseSequence,
    meta: SessionMeta,
    exercise: Exercise,
    saved: SessionLabels | None,
) -> dict[str, Any]:
    """Dữ liệu xem lại + nhãn (đã lưu, hoặc mặc định từ set_errors nếu chưa gán)."""
    features, reps = analyze(pose, exercise)
    times = (meta.timestamps_ms - meta.timestamps_ms[0]) / 1000.0
    th = exercise.phase_thresholds()

    if saved is None:
        labels = default_labels(meta.session_id, meta.exercise, reps, times, meta.set_errors, th)
        problems: list[str] = []
    else:
        labels = saved
        problems = check_alignment(saved, reps, times)

    idx = [pose.joint_names.index(j) for j in STICK_JOINTS]
    keypoints = [
        [None if not np.isfinite(p[:2]).all() else [_num(p[0], 4), _num(p[1], 4)] for p in frame]
        for frame in pose.keypoints[:, idx, :]
    ]

    return {
        "session_id": meta.session_id,
        "exercise": meta.exercise,
        "recorded_at": meta.recorded_at,
        "set_errors": sorted(meta.set_errors),
        "notes": meta.notes,
        "error_labels": list(exercise.error_labels),
        "frame_size": list(pose.frame_size),
        "fps": round(pose.fps, 2),
        "times_s": _series(times, 3),
        "primary_signal": exercise.primary_signal(),
        "signals": {n: _series(v) for n, v in features.signals.items() if not n.endswith("_raw")},
        "thresholds": {k: th[k] for k in ("top_min", "min_amplitude_deg")},
        "joints": STICK_JOINTS,
        "keypoints": keypoints,  # [khung][khớp] = [x, y] chuẩn hoá 0–1, hoặc None
        "reps": [
            {
                "index": r.index,
                "start_frame": r.start_frame,
                "end_frame": r.end_frame,
                "start_s": _num(times[r.start_frame], 3),
                "end_s": _num(times[r.end_frame], 3),
                "features": {k: _num(v, 2) for k, v in r.features.items()},
            }
            for r in reps
        ],
        "labels": to_dict(labels),
        "labels_saved": saved is not None,
        "alignment_problems": problems,  # khác rỗng → nhãn đã lưu không còn khớp rep hiện tại
    }
