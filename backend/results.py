"""Kết quả tập luyện của người dùng: chọn bộ phân loại, lưu/đọc bảng `sessions` + `reps`.

Mọi truy vấn kết quả nằm ở đây (cùng `db.py`, `auth.py`) để đổi DB chỉ sửa trong `backend/`.
Kết quả luôn gắn `user_id`: người khác hỏi hiệp không phải của mình → không thấy (404).

Bộ phân loại theo `FORMCOACH_MODEL` (`rules` | `stump` | `rf`, mặc định `rf`), huấn luyện LẦN ĐẦU
cần tới từ dữ liệu đã gán nhãn trong `data/` rồi giữ trong bộ nhớ. Nhãn mới gán sau đó chỉ được
dùng khi khởi động lại server. Không huấn luyện được (server không có `data/`) → lùi về luật.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from formcoach.dataset import build_dataset
from formcoach.exercises import get_exercise
from formcoach.exercises.base import Exercise
from formcoach.models.base import FormClassifier
from formcoach.models.train import train_classifier
from formcoach.pose.session_json import SessionMeta
from formcoach.progress.summary import summarize
from formcoach.types import Rep, RepResult, Session

DEFAULT_MODEL = "rf"

_cache: dict[tuple[str, str, str], tuple[FormClassifier, str]] = {}
_lock = threading.Lock()  # hai request đầu tiên cùng lúc: chỉ huấn luyện một lần


def get_classifier(exercise: Exercise, data_dir: Path) -> tuple[FormClassifier, str]:
    """(bộ phân loại đã fit, tên mô hình thật sự dùng). Tên lạ trong env → ValueError."""
    name = os.environ.get("FORMCOACH_MODEL", DEFAULT_MODEL)
    key = (name, exercise.name, str(data_dir))
    with _lock:
        if key not in _cache:
            dataset = None if name == "rules" else build_dataset(data_dir, exercise.name)
            _cache[key] = train_classifier(name, exercise, dataset)
        return _cache[key]


def _finite(features: dict[str, float]) -> dict[str, float | None]:
    """NaN/inf → None: JSON chuẩn (và JavaScript) không đọc được NaN."""
    return {k: (v if math.isfinite(v) else None) for k, v in features.items()}


def rep_json(result: RepResult) -> dict[str, Any]:
    rep = result.rep
    return {
        "index": rep.index,
        "start_frame": rep.start_frame,
        "end_frame": rep.end_frame,
        "errors": sorted(result.errors),
        "scores": result.scores,
    }


def store_result(
    db: sqlite3.Connection,
    user_id: int,
    meta: SessionMeta,
    session: Session,
    model_name: str,
    n_frames: int,
    duration_s: float,
) -> None:
    """Ghi một hiệp + các rep vào DB (chưa commit: route commit sau khi đã ghi file)."""
    cur = db.execute(
        "INSERT INTO sessions (user_id, exercise, session_id, recorded_at, set_errors, source,"
        " model_name, n_frames, duration_s, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            session.exercise,
            session.session_id,
            meta.recorded_at,
            json.dumps(sorted(meta.set_errors)),
            json.dumps(meta.source, ensure_ascii=False),
            model_name,
            n_frames,
            duration_s,
            datetime.now(UTC).isoformat(),
        ),
    )
    session_pk = cur.lastrowid
    db.executemany(
        "INSERT INTO reps (session_pk, idx, start_frame, end_frame, features_json,"
        " predicted_errors, scores_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                session_pk,
                r.rep.index,
                r.rep.start_frame,
                r.rep.end_frame,
                json.dumps(_finite(r.rep.features)),
                json.dumps(sorted(r.errors)),
                json.dumps(r.scores or {}),
            )
            for r in session.results
        ],
    )


def load_result(
    db: sqlite3.Connection, user_id: int, exercise: str, session_id: str
) -> dict[str, Any] | None:
    """Kết quả một hiệp của chính user; không có (hoặc của người khác) → None."""
    row = db.execute(
        "SELECT * FROM sessions WHERE user_id = ? AND exercise = ? AND session_id = ?",
        (user_id, exercise, session_id),
    ).fetchone()
    if row is None:
        return None
    results = [
        RepResult(
            Rep(r["idx"], r["start_frame"], r["end_frame"], json.loads(r["features_json"])),
            frozenset(json.loads(r["predicted_errors"])),
            json.loads(r["scores_json"]) or None,
        )
        for r in db.execute(
            "SELECT * FROM reps WHERE session_pk = ? ORDER BY idx", (row["id"],)
        ).fetchall()
    ]
    session = Session(session_id, exercise, results)
    return {
        "session_id": session_id,
        "exercise": exercise,
        "recorded_at": row["recorded_at"],
        "set_errors": json.loads(row["set_errors"]),
        "model_name": row["model_name"],
        "n_frames": row["n_frames"],
        "duration_s": row["duration_s"],
        "reps": [rep_json(r) for r in results],
        "summary": summarize(session, get_exercise(exercise).error_labels),
    }


def list_results(db: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    """Lịch sử của user, mới nhất trước. Rep tốt = `predicted_errors` là danh sách rỗng."""
    rows = db.execute(
        "SELECT s.exercise, s.session_id, s.recorded_at, s.duration_s, s.model_name,"
        " COUNT(r.id) AS n_reps,"
        " COALESCE(SUM(CASE WHEN r.predicted_errors = '[]' THEN 1 ELSE 0 END), 0) AS n_good"
        " FROM sessions s LEFT JOIN reps r ON r.session_pk = s.id"
        " WHERE s.user_id = ? GROUP BY s.id ORDER BY s.recorded_at DESC, s.id DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]
