"""Kiểm tra ID token của "Sign in with Google" (G1). Không gọi DB: route ở backend/auth.py.

Web nhận ID token (một JWT do Google ký) từ nút Google rồi gửi lên. Server tự kiểm, không tin web:
- chữ ký RS256 bằng khoá công khai của Google (JWKS, tải một lần rồi giữ trong bộ nhớ);
- `aud` = Client ID của app (token cấp cho app khác không dùng được ở đây);
- `iss` là Google, `exp` chưa qua (PyJWT kiểm), có đủ `sub`, `email`, `email_verified`.

Biến môi trường `FORMCOACH_GOOGLE_CLIENT_ID` (dạng `....apps.googleusercontent.com`): không phải
bí mật (web cũng cần nó để vẽ nút). Không đặt → đăng nhập Google tắt.

Thư viện: PyJWT[crypto] (bạn chọn b, 2026-11-07): ít gói hơn `google-auth` và có cache khoá.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from typing import Any

import jwt

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
MAX_TOKEN_LENGTH = 4096  # ID token của Google ~1–1,5 KB; chặn chuỗi khổng lồ trước khi giải mã


class GoogleTokenError(Exception):
    """Token không hợp lệ (sai chữ ký, aud/iss, hết hạn, thiếu trường) hoặc không lấy được khoá."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str  # mã người dùng Google, cố định suốt đời tài khoản (email thì có thể đổi)
    email: str
    email_verified: bool


def client_id() -> str | None:
    """Client ID đang cấu hình; None = tắt đăng nhập Google. Đọc lại mỗi lần để test đổi được."""
    return os.environ.get("FORMCOACH_GOOGLE_CLIENT_ID", "").strip() or None


@cache
def _jwks_client() -> jwt.PyJWKClient:
    # Giữ bộ khoá 1 giờ; token có `kid` lạ (Google vừa xoay khoá) thì PyJWKClient tự tải lại.
    return jwt.PyJWKClient(GOOGLE_CERTS_URL, lifespan=3600, timeout=5)


def _signing_key(token: str) -> Any:
    """Khoá công khai của Google khớp `kid` trong token. Test thay hàm này bằng khoá tự tạo."""
    return _jwks_client().get_signing_key_from_jwt(token).key


def verify_id_token(token: str, audience: str) -> GoogleIdentity:
    """ID token → GoogleIdentity; sai bất kỳ điều kiện nào → GoogleTokenError."""
    if not token or len(token) > MAX_TOKEN_LENGTH:
        raise GoogleTokenError("token rỗng hoặc quá dài")
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],  # chỉ RS256: chặn token tự ký bằng thuật toán khác (vd "none")
            audience=audience,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as e:  # gồm cả lỗi tải khoá (PyJWKClientError)
        raise GoogleTokenError(str(e)) from None
    sub, email = claims.get("sub"), claims.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or "@" not in email:
        raise GoogleTokenError("token thiếu sub hoặc email")
    # Google gửi boolean; token kiểu cũ có thể là chuỗi "true".
    verified = claims.get("email_verified") in (True, "true")
    return GoogleIdentity(sub=sub, email=email, email_verified=verified)
