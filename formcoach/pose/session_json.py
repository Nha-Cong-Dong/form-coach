"""Đọc file keypoint do trang quay (MediaPipe JS) xuất ra — ranh giới giữa web/ và Python.

Định dạng xem docs/ARCHITECTURE.md §2b. File đến từ bên ngoài (trình duyệt, sau này qua mạng)
nên mọi trường đều được kiểm tra; sai thì báo `SessionFormatError` nói rõ sai ở đâu,
thay vì để lỗi khó hiểu nổ ra ở bước sau.

`t_ms` của camera trình duyệt không đều nhau. Bản hiện tại chỉ yêu cầu `t_ms` tăng ngặt và
đặt fps = 1000 / trung vị khoảng cách khung; có cần lấy mẫu lại về fps cố định hay không
sẽ quyết định ở bước 10 khi đo độ dao động thật (xem ARCHITECTURE).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from formcoach.exercises import EXERCISES
from formcoach.pose.joints import MEDIAPIPE_JOINTS
from formcoach.types import PoseSequence

FORMAT_VERSION = 1
# Chỉ chữ, số, '_' và '-': session_id được dùng làm tên file, chặn '../' hay '/'.
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
REQUIRED_KEYS = (
    "format_version",
    "session_id",
    "exercise",
    "set_errors",
    "recorded_at",
    "source",
    "frame_size",
    "joint_names",
    "frames",
)


class SessionFormatError(ValueError):
    """File JSON không đúng định dạng §2b."""


@dataclass(frozen=True)
class SessionMeta:
    """Thông tin về hiệp quay, đi kèm PoseSequence."""

    session_id: str
    exercise: str
    set_errors: frozenset[str]  # tập lỗi cố ý của cả hiệp; rỗng = hiệp tập đúng
    recorded_at: str  # ISO 8601, giữ nguyên chuỗi gốc
    source: dict[str, str]  # {"pose": "mediapipe-js", "version": ..., "model": ...}
    timestamps_ms: np.ndarray = field(repr=False)  # (T,) t_ms gốc, để đo độ đều của khung


def _is_number(x: Any) -> bool:
    # bool là lớp con của int trong Python, nhưng true/false trong JSON không phải toạ độ.
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _parse_frames(frames: Any) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(frames, list) or len(frames) < 2:
        raise SessionFormatError("'frames' phải là danh sách có ít nhất 2 khung")
    n_joints = len(MEDIAPIPE_JOINTS)
    keypoints = np.full((len(frames), n_joints, 3), np.nan)
    t_ms = np.empty(len(frames))
    for i, frame in enumerate(frames):
        if not isinstance(frame, dict) or "t_ms" not in frame or "kp" not in frame:
            raise SessionFormatError(f"khung {i}: phải là object có 't_ms' và 'kp'")
        if not _is_number(frame["t_ms"]) or frame["t_ms"] < 0:
            raise SessionFormatError(f"khung {i}: 't_ms' phải là số không âm")
        t_ms[i] = frame["t_ms"]
        kp = frame["kp"]
        if kp is None:  # không thấy người → giữ hàng NaN
            continue
        if not isinstance(kp, list) or len(kp) != n_joints:
            raise SessionFormatError(f"khung {i}: 'kp' phải là null hoặc {n_joints} khớp")
        for j, point in enumerate(kp):
            if not isinstance(point, list) or len(point) != 3 or not all(map(_is_number, point)):
                raise SessionFormatError(f"khung {i}, khớp {j}: phải là [x, y, visibility] số")
        keypoints[i] = kp
    steps = np.diff(t_ms)
    if (steps <= 0).any():
        bad = int(np.argmax(steps <= 0)) + 1
        raise SessionFormatError(f"khung {bad}: 't_ms' phải tăng ngặt so với khung trước")
    return keypoints, t_ms


def parse_session(data: Any) -> tuple[PoseSequence, SessionMeta]:
    """Kiểm tra và chuyển dict (đã json.loads) thành PoseSequence + SessionMeta."""
    if not isinstance(data, dict):
        raise SessionFormatError("nội dung phải là một JSON object")
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise SessionFormatError(f"thiếu trường: {', '.join(missing)}")
    if data["format_version"] != FORMAT_VERSION:
        raise SessionFormatError(
            f"format_version {data['format_version']!r} không hỗ trợ (cần {FORMAT_VERSION})"
        )

    session_id = data["session_id"]
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        raise SessionFormatError("'session_id' chỉ được gồm chữ, số, '_' và '-' (1–100 ký tự)")

    exercise_name = data["exercise"]
    if exercise_name not in EXERCISES:
        raise SessionFormatError(
            f"bài tập {exercise_name!r} không hỗ trợ (hợp lệ: {sorted(EXERCISES)})"
        )
    valid_errors = set(EXERCISES[exercise_name].error_labels)
    set_errors = data["set_errors"]
    if not isinstance(set_errors, list) or not all(isinstance(e, str) for e in set_errors):
        raise SessionFormatError("'set_errors' phải là danh sách chuỗi")
    unknown = sorted(set(set_errors) - valid_errors)
    if unknown:
        raise SessionFormatError(f"lỗi không hợp lệ cho {exercise_name}: {unknown}")
    if len(set(set_errors)) != len(set_errors):
        raise SessionFormatError("'set_errors' bị trùng phần tử")

    recorded_at = data["recorded_at"]
    try:
        datetime.fromisoformat(recorded_at)
    except (TypeError, ValueError):
        raise SessionFormatError("'recorded_at' phải là thời điểm dạng ISO 8601") from None

    source = data["source"]
    if not isinstance(source, dict) or not all(isinstance(v, str) for v in source.values()):
        raise SessionFormatError("'source' phải là object có giá trị là chuỗi")

    size = data["frame_size"]
    if (
        not isinstance(size, list)
        or len(size) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in size)
    ):
        raise SessionFormatError("'frame_size' phải là [width, height] số nguyên dương")

    if data["joint_names"] != MEDIAPIPE_JOINTS:
        raise SessionFormatError("'joint_names' phải đúng 33 tên khớp MediaPipe theo thứ tự")

    keypoints, t_ms = _parse_frames(data["frames"])
    fps = 1000.0 / float(np.median(np.diff(t_ms)))

    pose = PoseSequence(
        keypoints=keypoints,
        joint_names=list(MEDIAPIPE_JOINTS),
        fps=fps,
        frame_size=(size[0], size[1]),
    )
    meta = SessionMeta(
        session_id=session_id,
        exercise=exercise_name,
        set_errors=frozenset(set_errors),
        recorded_at=recorded_at,
        source=dict(source),
        timestamps_ms=t_ms,
    )
    return pose, meta


def load_session_json(path: Path) -> tuple[PoseSequence, SessionMeta]:
    """Đọc file JSON từ trang quay. JSON hỏng cũng báo SessionFormatError."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SessionFormatError(f"không phải JSON hợp lệ: {e}") from None
    return parse_session(data)
