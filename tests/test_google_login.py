"""Đăng nhập Google (G1): kiểm tra ID token + route POST /api/auth/google.

Không gọi Google: tự tạo cặp khoá RSA, ký token như Google ký, và thay `_signing_key` (chỗ duy nhất
lấy khoá công khai từ Google) bằng khoá công khai tự tạo.
"""

import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend import google_login
from backend.app import app
from backend.auth import COOKIE_NAME
from backend.db import connect
from backend.google_login import GoogleTokenError, verify_id_token

CLIENT_ID = "123-abc.apps.googleusercontent.com"
PW = "mat-khau-dai"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, algorithm: str = "RS256", **changes) -> str:
    """ID token giống của Google; `changes` sửa/xoá (giá trị ...) từng claim."""
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1100000000001",
        "email": "an@gmail.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 3600,
    }
    for name, value in changes.items():
        if value is ...:
            del claims[name]
        else:
            claims[name] = value
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "k1"})


@pytest.fixture(autouse=True)
def fake_google_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_login, "_signing_key", lambda _token: KEY.public_key())


# --- kiểm tra token ---


def test_valid_token() -> None:
    identity = verify_id_token(token(), CLIENT_ID)
    assert identity == google_login.GoogleIdentity("1100000000001", "an@gmail.com", True)
    assert verify_id_token(token(iss="accounts.google.com"), CLIENT_ID).sub == "1100000000001"


def test_email_verified_variants() -> None:
    assert verify_id_token(token(email_verified="true"), CLIENT_ID).email_verified
    assert not verify_id_token(token(email_verified=False), CLIENT_ID).email_verified
    assert not verify_id_token(token(email_verified=...), CLIENT_ID).email_verified


@pytest.mark.parametrize(
    "bad",
    [
        token(aud="app-khac.apps.googleusercontent.com"),  # token cấp cho app khác
        token(iss="https://evil.example.com"),
        token(exp=int(time.time()) - 60),  # hết hạn
        token(key=OTHER_KEY),  # không phải Google ký
        token(sub=...),
        token(exp=...),
        token(email=...),
        token(sub=""),
        "khong-phai-jwt",
        "",
    ],
)
def test_invalid_tokens(bad: str) -> None:
    with pytest.raises(GoogleTokenError):
        verify_id_token(bad, CLIENT_ID)


def test_only_rs256_accepted() -> None:
    """Chỉ nhận RS256: token "none" (không chữ ký) hay HS256 (khoá đối xứng tự chọn) bị từ chối."""
    unsigned = jwt.encode(
        {"iss": "accounts.google.com", "aud": CLIENT_ID, "sub": "1", "email": "a@b.c"},
        None,
        algorithm="none",
    )
    with pytest.raises(GoogleTokenError):
        verify_id_token(unsigned, CLIENT_ID)
    with pytest.raises(GoogleTokenError):
        verify_id_token(
            token(key="khoa-bi-mat-doi-xung-du-dai-32-byte!!", algorithm="HS256"), CLIENT_ID
        )


def test_too_long_token_rejected_before_decoding() -> None:
    with pytest.raises(GoogleTokenError, match="quá dài"):
        verify_id_token("a" * (google_login.MAX_TOKEN_LENGTH + 1), CLIENT_ID)


def test_key_fetch_failure_is_token_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không tải được khoá của Google (mạng) → GoogleTokenError, route trả 401 thay vì 500."""

    def fail(_token: str):
        raise jwt.PyJWKClientConnectionError("không kết nối được")

    monkeypatch.setattr(google_login, "_signing_key", fail)
    with pytest.raises(GoogleTokenError):
        verify_id_token(token(), CLIENT_ID)


# --- qua API ---


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pg_database: str) -> TestClient:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
    monkeypatch.setenv("FORMCOACH_GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.delenv("FORMCOACH_ALLOW_REGISTER", raising=False)  # tài khoản mới chỉ qua Google
    monkeypatch.delenv("FORMCOACH_ADMIN_EMAILS", raising=False)
    return TestClient(app)


def google(client: TestClient, **changes):
    return client.post("/api/auth/google", json={"credential": token(**changes)})


def users() -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT id, email, password_hash, google_sub FROM users ORDER BY id"
        ).fetchall()


def test_options_show_client_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/auth/options").json()["google_client_id"] == CLIENT_ID
    monkeypatch.delenv("FORMCOACH_GOOGLE_CLIENT_ID")
    assert client.get("/api/auth/options").json()["google_client_id"] is None


def test_disabled_without_client_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORMCOACH_GOOGLE_CLIENT_ID")
    assert google(client).status_code == 404
    assert users() == []


def test_new_google_user_even_when_register_is_off(client: TestClient) -> None:
    r = google(client)
    assert r.status_code == 200
    assert r.json()["email"] == "an@gmail.com" and r.json()["is_admin"] is False
    assert COOKIE_NAME in r.cookies
    assert client.get("/api/auth/me").json()["email"] == "an@gmail.com"
    [row] = users()
    assert row["password_hash"] is None and row["google_sub"] == "1100000000001"


def test_same_google_account_logs_into_same_user(client: TestClient) -> None:
    first = google(client).json()["id"]
    # Đổi email bên Google: vẫn là tài khoản đó (tìm theo sub, không theo email).
    again = google(TestClient(app), email="an.moi@gmail.com").json()
    assert again["id"] == first and again["email"] == "an@gmail.com"
    assert len(users()) == 1


def test_links_existing_password_account_and_drops_password(
    client: TestClient, monkeypatch
) -> None:
    """Gộp vào tài khoản cùng email (giữ dữ liệu) và xoá mật khẩu: người tạo trước tài khoản bằng
    email của chủ Google (đăng ký không xác minh email) không còn đăng nhập được."""
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    owner = TestClient(app)
    r = owner.post("/api/auth/register", json={"email": "An@Gmail.com", "password": PW})
    old_id = r.json()["id"]
    r = google(TestClient(app))  # email khác hoa thường vẫn là một tài khoản
    assert r.status_code == 200 and r.json()["id"] == old_id
    [row] = users()
    assert row["google_sub"] == "1100000000001" and row["password_hash"] is None
    login = TestClient(app).post("/api/auth/login", json={"email": "an@gmail.com", "password": PW})
    assert login.status_code == 401
    # Phiên mở bằng mật khẩu từ trước bị huỷ; đăng nhập lại thì phải qua Google.
    assert owner.get("/api/auth/me").status_code == 401
    assert google(owner).json()["id"] == old_id
    assert owner.get("/api/auth/me").json()["id"] == old_id


def test_unverified_email_is_403(client: TestClient) -> None:
    r = google(client, email_verified=False)
    assert r.status_code == 403
    assert users() == []


def test_invalid_token_is_401(client: TestClient) -> None:
    assert google(client, aud="app-khac").status_code == 401
    r = client.post("/api/auth/google", json={"credential": "rac"})
    assert r.status_code == 401 and r.json()["detail"] == "đăng nhập Google không hợp lệ"
    assert users() == []


def test_email_linked_to_other_google_account_is_409(client: TestClient) -> None:
    google(client)
    r = google(TestClient(app), sub="2200000000002")  # Google khác, cùng email
    assert r.status_code == 409
    assert len(users()) == 1


def test_google_only_account_has_no_password(client: TestClient, monkeypatch) -> None:
    google(client)
    r = TestClient(app).post("/api/auth/login", json={"email": "an@gmail.com", "password": PW})
    assert r.status_code == 401 and r.json()["detail"] == "email hoặc mật khẩu không đúng"
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    r = TestClient(app).post("/api/auth/register", json={"email": "an@gmail.com", "password": PW})
    assert r.status_code == 409  # không chiếm được email của tài khoản Google


def test_admin_by_google_email(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("FORMCOACH_ADMIN_EMAILS", "an@gmail.com")
    assert google(client).json()["is_admin"] is True


def test_huge_credential_is_422(client: TestClient) -> None:
    r = client.post("/api/auth/google", json={"credential": "a" * 10_000})
    assert r.status_code == 422
