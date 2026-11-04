"""Tải file mô hình đã train (`python -m formcoach train`) lên bảng `models` của DB (P3, deploy).

Server trên Render Free không giữ file, nên mô hình nằm trong DB; server đọc nó lúc khởi động khi
không đặt `FORMCOACH_MODEL_PATH`. Kiểm tra file TRƯỚC khi tải (đúng định dạng, đúng bài, cùng bản
scikit-learn với máy này = bản trong requirements.txt mà server cài), để không đẩy file hỏng lên.
Tải lại thì ghi đè mô hình cũ của bài đó. Server đang chạy dùng mô hình mới từ lần khởi động sau.

DB đích là `FORMCOACH_DATABASE_URL` trong terminal. Tải lên Neon (deploy) thì đặt biến bằng
connection string của Neon chỉ cho lệnh này:

    python -m tools.upload_model models/pushup-rf.pkl                 # DB ở máy (.env)
    FORMCOACH_DATABASE_URL='<neon>' python -m tools.upload_model models/pushup-rf.pkl
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

from backend.db import Connection, connect, database_url
from formcoach.exercises import EXERCISES
from formcoach.models.store import ModelFileError, ModelInfo, load_model


def upload(conn: Connection, path: Path, exercise: str) -> ModelInfo:
    """Kiểm tra file rồi ghi vào `models` (ghi đè bài đã có). Chưa commit: người gọi commit.
    File không dùng được → ModelFileError, không ghi gì."""
    _, info = load_model(path, exercise)
    conn.execute(
        "INSERT INTO models (exercise, data, model_name, trained_at, uploaded_at)"
        " VALUES (%s, %s, %s, %s, %s)"
        " ON CONFLICT (exercise) DO UPDATE SET data = excluded.data,"
        " model_name = excluded.model_name, trained_at = excluded.trained_at,"
        " uploaded_at = excluded.uploaded_at",
        (exercise, path.read_bytes(), info.model_name, info.trained_at, _now()),
    )
    return info


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _where(url: str) -> str:
    """Máy chủ DB để in ra cho người dùng biết đang tải lên đâu; KHÔNG in mật khẩu."""
    parts = conninfo_to_dict(url)
    return f"{parts.get('host', '?')}/{parts.get('dbname', '?')}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tải file mô hình lên bảng models của DB.")
    parser.add_argument("path", type=Path, help="file .pkl do `python -m formcoach train` lưu")
    parser.add_argument("--exercise", default="pushup", choices=sorted(EXERCISES))
    args = parser.parse_args(argv)
    try:
        url = database_url()
        with connect(url) as conn:  # `with`: commit khi xong, rollback nếu lỗi
            info = upload(conn, args.path, args.exercise)
    except (ModelFileError, RuntimeError) as e:
        print(f"Không tải lên: {e}", file=sys.stderr)
        return 1
    size_kb = args.path.stat().st_size / 1024
    print(
        f"Đã tải mô hình {args.exercise} lên {_where(url)}: {info.model_name}, train"
        f" {info.trained_at}, {info.n_reps} rep, {size_kb:.0f} kB."
        " Khởi động lại server để dùng mô hình mới."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
