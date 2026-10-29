import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.app import app
from backend.auth import COOKIE_NAME, LOGIN_LOCKOUT, LOGIN_WINDOW, lockout_end
from backend.db import connect, db_path
from tests.synthetic import make_session, train_session

PW = "mat-khau-dai"


@pytest.fixture
def anon_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client chưa đăng nhập, không override `current_user`; DB và data trong thư mục tạm."""
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    # TestClient chạy qua http://testserver: cookie Secure sẽ không được gửi lại, nên tắt.
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
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


def test_options_report_register_switch(anon_client: TestClient, monkeypatch) -> None:
    # Mở không cần đăng nhập, theo đúng biến môi trường.
    assert anon_client.get("/api/auth/options").json() == {"allow_register": True}
    monkeypatch.delenv("FORMCOACH_ALLOW_REGISTER")
    assert anon_client.get("/api/auth/options").json() == {"allow_register": False}


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
    "email",
    [
        "",
        "khong-co-a-cong",
        "@example.com",
        "an@",
        "a@b@c",
        "an @x.com",
        "an@x",
        "an@x.",
        "an@.com",
    ],
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
    # Mặc định (không đặt biến) là Secure.
    monkeypatch.delenv("FORMCOACH_COOKIE_SECURE")
    header = _register(anon_client, "binh@example.com").headers["set-cookie"].lower()
    assert "secure" in header


@pytest.mark.parametrize("route", ["login", "register"])
def test_huge_password_is_422_without_hashing(anon_client: TestClient, route: str) -> None:
    body = {"email": "an@example.com", "password": "x" * 1025}
    assert anon_client.post(f"/api/auth/{route}", json=body).status_code == 422
    body["email"] = "a" * 250 + "@x.com"
    body["password"] = PW
    assert anon_client.post(f"/api/auth/{route}", json=body).status_code == 422


def test_login_removes_expired_tokens(anon_client: TestClient) -> None:
    _register(anon_client)
    conn = connect(db_path())
    with conn:
        conn.execute("UPDATE auth_tokens SET expires_at = '2000-01-01T00:00:00+00:00'")
    conn.close()
    anon_client.cookies.clear()
    assert _login(anon_client).status_code == 200
    conn = connect(db_path())
    rows = conn.execute("SELECT expires_at FROM auth_tokens").fetchall()
    conn.close()
    assert len(rows) == 1 and not rows[0]["expires_at"].startswith("2000")


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
    assert anon_client.post("/api/sessions", json=train_session()).status_code == 201


# --- admin (FORMCOACH_ADMIN_EMAILS) ---

DATA_TOOLS = [
    ("get", "/api/sessions/pushup"),
    ("get", "/api/sessions/pushup/s1/review"),
    ("put", "/api/sessions/pushup/s1/labels"),
]


@pytest.mark.parametrize(("method", "path"), DATA_TOOLS)
def test_data_tools_are_403_for_non_admin(
    anon_client: TestClient, monkeypatch, method: str, path: str
) -> None:
    monkeypatch.setenv("FORMCOACH_ADMIN_EMAILS", "admin@example.com")
    _register(anon_client)  # an@example.com: không có trong danh sách
    kwargs = {"json": {}} if method == "put" else {}
    assert getattr(anon_client, method)(path, **kwargs).status_code == 403


def test_admin_list_ignores_case_and_spaces(anon_client: TestClient, monkeypatch) -> None:
    # Biến gõ tay khi deploy: chấp nhận khoảng trắng và hoa thường khác email đã đăng ký.
    monkeypatch.setenv("FORMCOACH_ADMIN_EMAILS", " khac@example.com , AN@Example.com ")
    assert _register(anon_client).json()["is_admin"] is True
    assert _login(anon_client).json()["is_admin"] is True
    assert anon_client.get("/api/auth/me").json()["is_admin"] is True
    assert anon_client.get("/api/sessions/pushup").status_code == 200


def test_no_admin_by_default(anon_client: TestClient) -> None:
    assert _register(anon_client).json()["is_admin"] is False
    assert _login(anon_client).json()["is_admin"] is False
    assert anon_client.get("/api/auth/me").json()["is_admin"] is False
    assert anon_client.get("/api/sessions/pushup").status_code == 403


def test_dataset_upload_is_admin_only(anon_client: TestClient, monkeypatch) -> None:
    # Hiệp Quay dữ liệu (cả file cũ không ghi capture_mode) là dữ liệu train: người thường 403,
    # không ghi file. Hiệp Tập ("train") thì ai cũng gửi được.
    monkeypatch.setenv("FORMCOACH_ADMIN_EMAILS", "admin@example.com")
    _register(anon_client)
    dataset = make_session()
    assert anon_client.post("/api/sessions", json=dataset).status_code == 403
    assert not list(Path(os.environ["FORMCOACH_DATA_DIR"]).glob("sessions/**/*.json"))
    _register(anon_client, "admin@example.com")  # đăng ký = đăng nhập bằng tài khoản admin
    assert anon_client.post("/api/sessions", json=dataset).status_code == 201


# --- giới hạn đăng nhập sai (D0b): 10 lần / 5 phút → khoá 15 phút ---

T0 = datetime(2026, 10, 29, 8, 0, tzinfo=UTC)


def _times(*seconds: float) -> list[datetime]:
    return [T0 + timedelta(seconds=s) for s in seconds]


def test_lockout_needs_ten_failures_within_window() -> None:
    assert lockout_end(_times(*range(9))) is None  # 9 lần: chưa khoá
    ten = _times(*range(10))
    assert lockout_end(ten) == ten[-1] + LOGIN_LOCKOUT  # khoá tính từ lần thứ 10
    # 10 lần nhưng trải dài hơn 5 phút (cách nhau 40 s → 6 phút): không khoá
    assert lockout_end(_times(*range(0, 400, 40))) is None
    # Đúng bằng 5 phút vẫn tính là trong cửa sổ
    edge = _times(*range(9), LOGIN_WINDOW.total_seconds())  # lần 1 lúc 0 s, lần 10 lúc 300 s
    assert lockout_end(edge) == T0 + LOGIN_WINDOW + LOGIN_LOCKOUT


def test_lockout_uses_latest_qualifying_run() -> None:
    # Hai đợt 10 lần: hết khoá theo đợt sau.
    first = _times(*range(10))
    second = _times(*range(2000, 2010))
    assert lockout_end(first + second) == second[-1] + LOGIN_LOCKOUT


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    """Đồng hồ giả cho backend.auth: test đổi now[0] để "tua" thời gian, không phải đợi thật."""
    now = [T0]
    monkeypatch.setattr(auth, "_now", lambda: now[0])
    return now


def test_ten_wrong_passwords_lock_even_correct_one(anon_client: TestClient, clock) -> None:
    _register(anon_client)
    for _ in range(10):
        assert _login(anon_client, password="sai-mat-khau").status_code == 401
        clock[0] += timedelta(seconds=5)
    r = _login(anon_client)  # mật khẩu đúng nhưng đang khoá
    assert r.status_code == 429
    retry = int(r.headers["Retry-After"])
    assert 0 < retry <= LOGIN_LOCKOUT.total_seconds()
    # Đang khoá thì thử thêm không kéo dài thời gian khoá.
    _login(anon_client, password="sai-mat-khau")
    clock[0] += LOGIN_LOCKOUT
    assert _login(anon_client).status_code == 200


def test_lock_applies_to_unknown_email_and_ignores_case(anon_client: TestClient, clock) -> None:
    # Email chưa đăng ký cũng bị khoá như email có thật: không dò được email nào tồn tại.
    for _ in range(10):
        assert _login(anon_client, "Khong-Co@Example.com").status_code == 401
    assert _login(anon_client, "khong-co@example.com").status_code == 429


def test_lock_is_per_email(anon_client: TestClient, clock) -> None:
    _register(anon_client, "an@example.com")
    _register(anon_client, "binh@example.com")
    for _ in range(10):
        _login(anon_client, "an@example.com", "sai-mat-khau")
    assert _login(anon_client, "an@example.com").status_code == 429
    assert _login(anon_client, "binh@example.com").status_code == 200


def test_success_resets_failures(anon_client: TestClient, clock) -> None:
    _register(anon_client)
    for _ in range(9):
        _login(anon_client, password="sai-mat-khau")
    assert _login(anon_client).status_code == 200  # xoá 9 lần sai trước đó
    for _ in range(9):
        _login(anon_client, password="sai-mat-khau")
    assert _login(anon_client).status_code == 200  # vẫn chưa tới 10 lần


def test_failures_spread_out_do_not_lock(anon_client: TestClient, clock) -> None:
    _register(anon_client)
    for _ in range(20):
        _login(anon_client, password="sai-mat-khau")
        clock[0] += timedelta(minutes=1)  # 1 lần mỗi phút: tối đa 6 lần trong 5 phút
    assert _login(anon_client).status_code == 200


def test_old_failures_are_cleaned_up(anon_client: TestClient, clock) -> None:
    _register(anon_client)
    for _ in range(3):
        _login(anon_client, password="sai-mat-khau")
    clock[0] += LOGIN_WINDOW + LOGIN_LOCKOUT + timedelta(seconds=1)
    _login(anon_client, "khac@example.com", "x")  # chỉ dọn bản ghi của email đang đăng nhập
    _login(anon_client, password="sai-mat-khau")
    conn = connect(db_path())
    keys = [r[0] for r in conn.execute("SELECT email_key FROM login_failures")]
    conn.close()
    assert sorted(keys) == ["an@example.com", "khac@example.com"]
