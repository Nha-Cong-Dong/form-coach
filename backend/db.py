"""Kết nối Postgres cho backend. Mọi truy vấn của app nằm trong backend/ (file này và các module
gọi nó).

Địa chỉ DB ở biến môi trường `FORMCOACH_DATABASE_URL` (vd
`postgresql://formcoach:formcoach@127.0.0.1:5432/formcoach` cho Postgres Docker ở máy, hoặc
connection string của Neon khi deploy). Đây là bí mật như API key: chỉ ở `.env` / biến môi
trường của server.

Vì sao có pool (giữ sẵn vài kết nối mở): mở một kết nối tới Neon qua internet tốn bắt tay TLS
(~100 ms trở lên); mỗi request mở mới thì trang nào cũng chậm. Pool mở lúc server khởi động
(`open_pool`, sai địa chỉ thì không khởi động), đóng lúc tắt (`close_pool`). Lược đồ
`schema.sql` chạy MỘT lần khi mở pool (idempotent), không phải mỗi request như hồi SQLite.

Đổi địa chỉ DB (test đặt mỗi test một schema riêng) → pool cũ đóng, pool mới mở theo địa chỉ mới.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
POOL_MAX_SIZE = 5  # Render Free 1 instance, ít người dùng; Neon Free cho tới vài trăm kết nối

Connection = psycopg.Connection  # kiểu dùng trong chữ ký hàm của backend/

_pool: ConnectionPool | None = None
_pool_url: str | None = None
_lock = threading.Lock()


def database_url() -> str:
    """Địa chỉ DB; đọc lại biến môi trường mỗi lần để test đổi được. Thiếu → lỗi nói rõ cách sửa."""
    url = os.environ.get("FORMCOACH_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "Chưa đặt FORMCOACH_DATABASE_URL (địa chỉ Postgres). Ở máy: bật Postgres Docker"
            " (docs/plans/postgres-neon.md) rồi thêm dòng này vào .env."
        )
    return url


def init_schema(conn: Connection) -> None:
    """Tạo bảng nếu chưa có. Nhiều câu lệnh trong một lần execute được vì không có tham số."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def connect(url: str | None = None) -> Connection:
    """Một kết nối riêng, không qua pool (công cụ dòng lệnh, test xem DB). Đã tạo bảng.

    `row_factory = dict_row`: đọc cột theo tên (`row["email"]`), như `sqlite3.Row` trước đây.
    Người gọi tự `commit()` / `close()`; `with connect() as c:` thì commit khi xong và đóng.
    """
    conn = psycopg.connect(url or database_url(), row_factory=dict_row)
    init_schema(conn)
    conn.commit()
    return conn


def open_pool() -> ConnectionPool:
    """Mở pool cho địa chỉ hiện tại (đã mở cho đúng địa chỉ đó thì dùng lại) và tạo bảng.

    `check`: trước khi đưa kết nối cho request, thử một câu lệnh rỗng; kết nối đã bị đóng (Neon
    ngủ sau 5 phút không dùng sẽ cắt kết nối) thì pool tự mở kết nối khác, request không lỗi.
    `wait()`: chờ kết nối đầu tiên, sai địa chỉ / sai mật khẩu thì lỗi ngay lúc khởi động.
    """
    global _pool, _pool_url
    url = database_url()
    with _lock:
        if _pool is not None and _pool_url == url:
            return _pool
        if _pool is not None:
            _pool.close()
        pool = ConnectionPool(
            url,
            min_size=1,
            max_size=POOL_MAX_SIZE,
            kwargs={"row_factory": dict_row},
            check=ConnectionPool.check_connection,
            open=True,
        )
        try:
            pool.wait(timeout=30)
            with pool.connection() as conn:
                init_schema(conn)
        except Exception:
            pool.close()
            raise
        _pool, _pool_url = pool, url
        return pool


def close_pool() -> None:
    """Đóng mọi kết nối (server tắt, hoặc test xong một DB)."""
    global _pool, _pool_url
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool, _pool_url = None, None


@contextmanager
def connection() -> Iterator[Connection]:
    """Mượn một kết nối của pool: xong không lỗi thì commit, có exception thì rollback, rồi trả
    kết nối về pool (không đóng)."""
    with open_pool().connection() as conn:
        yield conn


def get_db() -> Iterator[Connection]:
    """Dependency FastAPI: một kết nối cho mỗi request.

    Route chạy xong không lỗi thì commit; có exception (kể cả HTTPException) thì rollback, để
    không bao giờ lưu nửa chừng (vd hàng `sessions` có mà thiếu `reps`).
    """
    with connection() as conn:
        yield conn
