"""Lớp DB (backend/db.py + schema.sql) trên Postgres thật; mỗi test một schema sạch."""

import psycopg
import pytest

from backend.db import Connection, close_pool, connect, database_url, get_db, init_schema, open_pool

NOW = "2026-10-24T00:00:00+00:00"


def _add_user(conn: Connection, email: str = "a@example.com") -> int:
    return conn.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id",
        (email, "scrypt$x", NOW),
    ).fetchone()["id"]


def _add_session(conn: Connection, user_id: int, session_id: str = "s1") -> int:
    return conn.execute(
        "INSERT INTO sessions (user_id, exercise, session_id, set_errors, model_name,"
        " n_frames, duration_s, created_at)"
        " VALUES (%s, 'pushup', %s, '[]', 'rules', 60, 2.0, %s) RETURNING id",
        (user_id, session_id, NOW),
    ).fetchone()["id"]


def _add_rep(conn: Connection, session_pk: int, idx: int = 0) -> None:
    conn.execute(
        "INSERT INTO reps (session_pk, idx, start_frame, end_frame, features_json,"
        " predicted_errors, scores_json) VALUES (%s, %s, 0, 30, '{}', '[]', '{}')",
        (session_pk, idx),
    )


def _count(conn: Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


@pytest.fixture
def conn(pg_database: str):
    c = connect()
    yield c
    c.close()


def test_connect_creates_tables(conn: Connection) -> None:
    names = {
        r["table_name"]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
    }
    assert {"users", "auth_tokens", "sessions", "reps", "goals", "login_failures"} <= names


def test_schema_is_idempotent_and_keeps_data(conn: Connection) -> None:
    _add_user(conn)
    conn.commit()
    init_schema(conn)  # chạy lại schema.sql trên DB đã có bảng
    assert _count(conn, "users") == 1


def test_rows_read_by_column_name(conn: Connection) -> None:
    _add_user(conn, "b@example.com")
    assert conn.execute("SELECT email FROM users").fetchone()["email"] == "b@example.com"


def test_ids_count_up(conn: Connection) -> None:
    assert _add_user(conn, "a@example.com") < _add_user(conn, "b@example.com")


def test_email_unique_ignoring_case(conn: Connection) -> None:
    _add_user(conn, "an@example.com")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _add_user(conn, "An@Example.com")


def test_session_unique_per_exercise_and_id(conn: Connection) -> None:
    uid = _add_user(conn)
    _add_session(conn, uid, "s1")
    _add_session(conn, uid, "s2")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _add_session(conn, uid, "s1")


def test_rep_index_unique_within_session(conn: Connection) -> None:
    pk = _add_session(conn, _add_user(conn))
    _add_rep(conn, pk, 0)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _add_rep(conn, pk, 0)


def test_foreign_keys_are_enforced(conn: Connection) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(
            "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at)"
            " VALUES ('h', 999, %s, %s)",
            (NOW, NOW),
        )


def test_deleting_user_cascades(conn: Connection) -> None:
    uid = _add_user(conn)
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at)"
        " VALUES ('h', %s, %s, %s)",
        (uid, NOW, NOW),
    )
    _add_rep(conn, _add_session(conn, uid))
    conn.execute("DELETE FROM users WHERE id = %s", (uid,))
    for table in ("auth_tokens", "sessions", "reps"):
        assert _count(conn, table) == 0


def test_duration_keeps_double_precision(conn: Connection) -> None:
    # REAL của Postgres chỉ ~7 chữ số; cột phải là DOUBLE PRECISION.
    pk = _add_session(conn, _add_user(conn))
    conn.execute("UPDATE sessions SET duration_s = %s WHERE id = %s", (123.456789012, pk))
    assert conn.execute("SELECT duration_s FROM sessions").fetchone()["duration_s"] == 123.456789012


def test_database_url_missing_is_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORMCOACH_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="FORMCOACH_DATABASE_URL"):
        database_url()


def test_get_db_commits_on_success(pg_database: str) -> None:
    gen = get_db()
    _add_user(next(gen))
    with pytest.raises(StopIteration):
        next(gen)  # route xong bình thường → commit, trả kết nối về pool
    with connect() as c:
        assert _count(c, "users") == 1


def test_get_db_rolls_back_on_error(pg_database: str) -> None:
    gen = get_db()
    _add_user(next(gen))
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("route lỗi"))  # FastAPI ném lỗi của route vào dependency
    with connect() as c:
        assert _count(c, "users") == 0


def test_pool_reused_for_same_url_and_reopened_when_url_changes(
    pg_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = open_pool()
    assert open_pool() is first
    monkeypatch.setenv("FORMCOACH_DATABASE_URL", pg_database + " application_name=khac")
    second = open_pool()
    assert second is not first and first.closed
    close_pool()
    assert second.closed


def test_pool_survives_server_closing_idle_connection(pg_database: str) -> None:
    # Neon ngủ sau 5 phút sẽ cắt kết nối đang mở; request sau vẫn phải chạy.
    pool = open_pool()
    with pool.connection() as c:
        pid = c.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
    with connect() as other:
        other.execute("SELECT pg_terminate_backend(%s)", (pid,))
    gen = get_db()
    assert next(gen).execute("SELECT 1 AS one").fetchone()["one"] == 1
    with pytest.raises(StopIteration):
        next(gen)
