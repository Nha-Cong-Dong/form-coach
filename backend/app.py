"""Backend tối giản: nhận file quay từ điện thoại (data/sessions/), phục vụ màn hình gán nhãn
(xem lại một hiệp, lưu nhãn vào data/labels/).

Đăng nhập ở backend/auth.py: mọi endpoint trong router `protected` cần cookie phiên hợp lệ
(401 nếu không); chỉ /api/auth/* và /api/exercises/* mở. Mọi logic nằm trong formcoach/.
Chỉ lắng nghe 127.0.0.1; điện thoại đi qua proxy của Vite dev server (bước 9) nên backend
không lộ ra mạng LAN.

Chạy từ gốc repo (lần đầu cần bật đăng ký để tạo tài khoản):
    FORMCOACH_ALLOW_REGISTER=1 uvicorn backend.app:app --port 8000
Rồi mở http://127.0.0.1:8000/docs để xem và thử các endpoint.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException

from backend import auth, results
from backend.db import get_db
from formcoach.exercises import EXERCISES, get_exercise
from formcoach.labels import LabelFormatError, check_alignment, from_dict, load_labels, save_labels
from formcoach.pipeline import analyze, classify_session
from formcoach.pose.session_json import (
    SESSION_ID_RE,
    SessionFormatError,
    load_session_json,
    parse_session,
)
from formcoach.progress.summary import summarize
from formcoach.review import build_review

app = FastAPI(title="Form Coach", version="0.1.0")
app.include_router(auth.router)
# Endpoint thêm vào router này tự động cần đăng nhập (không phải nhớ gắn từng route).
protected = APIRouter(dependencies=[Depends(auth.current_user)])
Db = Annotated[sqlite3.Connection, Depends(get_db)]
CurrentUser = Annotated[auth.User, Depends(auth.current_user)]


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
    return {
        "name": exercise.name,
        "error_labels": list(exercise.error_labels),
        "error_display": {e: exercise.error_display.get(e, e) for e in exercise.error_labels},
    }


@protected.post("/api/sessions", status_code=201)
def upload_session(
    db: Db,
    user: CurrentUser,
    payload: dict[str, Any] = Body(...),  # noqa: B008
) -> dict[str, Any]:
    """Kiểm tra file quay theo ARCHITECTURE §2b, phân loại từng rep, lưu file + kết quả.

    File lưu nguyên văn (dữ liệu huấn luyện); kết quả vào DB gắn với người tải lên. Thứ tự: phân
    loại và ghi DB (chưa commit) → ghi file → commit, để lỗi ở bước nào cũng không để lại kết
    quả mà không có file. 422: sai định dạng (nói rõ sai ở đâu). 409: session_id đã tồn tại.
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

    t = meta.timestamps_ms
    n_frames = int(len(t))
    duration_s = round(float(t[-1] - t[0]) / 1000, 2)
    exercise = get_exercise(meta.exercise)
    classifier, model_name = results.get_classifier(exercise, data_dir())
    session = classify_session(pose, exercise, classifier, meta.session_id)
    try:
        results.store_result(db, user.id, meta, session, model_name, n_frames, duration_s)
    except sqlite3.IntegrityError:  # đã có kết quả (file bị xoá tay): như trùng file
        raise HTTPException(
            status_code=409, detail=f"session {meta.session_id} đã tồn tại"
        ) from None

    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    db.commit()

    return {
        "session_id": meta.session_id,
        "exercise": meta.exercise,
        "n_frames": n_frames,
        "duration_s": duration_s,
        "fps": round(pose.fps, 2),
        "frames_with_person": int(np.isfinite(pose.keypoints[:, 0, 0]).sum()),
        # Trường cộng thêm (B5): trang quay cũ chỉ đọc các trường ở trên nên không vỡ.
        "model_name": model_name,
        "reps": [results.rep_json(r) for r in session.results],
        "summary": summarize(session, exercise.error_labels),
    }


@protected.get("/api/sessions/{exercise}/{session_id}/result")
def session_result(exercise: str, session_id: str, db: Db, user: CurrentUser) -> dict[str, Any]:
    """Kết quả một hiệp của chính mình. Hiệp của người khác hoặc quay trước khi có DB → 404."""
    found = results.load_result(db, user.id, exercise, session_id)
    if found is None:
        raise HTTPException(status_code=404, detail="không có kết quả cho hiệp này")
    return found


@protected.get("/api/results")
def my_results(db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    """Lịch sử các hiệp của mình, mới nhất trước."""
    return results.list_results(db, user.id)


def _session_path(exercise: str, session_id: str) -> Path:
    """File của một hiệp; bài lạ, id có ký tự lạ hoặc file không có → 404."""
    if exercise not in EXERCISES or not SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=404, detail="không có hiệp này")
    path = data_dir() / "sessions" / exercise / f"{session_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"không có hiệp {session_id}")
    return path


def _load(exercise: str, session_id: str):
    try:
        return load_session_json(_session_path(exercise, session_id))
    except SessionFormatError as e:
        raise HTTPException(status_code=422, detail=f"file hiệp hỏng: {e}") from None


@protected.get("/api/sessions/{exercise}")
def list_sessions(exercise: str) -> list[dict[str, Any]]:
    """Các hiệp đã quay của một bài, mới nhất trước. File hỏng vẫn hiện, kèm lỗi."""
    if exercise not in EXERCISES:
        raise HTTPException(status_code=404, detail=f"bài tập {exercise!r} không hỗ trợ")
    folder = data_dir() / "sessions" / exercise
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json"), reverse=True):
        session_id = path.stem
        try:
            pose, meta = load_session_json(path)
            _, reps = analyze(pose, get_exercise(exercise))
            labels = load_labels(data_dir(), exercise, session_id)
            t = meta.timestamps_ms
            items.append(
                {
                    "session_id": session_id,
                    "recorded_at": meta.recorded_at,
                    "set_errors": sorted(meta.set_errors),
                    "notes": meta.notes,
                    "capture_mode": meta.capture_mode,
                    "duration_s": round(float(t[-1] - t[0]) / 1000, 1),
                    "n_reps": len(reps),
                    "labeled": labels is not None,
                }
            )
        except (SessionFormatError, LabelFormatError) as e:
            items.append({"session_id": session_id, "error": str(e)})
    return items


@protected.get("/api/sessions/{exercise}/{session_id}/review")
def review_session(exercise: str, session_id: str) -> dict[str, Any]:
    """Dữ liệu cho màn hình gán nhãn: thời gian, góc, khung xương rút gọn, rep, nhãn."""
    pose, meta = _load(exercise, session_id)
    try:
        saved = load_labels(data_dir(), exercise, session_id)
    except LabelFormatError as e:
        raise HTTPException(status_code=422, detail=f"file nhãn hỏng: {e}") from None
    return build_review(pose, meta, get_exercise(exercise), saved)


@protected.put("/api/sessions/{exercise}/{session_id}/labels")
def put_labels(
    exercise: str,
    session_id: str,
    payload: dict[str, Any] = Body(...),  # noqa: B008
) -> dict[str, Any]:
    """Lưu nhãn của một hiệp. 422: nhãn sai; 409: nhãn không khớp rep hiện tại của hiệp."""
    pose, meta = _load(exercise, session_id)
    try:
        labels = from_dict(payload)
    except LabelFormatError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    if (labels.exercise, labels.session_id) != (exercise, session_id):
        raise HTTPException(status_code=422, detail="nhãn thuộc hiệp khác với đường dẫn")

    _, reps = analyze(pose, get_exercise(exercise))
    times = (meta.timestamps_ms - meta.timestamps_ms[0]) / 1000.0
    problems = check_alignment(labels, reps, times)
    if problems:
        raise HTTPException(status_code=409, detail="; ".join(problems))

    save_labels(labels, data_dir())
    return {"session_id": session_id, "n_reps": len(labels.reps), "saved": True}


# Phải gọi SAU khi khai báo route: include_router chép các route đang có tại thời điểm gọi.
app.include_router(protected)
