import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import COOKIE_NAME
from backend.db import connect, db_path
from tests.synthetic import make_session

PW = "mat-khau-dai"


@pytest.fixture
def anon_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client chưa đăng nhập, không override `current_user`; DB và data trong thư mục tạm."""
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.delenv("FORMCOACH_COOKIE_SECURE", raising=False)
    return TestClient(app)


def _register(client: TestClient, email: str = "an@example.com", password: str = PW):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _login(client: TestClient, email: str = "an@example.com", password: str = PW):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# --- đăng ký ---


def test_register_logs_in_immediately(anon_client: TestClient) -> None:
    r = _register(anon_client)
    assert r.status_code == 201
    assert r.json()["email"] == "an@example.com"
    me = anon_client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "an@example.com"


def test_register_disabled_by_default(anon_client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("FORMCOACH_ALLOW_REGISTER")
    assert _register(anon_client).status_code == 403


def test_duplicate_email_is_409_ignoring_case(anon_client: TestClient) -> None:
    assert _register(anon_client, "An@Example.com").status_code == 201
    assert _register(anon_client, "An@Example.com").status_code == 409
    assert _register(anon_client, "an@example.COM").status_code == 409


def test_email_stored_as_typed(anon_client: TestClient) -> None:
    _register(anon_client, "An@Example.com")
    assert anon_client.get("/api/auth/me").json()["email"] == "An@Example.com"


def test_short_password_is_422(anon_client: TestClient) -> None:
    r = _register(anon_client, password="1234567")  # 7 ký tự
    assert r.status_code == 422 and "8" in r.json()["detail"]
    assert _register(anon_client, password="12345678").status_code == 201


@pytest.mark.parametrize(
    "email", ["", "khong-co-a-cong", "@example.com", "an@", "a@b@c", "an @x.com"]
)
def test_bad_email_is_422(anon_client: TestClient, email: str) -> None:
    assert _register(anon_client, email).status_code == 422


# --- đăng nhập ---


def test_login_ignores_email_case(anon_client: TestClient) -> None:
    _register(anon_client, "An@Example.com")
    anon_client.cookies.clear()
    r = _login(anon_client, "an@example.com")
    assert r.status_code == 200
    assert r.json()["email"] == "An@Example.com"  # trả email đúng như lúc đăng ký
    assert anon_client.get("/api/auth/me").status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(anon_client: TestClient) -> None:
    _register(anon_client)
    anon_client.cookies.clear()
    wrong_pw = _login(anon_client, password="sai-mat-khau")
    unknown = _login(anon_client, email="ai-do@example.com")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()  # không lộ email nào đã có tài khoản
    assert anon_client.get("/api/auth/me").status_code == 401


def test_password_is_case_sensitive(anon_client: TestClient) -> None:
    _register(anon_client)
    anon_client.cookies.clear()
    assert _login(anon_client, password=PW.upper()).status_code == 401


# --- phiên đăng nhập ---


def test_no_cookie_is_401(anon_client: TestClient) -> None:
    assert anon_client.get("/api/auth/me").status_code == 401


def test_garbage_token_is_401(anon_client: TestClient) -> None:
    anon_client.cookies.set(COOKIE_NAME, "khong-phai-token")
    assert anon_client.get("/api/auth/me").status_code == 401


def test_logout_invalidates_token(anon_client: TestClient) -> None:
    _register(anon_client)
    token = anon_client.cookies[COOKIE_NAME]
    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/auth/me").status_code == 401
    # Dùng lại token cũ (vd ai đó đã chép được cookie) cũng không được nữa.
    anon_client.cookies.set(COOKIE_NAME, token)
    assert anon_client.get("/api/auth/me").status_code == 401


def test_logout_without_login_is_ok(anon_client: TestClient) -> None:
    assert anon_client.post("/api/auth/logout").status_code == 200


def test_expired_token_is_401(anon_client: TestClient) -> None:
    _register(anon_client)
    conn = connect(db_path())
    with conn:
        conn.execute("UPDATE auth_tokens SET expires_at = '2000-01-01T00:00:00+00:00'")
    conn.close()
    assert anon_client.get("/api/auth/me").status_code == 401


def test_db_stores_token_hash_not_token(anon_client: TestClient) -> None:
    _register(anon_client)
    token = anon_client.cookies[COOKIE_NAME]
    conn = connect(db_path())
    stored = [r["token_hash"] for r in conn.execute("SELECT token_hash FROM auth_tokens")]
    conn.close()
    assert stored == [hashlib.sha256(token.encode()).hexdigest()]


def test_cookie_flags(anon_client: TestClient, monkeypatch) -> None:
    header = _register(anon_client).headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header and "secure" not in header
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "1")
    header = _register(anon_client, "binh@example.com").headers["set-cookie"].lower()
    assert "secure" in header


# --- endpoint được bảo vệ ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/sessions/pushup"),
        ("get", "/api/sessions/pushup/s1/review"),
        ("put", "/api/sessions/pushup/s1/labels"),
        ("post", "/api/sessions"),
    ],
)
def test_protected_endpoints_need_login(anon_client: TestClient, method: str, path: str) -> None:
    kwargs = {"json": make_session()} if method in ("post", "put") else {}
    assert getattr(anon_client, method)(path, **kwargs).status_code == 401


def test_exercise_info_is_open(anon_client: TestClient) -> None:
    assert anon_client.get("/api/exercises/pushup").status_code == 200


def test_upload_works_after_login(anon_client: TestClient) -> None:
    _register(anon_client)
    assert anon_client.post("/api/sessions", json=make_session()).status_code == 201
