"""Đăng ký, đăng nhập, đăng xuất bằng email + mật khẩu; dependency `current_user`.

Phiên đăng nhập là một token ngẫu nhiên gửi trong cookie HttpOnly (JavaScript không đọc được,
nên mã độc chèn vào trang cũng không lấy được). DB chỉ lưu sha256 của token. Mỗi request tra
bảng `auth_tokens` một lần; đăng xuất = xoá hàng đó, token mất hiệu lực ngay.

Biến môi trường:
- `FORMCOACH_ALLOW_REGISTER=1`: cho phép tạo tài khoản. Mặc định TẮT, để deploy mà quên cấu
  hình thì người lạ cũng không tự tạo tài khoản được.
- `FORMCOACH_COOKIE_SECURE=1`: cookie chỉ gửi qua HTTPS (bật khi deploy).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from backend.db import get_db
from backend.security import hash_password, verify_password

COOKIE_NAME = "formcoach_session"
TOKEN_TTL = timedelta(days=30)
MIN_PASSWORD_LENGTH = 8
MAX_EMAIL_LENGTH = 254

router = APIRouter(prefix="/api/auth", tags=["auth"])
Db = Annotated[sqlite3.Connection, Depends(get_db)]


@dataclass(frozen=True)
class User:
    id: int
    email: str


class Credentials(BaseModel):
    email: str
    password: str


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@cache
def _dummy_hash() -> str:
    """Hash giả để email không tồn tại cũng tốn thời gian kiểm tra như email có thật."""
    return hash_password(secrets.token_hex(16))


def _check_email(email: str) -> None:
    """Chỉ kiểm tra hình dạng tối thiểu; không sửa email (lưu đúng như người dùng gõ)."""
    local, at, domain = email.partition("@")
    if not (at and local and domain) or "@" in domain:
        raise HTTPException(status_code=422, detail="email không hợp lệ")
    if any(c.isspace() for c in email):
        raise HTTPException(status_code=422, detail="email không được có khoảng trắng")
    if len(email) > MAX_EMAIL_LENGTH:
        raise HTTPException(status_code=422, detail="email quá dài")


def _start_session(db: sqlite3.Connection, response: Response, user_id: int) -> None:
    """Tạo token mới, lưu hash vào DB, đặt cookie."""
    token = secrets.token_urlsafe(32)
    now = _now()
    db.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_hash_token(token), user_id, now.isoformat(), (now + TOKEN_TTL).isoformat()),
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("FORMCOACH_COOKIE_SECURE") == "1",
        path="/",
    )


def current_user(
    db: Db,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    """Dependency: người dùng của request. Không cookie, token lạ hoặc hết hạn → 401."""
    if not token:
        raise HTTPException(status_code=401, detail="chưa đăng nhập")
    row = db.execute(
        "SELECT u.id, u.email, t.expires_at FROM auth_tokens t"
        " JOIN users u ON u.id = t.user_id WHERE t.token_hash = ?",
        (_hash_token(token),),
    ).fetchone()
    # So thời gian bằng datetime, không so chuỗi, để không phụ thuộc định dạng chuỗi ISO.
    if row is None or datetime.fromisoformat(row["expires_at"]) <= _now():
        raise HTTPException(status_code=401, detail="phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return User(id=row["id"], email=row["email"])


@router.post("/register", status_code=201)
def register(body: Credentials, response: Response, db: Db) -> dict[str, Any]:
    """Tạo tài khoản rồi đăng nhập luôn. 403: đang tắt đăng ký; 409: email đã có."""
    if os.environ.get("FORMCOACH_ALLOW_REGISTER") != "1":
        raise HTTPException(status_code=403, detail="đăng ký đang tắt")
    _check_email(body.email)
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422, detail=f"mật khẩu cần ít nhất {MIN_PASSWORD_LENGTH} ký tự"
        )
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (body.email, hash_password(body.password), _now().isoformat()),
        )
    except sqlite3.IntegrityError:  # chỉ mục lower(email): trùng không phân biệt hoa thường
        raise HTTPException(status_code=409, detail="email đã được đăng ký") from None
    user_id = int(cur.lastrowid)
    _start_session(db, response, user_id)
    return {"id": user_id, "email": body.email}


@router.post("/login")
def login(body: Credentials, response: Response, db: Db) -> dict[str, Any]:
    """Đăng nhập. Sai email hay sai mật khẩu đều cùng một thông báo 401."""
    row = db.execute(
        "SELECT id, email, password_hash FROM users WHERE lower(email) = lower(?)",
        (body.email,),
    ).fetchone()
    stored = row["password_hash"] if row else _dummy_hash()
    if not verify_password(body.password, stored) or row is None:
        raise HTTPException(status_code=401, detail="email hoặc mật khẩu không đúng")
    _start_session(db, response, row["id"])
    return {"id": row["id"], "email": row["email"]}


@router.post("/logout")
def logout(
    response: Response,
    db: Db,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> dict[str, Any]:
    """Xoá token khỏi DB và xoá cookie. Gọi khi chưa đăng nhập cũng không lỗi."""
    if token:
        db.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (_hash_token(token),))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"logged_out": True}


@router.get("/me")
def me(user: Annotated[User, Depends(current_user)]) -> dict[str, Any]:
    """Người dùng đang đăng nhập (web dùng để biết có cần hiện màn đăng nhập không)."""
    return {"id": user.id, "email": user.email}
