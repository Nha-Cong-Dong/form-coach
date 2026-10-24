"""WebSocket /api/live: đếm rep trực tiếp khi đang tập (Track C2). Chỉ để hiển thị, không lưu gì.

Giao thức (JSON, mỗi tin một object):
    client → {"type": "start", "exercise": "pushup", "fps": 30, "frame_size": [1280, 720]}
    server ← {"type": "count", "n_reps": 0, "phase": "waiting_ready"}
    client → {"t_ms": 1234.5, "kp": [[x, y, visibility] × 33]}   (kp = null: không thấy người)
    server ← {"type": "count", ...}  chỉ khi số rep hoặc pha đổi (đỡ tốn băng thông)
    client → {"type": "stop"}
    server ← {"type": "final", "n_reps": 5}, rồi đóng kết nối
Tin sai → {"type": "error", "detail": "..."}, kết nối vẫn mở (một khung hỏng không làm mất hiệp).
Kết quả từng rep vẫn lấy từ `POST /api/sessions` (phân tích cả hiệp) sau khi bấm Xong.

Đăng nhập: kiểm tra cookie phiên TRƯỚC khi chấp nhận kết nối; không hợp lệ → đóng mã 4401
(mã riêng của ứng dụng, 4000–4999; "4401" để nhớ là 401).
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.auth import COOKIE_NAME, user_for_token
from backend.db import connect, db_path
from formcoach.exercises import EXERCISES, get_exercise
from formcoach.features.online import OnlineRepCounter
from formcoach.pose.joints import MEDIAPIPE_JOINTS

router = APIRouter()

UNAUTHORIZED = 4401
N_JOINTS = len(MEDIAPIPE_JOINTS)
MAX_FPS = 120


def _error(detail: str) -> dict[str, Any]:
    return {"type": "error", "detail": detail}


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def parse_keypoints(kp: Any) -> np.ndarray:
    """`kp` của một khung → mảng (33, 3); null → toàn NaN (không thấy người). Sai → ValueError."""
    if kp is None:
        return np.full((N_JOINTS, 3), np.nan)
    if not isinstance(kp, list) or len(kp) != N_JOINTS:
        raise ValueError(f"'kp' phải là danh sách {N_JOINTS} khớp hoặc null")
    for j, point in enumerate(kp):
        if not isinstance(point, list) or len(point) != 3 or not all(map(_is_number, point)):
            raise ValueError(f"khớp {j}: phải là [x, y, visibility] số")
    return np.asarray(kp, dtype=float)


class LiveSession:
    """Một kết nối đếm trực tiếp: nhận tin (đã json.loads), trả các tin cần gửi lại. Không I/O."""

    def __init__(self) -> None:
        self.counter: OnlineRepCounter | None = None
        self.finished = False
        self._last: tuple[int, str] | None = None

    def _count_message(self) -> list[dict[str, Any]]:
        assert self.counter is not None
        state = (self.counter.count, self.counter.phase)
        if state == self._last:
            return []
        self._last = state
        return [{"type": "count", "n_reps": state[0], "phase": state[1]}]

    def _start(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        if self.counter is not None:
            return [_error("đã bắt đầu rồi")]
        exercise, fps, size = msg.get("exercise"), msg.get("fps"), msg.get("frame_size")
        if exercise not in EXERCISES:
            return [_error(f"bài tập không hỗ trợ: {exercise!r}")]
        if not _is_number(fps) or not 0 < fps <= MAX_FPS:
            return [_error(f"'fps' phải là số trong (0, {MAX_FPS}]")]
        if (
            not isinstance(size, list)
            or len(size) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in size)
        ):
            return [_error("'frame_size' phải là [width, height] số nguyên dương")]
        self.counter = OnlineRepCounter(get_exercise(exercise), float(fps), (size[0], size[1]))
        return self._count_message()

    def handle(self, msg: Any) -> list[dict[str, Any]]:
        if self.finished:
            return [_error("hiệp đã kết thúc")]
        if not isinstance(msg, dict):
            return [_error("tin phải là một JSON object")]
        kind = msg.get("type", "frame")
        if kind == "start":
            return self._start(msg)
        if self.counter is None:
            return [_error("gửi 'start' trước")]
        if kind == "stop":
            self.finished = True
            return [{"type": "final", "n_reps": self.counter.finish()}]
        if kind != "frame":
            return [_error(f"loại tin không hỗ trợ: {kind!r}")]
        try:
            kp = parse_keypoints(msg.get("kp"))
        except ValueError as e:
            return [_error(str(e))]
        self.counter.update(kp)
        return self._count_message()


@router.websocket("/api/live")
async def live(websocket: WebSocket) -> None:
    """Đếm rep trực tiếp. Chỉ người đã đăng nhập (cookie phiên, kiểm tra trước khi accept)."""
    conn = connect(db_path())
    try:
        user = user_for_token(conn, websocket.cookies.get(COOKIE_NAME))
    finally:
        conn.close()
    if user is None:
        await websocket.close(code=UNAUTHORIZED)
        return

    await websocket.accept()
    session = LiveSession()
    try:
        while not session.finished:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json(_error("không phải JSON"))
                continue
            for out in session.handle(msg):
                await websocket.send_json(out)
    except WebSocketDisconnect:
        return  # client đóng (vd tắt tab): không có gì để lưu
    await websocket.close()
