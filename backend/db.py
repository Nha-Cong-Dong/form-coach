"""Kết nối SQLite cho backend. Mọi truy vấn của app nằm trong backend/ (file này và các module
gọi nó), để sau này đổi sang Postgres/MySQL chỉ phải sửa một chỗ.

DB nằm ở $FORMCOACH_DATA_DIR/formcoach.db (mặc định data/formcoach.db). Mỗi request mở một kết
nối riêng rồi đóng (dependency `get_db`); lược đồ `schema.sql` chạy mỗi lần mở, idempotent.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def db_path() -> Path:
    """Đường dẫn file DB; đọc lại biến môi trường mỗi lần để test đổi được (giống `data_dir`)."""
    return Path(os.environ.get("FORMCOACH_DATA_DIR", "data")) / "formcoach.db"


def connect(path: Path) -> sqlite3.Connection:
    """Mở DB (tạo file và bảng nếu chưa có).

    - `foreign_keys = ON`: SQLite mặc định KHÔNG kiểm tra khoá ngoại, phải bật mỗi kết nối.
    - WAL: đang có lệnh ghi thì request khác vẫn đọc được. Chế độ này lưu luôn trong file DB.
    - `check_same_thread=False`: FastAPI có thể chạy dependency và hàm route ở hai thread khác
      nhau; an toàn vì mỗi request có kết nối riêng và dùng tuần tự.
    - `row_factory = sqlite3.Row`: đọc cột theo tên (`row["email"]`).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """Dependency FastAPI: một kết nối cho mỗi request.

    Route chạy xong không lỗi thì commit; có exception (kể cả HTTPException) thì rollback, để
    không bao giờ lưu nửa chừng (vd hàng `sessions` có mà thiếu `reps`).
    """
    conn = connect(db_path())
    try:
        with conn:  # `with` của sqlite3: commit khi thoát bình thường, rollback khi có lỗi
            yield conn
    finally:
        conn.close()
