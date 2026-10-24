import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.db import connect, db_path, get_db

NOW = "2026-10-24T00:00:00+00:00"


def _add_user(conn: sqlite3.Connection, email: str = "a@example.com") -> int:
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        (email, "scrypt$x", NOW),
    )
    return int(cur.lastrowid)


def _add_session(conn: sqlite3.Connection, user_id: int, session_id: str = "s1") -> int:
    cur = conn.execute(
        "INSERT INTO sessions (user_id, exercise, session_id, set_errors, model_name,"
        " n_frames, duration_s, created_at) VALUES (?, 'pushup', ?, '[]', 'rules', 60, 2.0, ?)",
        (user_id, session_id, NOW),
    )
    return int(cur.lastrowid)


def _add_rep(conn: sqlite3.Connection, session_pk: int, idx: int = 0) -> None:
    conn.execute(
        "INSERT INTO reps (session_pk, idx, start_frame, end_frame, features_json,"
        " predicted_errors, scores_json) VALUES (?, ?, 0, 30, '{}', '[]', '{}')",
        (session_pk, idx),
    )


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    c = connect(tmp_path / "t.db")
    yield c
    c.close()


def test_connect_creates_file_and_tables(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "t.db"  # thư mục chưa có cũng phải tạo được
    c = connect(path)
    names = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    c.close()
    assert path.exists()
    assert {"users", "auth_tokens", "sessions", "reps"} <= names


def test_schema_is_idempotent_and_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    with connect(path) as c:
        _add_user(c)
    c.close()
    c2 = connect(path)  # chạy lại schema.sql trên DB đã có
    assert c2.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    c2.close()


def test_rows_read_by_column_name(conn: sqlite3.Connection) -> None:
    _add_user(conn, "b@example.com")
    assert conn.execute("SELECT email FROM users").fetchone()["email"] == "b@example.com"


def test_email_is_unique(conn: sqlite3.Connection) -> None:
    _add_user(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _add_user(conn)


def test_session_unique_per_exercise_and_id(conn: sqlite3.Connection) -> None:
    uid = _add_user(conn)
    _add_session(conn, uid, "s1")
    _add_session(conn, uid, "s2")
    with pytest.raises(sqlite3.IntegrityError):
        _add_session(conn, uid, "s1")


def test_rep_index_unique_within_session(conn: sqlite3.Connection) -> None:
    pk = _add_session(conn, _add_user(conn))
    _add_rep(conn, pk, 0)
    with pytest.raises(sqlite3.IntegrityError):
        _add_rep(conn, pk, 0)


def test_foreign_keys_are_enforced(conn: sqlite3.Connection) -> None:
    # SQLite mặc định bỏ qua khoá ngoại; connect() phải bật lên.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at)"
            " VALUES ('h', 999, ?, ?)",
            (NOW, NOW),
        )


def test_deleting_user_cascades(conn: sqlite3.Connection) -> None:
    uid = _add_user(conn)
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at)"
        " VALUES ('h', ?, ?, ?)",
        (uid, NOW, NOW),
    )
    _add_rep(conn, _add_session(conn, uid))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    for table in ("auth_tokens", "sessions", "reps"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_connection_usable_from_another_thread(conn: sqlite3.Connection) -> None:
    # FastAPI có thể mở kết nối ở một thread rồi chạy route ở thread khác.
    errors: list[Exception] = []

    def work() -> None:
        try:
            _add_user(conn)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert errors == []


def test_db_path_follows_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    assert db_path() == tmp_path / "formcoach.db"


def test_get_db_commits_on_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    gen = get_db()
    _add_user(next(gen))
    with pytest.raises(StopIteration):
        next(gen)  # route xong bình thường → commit và đóng
    c = connect(db_path())
    assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    c.close()


def test_get_db_rolls_back_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    gen = get_db()
    _add_user(next(gen))
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("route lỗi"))  # FastAPI ném lỗi của route vào dependency
    c = connect(db_path())
    assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    c.close()
