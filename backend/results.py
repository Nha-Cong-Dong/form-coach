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


def _from_json(text: str) -> dict[str, float]:
    """Đặc trưng đã lưu: null (NaN lúc lưu) → NaN lại."""
    return {k: (float("nan") if v is None else v) for k, v in json.loads(text).items()}


def rep_json(result: RepResult, exercise: Exercise) -> dict[str, Any]:
    """Một rep cho web: lỗi đoán được, điểm, và số đo hiện cho người dùng (`measure_display`)."""
    rep = result.rep
    shown = _finite({f: rep.features.get(f, float("nan")) for f in exercise.measure_display})
    return {
        "index": rep.index,
        "start_frame": rep.start_frame,
        "end_frame": rep.end_frame,
        "errors": sorted(result.errors),
        "scores": result.scores,
        "measures": shown,
    }


def measures_json(exercise: Exercise) -> list[dict[str, Any]]:
    """Số đo hiện ở trang kết quả, kèm mục tiêu lấy từ luật của lỗi dùng số đo đó.

    Lỗi khi `giá trị <op> ngưỡng` (vd shallow: góc khuỷu ở đáy > 67°), nên mục tiêu là phía
    ngược lại. Chỉ là mốc tham khảo: rep có lỗi hay không vẫn do bộ phân loại quyết định.
    """
    out = []
    for error, rule in exercise.error_rules().items():
        if rule is None or rule.feature not in exercise.measure_display:
            continue
        label, unit = exercise.measure_display[rule.feature]
        out.append(
            {
                "error": error,
                "feature": rule.feature,
                "label": label,
                "unit": unit,
                "op": rule.op,
                "threshold": rule.threshold,
            }
        )
    return out


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
) -> tuple[dict[str, Any], Session] | None:
    """(JSON kết quả, Session) một hiệp của chính user; không có (hoặc của người khác) → None.

    Trả kèm `Session` để route dựng nhận xét coach (ở backend/progress.py) mà không đọc lại DB.
    """
    row = db.execute(
        "SELECT * FROM sessions WHERE user_id = ? AND exercise = ? AND session_id = ?",
        (user_id, exercise, session_id),
    ).fetchone()
    if row is None:
        return None
    ex = get_exercise(exercise)
    results = [
        RepResult(
            Rep(r["idx"], r["start_frame"], r["end_frame"], _from_json(r["features_json"])),
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
        "reps": [rep_json(r, ex) for r in results],
        "summary": summarize(session, ex.error_labels),
        "measures": measures_json(ex),
    }, session


def rep_frames(
    db: sqlite3.Connection, user_id: int, exercise: str, session_id: str, index: int
) -> tuple[int, int] | None:
    """(khung đầu, khung cuối) của rep đã lưu, chỉ khi hiệp là của user; không có → None."""
    row = db.execute(
        "SELECT r.start_frame, r.end_frame FROM reps r JOIN sessions s ON s.id = r.session_pk"
        " WHERE s.user_id = ? AND s.exercise = ? AND s.session_id = ? AND r.idx = ?",
        (user_id, exercise, session_id, index),
    ).fetchone()
    return None if row is None else (row["start_frame"], row["end_frame"])


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
