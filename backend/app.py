"""Backend tối giản tuần 1: nhận file quay từ điện thoại và lưu vào data/sessions/.

Chưa có database, đăng nhập hay chạy pipeline (tuần 3). Chỉ lắng nghe 127.0.0.1;
điện thoại đi qua proxy của Vite dev server (bước 9) nên backend không lộ ra mạng LAN.

Chạy từ gốc repo:
    uvicorn backend.app:app --port 8000
Rồi mở http://127.0.0.1:8000/docs để xem và thử các endpoint.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import Body, FastAPI, HTTPException

from formcoach.exercises import get_exercise
from formcoach.pose.session_json import SessionFormatError, parse_session

app = FastAPI(title="Form Coach", version="0.1.0")


def data_dir() -> Path:
    """Thư mục dữ liệu; đọc lại mỗi request để test đổi được qua biến môi trường."""
    return Path(os.environ.get("FORMCOACH_DATA_DIR", "data"))


@app.get("/api/exercises/{name}")
def exercise_info(name: str) -> dict[str, Any]:
    """Tên bài và danh sách lỗi hợp lệ, để trang quay không tự chép danh sách lỗi."""
    try:
        exercise = get_exercise(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None
    return {"name": exercise.name, "error_labels": list(exercise.error_labels)}


@app.post("/api/sessions", status_code=201)
def upload_session(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
    """Kiểm tra file quay theo ARCHITECTURE §2b rồi lưu nguyên văn.

    422: sai định dạng (thông báo nói rõ sai ở đâu). 409: session_id đã tồn tại.
    """
    try:
        pose, meta = parse_session(payload)
    except SessionFormatError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    folder = (data_dir() / "sessions" / meta.exercise).resolve()
    path = (folder / f"{meta.session_id}.json").resolve()
    # parse_session đã chặn ký tự lạ trong session_id; kiểm tra thêm lần nữa cho chắc.
    if path.parent != folder:
        raise HTTPException(status_code=422, detail="session_id không hợp lệ")
    if path.exists():
        raise HTTPException(status_code=409, detail=f"session {meta.session_id} đã tồn tại")

    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    t = meta.timestamps_ms
    return {
        "session_id": meta.session_id,
        "exercise": meta.exercise,
        "n_frames": int(len(t)),
        "duration_s": round(float(t[-1] - t[0]) / 1000, 2),
        "fps": round(pose.fps, 2),
        "frames_with_person": int(np.isfinite(pose.keypoints[:, 0, 0]).sum()),
    }
