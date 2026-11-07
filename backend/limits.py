"""Giới hạn tải hiệp lên và lưu keypoint, để bản deploy miễn phí không hết RAM hay đầy DB.

Con số do bạn chốt 2026-11-07 (ARCHITECTURE §4):
- Mỗi hiệp tối đa 30 phút; dữ liệu gửi lên tối đa 20 MB (kiểm tra TRƯỚC khi đọc JSON: đọc JSON
  mới là bước tốn RAM). Quá → 413.
- Keypoint (để xem lại rep) chỉ lưu 10 phút đầu mỗi hiệp, và mỗi người tối đa 30 phút trong 24 giờ
  trượt. Quá thì hiệp vẫn được chấm và lưu kết quả, chỉ không lưu (phần sau của) keypoint.

"24 giờ" tính theo `sessions.created_at` (giờ server lúc nhận, lưu trong DB): server ngủ hay khởi
động lại không ảnh hưởng, và người dùng không lách được bằng cách đổi giờ điện thoại.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from backend.db import Connection

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # hiệp v2 30 phút ở 30 fps ~15 MB
MAX_SESSION_S = 30 * 60
KEEP_PAYLOAD_S = 10 * 60
DAILY_PAYLOAD_S = 30 * 60
WINDOW = timedelta(hours=24)

TOO_LARGE = 413


def _too_large(detail: str) -> HTTPException:
    return HTTPException(status_code=TOO_LARGE, detail=detail)


async def session_body(request: Request) -> Any:
    """Đọc body JSON của `POST /api/sessions`, dừng ngay khi quá MAX_UPLOAD_BYTES.

    Thay cho `Body(...)` của FastAPI (đọc hết rồi mới parse, không giới hạn cỡ). Đọc theo từng
    khúc nên cả khi thiếu header Content-Length (hoặc header nói dối) cũng không nhận quá giới hạn.
    """
    limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
    message = f"dữ liệu hiệp quá lớn (tối đa {limit_mb} MB, khoảng {MAX_SESSION_S // 60} phút)"
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise _too_large(message)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise _too_large(message)
        chunks.append(chunk)
    try:
        # JSON vài MB mất vài chục ms: chạy ngoài vòng sự kiện để không chặn request khác.
        return await run_in_threadpool(json.loads, b"".join(chunks))
    except ValueError:
        raise HTTPException(status_code=422, detail="nội dung không phải JSON hợp lệ") from None


def check_duration(duration_s: float) -> None:
    """Hiệp dài hơn MAX_SESSION_S → 413 (dù cỡ dữ liệu chưa vượt, vd fps thấp)."""
    if duration_s > MAX_SESSION_S:
        raise _too_large(
            f"hiệp dài {_minutes(duration_s)}, tối đa {_minutes(MAX_SESSION_S)} mỗi hiệp"
        )


def _minutes(seconds: float) -> str:
    """90.4 → "1 phút 30 giây"; làm tròn xuống giây (30 phút 20 giây không thành "30 phút")."""
    m, s = divmod(int(seconds), 60)
    parts = [f"{m} phút"] if m else []
    if s or not m:
        parts.append(f"{s} giây")
    return " ".join(parts)


def used_payload_s(db: Connection, user_id: int, now: datetime) -> float:
    """Số giây keypoint user đã được lưu trong 24 giờ trước `now` (hiệp cũ NULL = lưu đủ)."""
    row = db.execute(
        "SELECT COALESCE(SUM(COALESCE(replay_s, duration_s)), 0) AS used FROM sessions"
        " WHERE user_id = %s AND created_at >= %s",
        (user_id, (now - WINDOW).isoformat()),
    ).fetchone()
    return float(row["used"])


def payload_budget_s(used_s: float) -> float:
    """Số giây keypoint được lưu cho hiệp mới: min(10 phút, phần còn lại của 24 giờ)."""
    return max(0.0, min(KEEP_PAYLOAD_S, DAILY_PAYLOAD_S - used_s))


def payload_frames(t_ms: Sequence[float] | np.ndarray, budget_s: float) -> int:
    """Số khung đầu nằm trong `budget_s` giây đầu hiệp; < 2 → 0 (không lưu: 1 khung vô nghĩa)."""
    t = np.asarray(t_ms, dtype=float)
    n = int(np.searchsorted(t - t[0], budget_s * 1000, side="right"))
    return n if n >= 2 else 0
