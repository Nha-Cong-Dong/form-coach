"""Đọc file keypoint do trang quay (MediaPipe JS) xuất ra — ranh giới giữa web/ và Python.

Định dạng xem docs/ARCHITECTURE.md §2b. File đến từ bên ngoài (trình duyệt, sau này qua mạng)
nên mọi trường đều được kiểm tra; sai thì báo `SessionFormatError` nói rõ sai ở đâu,
thay vì để lỗi khó hiểu nổ ra ở bước sau.

Hai phiên bản: v1 (`frames`: mỗi khung một object, đọc được bằng mắt) và v2 (`t_ms` + `kp_i16`:
keypoint dạng int16 base64, numpy đọc thẳng, đỡ RAM ~12 lần cỡ file của v1). Cả hai ra cùng
`PoseSequence` + `SessionMeta`.

`t_ms` của camera trình duyệt không đều nhau. Bản hiện tại chỉ yêu cầu `t_ms` tăng ngặt và
đặt fps = 1000 / trung vị khoảng cách khung; có cần lấy mẫu lại về fps cố định hay không
sẽ quyết định ở bước 10 khi đo độ dao động thật (xem ARCHITECTURE).
"""

from __future__ import annotations

import base64
import binascii
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

FORMAT_VERSIONS = (1, 2)  # đọc được cả hai (ARCHITECTURE §2b)
# v2: giá trị int16 = round(v × KP_SCALE); cả khung bằng KP_MISSING = không thấy người.
KP_SCALE = 10_000
KP_MISSING = -32768
KP_LIMIT = 32767 / KP_SCALE  # |v| lớn nhất lưu được (~3,28 lần khung)
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
)
# Trường keypoint riêng của từng phiên bản.
FRAME_KEYS = {1: ("frames",), 2: ("t_ms", "kp_i16")}
MAX_NOTES_LEN = 1000  # ghi chú tuỳ chọn (D4): vài câu về điều kiện quay, không phải văn bản dài
# Hiệp quay từ đâu: "dataset" = Quay dữ liệu (có lỗi cố ý `set_errors`, công cụ thu dataset);
# "train" = chế độ Tập của app (không có kịch bản lỗi, `set_errors` rỗng KHÔNG có nghĩa "cố ý
# tập đúng"). File cũ không có trường này đều quay bằng màn Quay dữ liệu → mặc định "dataset".
CAPTURE_MODES = ("dataset", "train")


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
    notes: str = ""  # ghi chú tuỳ chọn về điều kiện quay; file cũ không có trường này → ""
    capture_mode: str = "dataset"  # "dataset" | "train" (CAPTURE_MODES); file cũ → "dataset"


def _is_number(x: Any) -> bool:
    # bool là lớp con của int trong Python, nhưng true/false trong JSON không phải toạ độ.
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_t_ms(t_ms: np.ndarray) -> None:
    steps = np.diff(t_ms)
    if (steps <= 0).any():
        bad = int(np.argmax(steps <= 0)) + 1
        raise SessionFormatError(f"khung {bad}: 't_ms' phải tăng ngặt so với khung trước")


def _parse_frames(frames: Any) -> tuple[np.ndarray, np.ndarray]:
    """v1: `frames` = [{t_ms, kp}] → (keypoints (T, 33, 3), t_ms (T,))."""
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
    _check_t_ms(t_ms)
    return keypoints, t_ms


def _parse_packed(t_list: Any, kp_text: Any) -> tuple[np.ndarray, np.ndarray]:
    """v2: `t_ms` (danh sách số) + `kp_i16` (base64 int16 little-endian) → như `_parse_frames`."""
    if not isinstance(t_list, list) or len(t_list) < 2:
        raise SessionFormatError("'t_ms' phải là danh sách có ít nhất 2 khung")
    for i, t in enumerate(t_list):
        if not _is_number(t) or t < 0:
            raise SessionFormatError(f"khung {i}: 't_ms' phải là số không âm")
    t_ms = np.asarray(t_list, dtype=float)
    _check_t_ms(t_ms)

    if not isinstance(kp_text, str):
        raise SessionFormatError("'kp_i16' phải là chuỗi base64")
    try:
        raw = base64.b64decode(kp_text, validate=True)
    except (binascii.Error, ValueError):
        raise SessionFormatError("'kp_i16' không phải base64 hợp lệ") from None
    n_values = len(t_ms) * len(MEDIAPIPE_JOINTS) * 3
    if len(raw) != n_values * 2:
        raise SessionFormatError(
            f"'kp_i16' dài {len(raw)} byte, cần {n_values * 2} (= {len(t_ms)} khung × 33 khớp"
            " × 3 số × 2 byte)"
        )
    packed = np.frombuffer(raw, dtype="<i2").reshape(len(t_ms), len(MEDIAPIPE_JOINTS), 3)
    missing = packed == KP_MISSING
    frame_missing = missing.all(axis=(1, 2))
    partial = missing.any(axis=(1, 2)) & ~frame_missing
    if partial.any():
        bad = int(np.argmax(partial))
        raise SessionFormatError(
            f"khung {bad}: giá trị {KP_MISSING} (không thấy người) phải phủ cả khung"
        )
    keypoints = packed.astype(float) / KP_SCALE
    keypoints[frame_missing] = np.nan
    return keypoints, t_ms


def encode_kp_i16(keypoints: np.ndarray) -> str:
    """(T, 33, 3) → chuỗi `kp_i16` của v2. Hàng NaN (không thấy người) → cả khung `KP_MISSING`.

    Giá trị kẹp vào ±KP_LIMIT như web. Dùng cho test và khi server cắt bớt keypoint.
    """
    kp = np.asarray(keypoints, dtype=float)
    if kp.ndim != 3 or kp.shape[1:] != (len(MEDIAPIPE_JOINTS), 3):
        raise ValueError(f"keypoints phải có dạng (T, 33, 3), nhận {kp.shape}")
    nan = np.isnan(kp)
    frame_nan = nan.all(axis=(1, 2))
    if (nan.any(axis=(1, 2)) & ~frame_nan).any():
        raise ValueError("khung chỉ được toàn NaN (không thấy người) hoặc không có NaN")
    packed = np.round(np.clip(np.nan_to_num(kp), -KP_LIMIT, KP_LIMIT) * KP_SCALE).astype("<i2")
    packed[frame_nan] = KP_MISSING
    return base64.b64encode(packed.tobytes()).decode("ascii")


def parse_session(data: Any) -> tuple[PoseSequence, SessionMeta]:
    """Kiểm tra và chuyển dict (đã json.loads) thành PoseSequence + SessionMeta."""
    if not isinstance(data, dict):
        raise SessionFormatError("nội dung phải là một JSON object")
    if "format_version" not in data:
        raise SessionFormatError("thiếu trường: format_version")
    version = data["format_version"]
    if isinstance(version, bool) or version not in FORMAT_VERSIONS:
        raise SessionFormatError(
            f"format_version {version!r} không hỗ trợ (hợp lệ: {list(FORMAT_VERSIONS)})"
        )
    missing = [k for k in (*REQUIRED_KEYS, *FRAME_KEYS[version]) if k not in data]
    if missing:
        raise SessionFormatError(f"thiếu trường: {', '.join(missing)}")

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

    # Trường tuỳ chọn (thêm 2026-10-20, format_version vẫn 1): file cũ không có vẫn đọc được.
    notes = data.get("notes", "")
    if not isinstance(notes, str) or len(notes) > MAX_NOTES_LEN:
        raise SessionFormatError(f"'notes' phải là chuỗi, tối đa {MAX_NOTES_LEN} ký tự")
    # Trường tuỳ chọn (thêm 2026-10-24, format_version vẫn 1).
    capture_mode = data.get("capture_mode", "dataset")
    if capture_mode not in CAPTURE_MODES:
        raise SessionFormatError(f"'capture_mode' phải là một trong {list(CAPTURE_MODES)}")
    if capture_mode == "train" and set_errors:
        raise SessionFormatError("hiệp chế độ Tập không có lỗi cố ý ('set_errors' phải rỗng)")

    size = data["frame_size"]
    if (
        not isinstance(size, list)
        or len(size) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in size)
    ):
        raise SessionFormatError("'frame_size' phải là [width, height] số nguyên dương")

    if data["joint_names"] != MEDIAPIPE_JOINTS:
        raise SessionFormatError("'joint_names' phải đúng 33 tên khớp MediaPipe theo thứ tự")

    if version == 1:
        keypoints, t_ms = _parse_frames(data["frames"])
    else:
        keypoints, t_ms = _parse_packed(data["t_ms"], data["kp_i16"])
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
        notes=notes,
        capture_mode=capture_mode,
    )
    return pose, meta


def load_session_json(path: Path) -> tuple[PoseSequence, SessionMeta]:
    """Đọc file JSON từ trang quay. JSON hỏng cũng báo SessionFormatError."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SessionFormatError(f"không phải JSON hợp lệ: {e}") from None
    return parse_session(data)


def truncate_session(data: dict[str, Any], n_frames: int) -> dict[str, Any]:
    """Bản sao file hiệp (đã qua `parse_session`) chỉ giữ `n_frames` khung đầu, cùng phiên bản.

    Server dùng để lưu keypoint của phần đầu hiệp dài (giới hạn lưu, ARCHITECTURE §4). Các trường
    khác giữ nguyên (sao nông: không sửa `data`). Cần n_frames ≥ 2 (file < 2 khung không hợp lệ).
    """
    if n_frames < 2:
        raise ValueError(f"cần giữ ít nhất 2 khung, nhận {n_frames}")
    out = dict(data)
    if data["format_version"] == 1:
        out["frames"] = data["frames"][:n_frames]
    else:
        n_bytes = n_frames * len(MEDIAPIPE_JOINTS) * 3 * 2
        out["t_ms"] = data["t_ms"][:n_frames]
        out["kp_i16"] = base64.b64encode(base64.b64decode(data["kp_i16"])[:n_bytes]).decode("ascii")
    return out
