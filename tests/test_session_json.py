import copy
import json
from pathlib import Path

import numpy as np
import pytest

from formcoach.exercises import PushUp, get_exercise
from formcoach.features.extractor import FeatureExtractor
from formcoach.features.segmenter import RepSegmenter
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.pose.session_json import SessionFormatError, load_session_json, parse_session

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
    """Dict giống hệt file trang quay sẽ xuất: ~30 fps, t_ms dao động ±jitter_ms."""
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


# --- đọc đúng ---


def test_valid_session() -> None:
    pose, meta = parse_session(make_session())
    assert pose.keypoints.shape == (60, 33, 3)
    assert pose.joint_names == MEDIAPIPE_JOINTS
    assert pose.frame_size == SIZE
    assert meta.session_id == "2026-10-20T19-05-12_pushup"
    assert meta.exercise == "pushup"
    assert meta.set_errors == frozenset()
    assert meta.source["pose"] == "mediapipe-js"
    assert meta.timestamps_ms.shape == (60,)


def test_fps_from_jittery_timestamps() -> None:
    # Khung cách nhau 33 ms ± 10 ms ngẫu nhiên. Trung vị của ~300 khoảng cách cũng dao động
    # khoảng ±1 ms (≈ ±1 fps) tuỳ seed, nên dung sai ±2 fps.
    pose, _ = parse_session(make_session(np.full(300, 165.0), jitter_ms=10.0))
    assert pose.fps == pytest.approx(30.0, abs=2.0)


def test_fps_robust_to_browser_stalls() -> None:
    # Trình duyệt khựng 3 lần (500 ms không có khung, vd điện thoại nóng máy). Trung vị không
    # bị ảnh hưởng, còn fps tính bằng trung bình (số khung / thời lượng) tụt xuống ~23:
    # lý do chọn trung vị.
    data = make_session(np.full(150, 165.0), jitter_ms=0.0)
    for start in (40, 80, 120):
        for frame in data["frames"][start:]:
            frame["t_ms"] += 500
    pose, meta = parse_session(data)
    assert pose.fps == pytest.approx(30.0, abs=0.5)
    mean_fps = (
        1000 * (len(meta.timestamps_ms) - 1) / (meta.timestamps_ms[-1] - meta.timestamps_ms[0])
    )
    assert mean_fps < 25


def test_null_kp_becomes_nan_row() -> None:
    data = make_session()
    data["frames"][5]["kp"] = None
    pose, _ = parse_session(data)
    assert np.isnan(pose.keypoints[5]).all()
    assert np.isfinite(pose.keypoints[4]).all() and np.isfinite(pose.keypoints[6]).all()


def test_set_errors_parsed() -> None:
    data = make_session()
    data["set_errors"] = ["shallow", "hip_sag"]
    _, meta = parse_session(data)
    assert meta.set_errors == frozenset({"shallow", "hip_sag"})


def test_load_from_file(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text(json.dumps(make_session()), encoding="utf-8")
    pose, meta = load_session_json(path)
    assert pose.keypoints.shape == (60, 33, 3)
    assert meta.exercise == "pushup"


def test_session_feeds_rep_counter() -> None:
    # File trang quay → extractor → bộ đếm: plank 1 s rồi 3 rep (165° ↔ 70°, 2,4 s/rep).
    t = np.arange(int(3 * 2.4 * 30)) / 30
    reps = 117.5 + 47.5 * np.cos(2 * np.pi * t / 2.4)
    elbow = np.concatenate([np.full(30, 165.0), reps, np.full(30, 165.0)])
    pose, meta = parse_session(make_session(elbow, jitter_ms=5.0))
    exercise = get_exercise(meta.exercise)
    features = FeatureExtractor().extract(pose, exercise)
    assert len(RepSegmenter().segment(features, exercise)) == 3


# --- báo lỗi rõ ràng ---


def broken(**changes) -> dict:
    data = make_session()
    for key, value in changes.items():
        if value is ...:
            del data[key]
        else:
            data[key] = value
    return data


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ([], "JSON object"),
        (broken(frames=...), "thiếu trường: frames"),
        (broken(format_version=2), "format_version"),
        (broken(session_id="../../etc/passwd"), "session_id"),
        (broken(session_id="a/b"), "session_id"),
        (broken(session_id=""), "session_id"),
        (broken(exercise="deadlift"), "không hỗ trợ"),
        (broken(set_errors=["good"]), "không hợp lệ"),
        (broken(set_errors=["shallow", "shallow"]), "trùng"),
        (broken(set_errors="shallow"), "danh sách chuỗi"),
        (broken(recorded_at="hôm qua"), "ISO 8601"),
        (broken(source="mediapipe"), "'source'"),
        (broken(frame_size=[1280]), "frame_size"),
        (broken(frame_size=[1280, 0]), "frame_size"),
        (broken(frame_size=[1280.5, 720]), "frame_size"),
        (broken(joint_names=MEDIAPIPE_JOINTS[:32]), "joint_names"),
        (broken(frames=[]), "ít nhất 2 khung"),
    ],
)
def test_format_errors(data, message: str) -> None:
    with pytest.raises(SessionFormatError, match=message):
        parse_session(data)


def test_bad_frame_errors_name_the_frame() -> None:
    cases = [
        (lambda f: f[3].pop("t_ms"), "khung 3"),
        (lambda f: f[3].update(kp=[[0.5, 0.5, 0.9]] * 32), "khung 3"),
        (lambda f: f[3]["kp"][7].__setitem__(1, "x"), "khung 3, khớp 7"),
        (lambda f: f[3]["kp"][7].__setitem__(2, True), "khung 3, khớp 7"),
        (lambda f: f[3].update(t_ms=-1), "khung 3"),
    ]
    for mutate, message in cases:
        data = copy.deepcopy(make_session())
        mutate(data["frames"])
        with pytest.raises(SessionFormatError, match=message):
            parse_session(data)


def test_non_increasing_t_ms_rejected() -> None:
    data = make_session()
    data["frames"][10]["t_ms"] = data["frames"][9]["t_ms"]  # trùng timestamp
    with pytest.raises(SessionFormatError, match="khung 10.*tăng ngặt"):
        parse_session(data)


def test_invalid_json_file(tmp_path: Path) -> None:
    path = tmp_path / "hong.json"
    path.write_text("{ không phải json", encoding="utf-8")
    with pytest.raises(SessionFormatError, match="không phải JSON"):
        load_session_json(path)


def test_get_exercise() -> None:
    assert isinstance(get_exercise("pushup"), PushUp)
    with pytest.raises(KeyError, match="pushup"):
        get_exercise("deadlift")
