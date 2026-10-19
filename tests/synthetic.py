"""Dữ liệu tổng hợp dùng chung cho nhiều file test (không phải file test)."""

import numpy as np

from formcoach.pose.joints import MEDIAPIPE_JOINTS

SIZE = (1280, 720)


def plank_keypoints(elbow_deg: np.ndarray) -> np.ndarray:
    """(T, 33, 3) chuẩn hoá 0–1: thân nằm ngang, góc khuỷu phải theo elbow_deg, bên phải rõ."""
    n = len(elbow_deg)
    kp = np.full((n, 33, 3), 0.5)
    kp[:, :, 2] = 0.2
    shoulder = np.array([400.0, 300.0])
    elbow = shoulder + [0.0, 150.0]
    phi = np.radians(-90.0 + elbow_deg)
    wrist = elbow + 150.0 * np.stack([np.cos(phi), np.sin(phi)], axis=1)
    points = {
        "shoulder": shoulder,
        "elbow": elbow,
        "wrist": wrist,
        "hip": shoulder + [300.0, 0.0],
        "ankle": shoulder + [600.0, 0.0],
    }
    for joint, px in points.items():
        idx = MEDIAPIPE_JOINTS.index(f"right_{joint}")
        kp[:, idx, :2] = np.broadcast_to(px, (n, 2)) / np.array(SIZE)
        kp[:, idx, 2] = 0.95
    return kp


def make_session(
    elbow_deg: np.ndarray | None = None, jitter_ms: float = 10.0, seed: int = 0
) -> dict:
    """Dict giống file trang quay xuất (ARCHITECTURE §2b): ~30 fps, t_ms lệch ±jitter_ms."""
    if elbow_deg is None:
        elbow_deg = np.full(60, 165.0)
    n = len(elbow_deg)
    rng = np.random.default_rng(seed)
    t_ms = np.cumsum(np.full(n, 1000 / 30) + rng.uniform(-jitter_ms, jitter_ms, n))
    t_ms -= t_ms[0]
    kp = plank_keypoints(elbow_deg)
    return {
        "format_version": 1,
        "session_id": "2026-10-20T19-05-12_pushup",
        "exercise": "pushup",
        "set_errors": [],
        "recorded_at": "2026-10-20T19:05:12+07:00",
        "source": {"pose": "mediapipe-js", "version": "1.1.1", "model": "pose_landmarker_full"},
        "frame_size": list(SIZE),
        "joint_names": list(MEDIAPIPE_JOINTS),
        "frames": [{"t_ms": round(float(t), 1), "kp": kp[i].tolist()} for i, t in enumerate(t_ms)],
    }
