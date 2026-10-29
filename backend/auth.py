"""Đăng ký, đăng nhập, đăng xuất bằng email + mật khẩu; dependency `current_user`.

Phiên đăng nhập là một token ngẫu nhiên gửi trong cookie HttpOnly (JavaScript không đọc được,
nên mã độc chèn vào trang cũng không lấy được). DB chỉ lưu sha256 của token. Mỗi request tra
bảng `auth_tokens` một lần; đăng xuất = xoá hàng đó, token mất hiệu lực ngay.

Biến môi trường:
- `FORMCOACH_ALLOW_REGISTER=1`: cho phép tạo tài khoản. Mặc định TẮT, để deploy mà quên cấu
  hình thì người lạ cũng không tự tạo tài khoản được.
- `FORMCOACH_ADMIN_EMAILS=a@x.com,b@y.com`: tài khoản admin (dùng công cụ dữ liệu: danh sách
  hiệp, gán nhãn, Quay dữ liệu). So không phân biệt hoa thường. Mặc định trống = không ai là admin.
- `FORMCOACH_COOKIE_SECURE=0`: cho cookie đi qua HTTP thường. Mặc định cookie có cờ `Secure`
  (chỉ gửi qua HTTPS), để deploy mà quên cấu hình cũng an toàn. Dev vẫn chạy vì trình duyệt vào
  Vite qua HTTPS (và localhost được coi là an toàn); test chạy qua http nên đặt 0.

Mỗi route ghi DB ở đây tự `commit()` trước khi trả về: nếu commit lỗi thì request lỗi luôn,
không có chuyện trình duyệt nhận cookie trỏ tới token chưa được lưu.
"""

from __future__ import annotations

import hashlib
import math
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.security import hash_password, verify_password

COOKIE_NAME = "formcoach_session"
TOKEN_TTL = timedelta(days=30)
MIN_PASSWORD_LENGTH = 8
MAX_EMAIL_LENGTH = 254
# scrypt tốn RAM/CPU theo mỗi lần gọi; chặn mật khẩu khổng lồ trước khi băm (kể cả khi đăng nhập).
MAX_PASSWORD_LENGTH = 1024
# Chống đoán mật khẩu (D0b): sai LOGIN_MAX_FAILURES lần trong LOGIN_WINDOW với cùng một email
# → khoá email đó LOGIN_LOCKOUT, tính từ lần sai cuối. Đếm theo email, không theo IP: sau proxy
# của nơi deploy, IP thật cần cấu hình thêm (xem lại ở D1).
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW = timedelta(minutes=5)
LOGIN_LOCKOUT = timedelta(minutes=15)

router = APIRouter(prefix="/api/auth", tags=["auth"])
Db = Annotated[sqlite3.Connection, Depends(get_db)]


@dataclass(frozen=True)
class User:
    id: int
    email: str


class Credentials(BaseModel):
    # Quá dài → FastAPI trả 422 trước khi vào route (không chạy scrypt).
    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


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
    # Tên miền phải có dấu chấm ở giữa (x.com), như các trang web thường kiểm tra.
    host, dot, tld = domain.rpartition(".")
    if not (at and local and host and dot and tld) or "@" in domain:
        raise HTTPException(status_code=422, detail="email không hợp lệ")
    if any(c.isspace() for c in email):
        raise HTTPException(status_code=422, detail="email không được có khoảng trắng")
    if len(email) > MAX_EMAIL_LENGTH:
        raise HTTPException(status_code=422, detail="email quá dài")


def _cookie_secure() -> bool:
    return os.environ.get("FORMCOACH_COOKIE_SECURE", "1") != "0"


def _start_session(db: sqlite3.Connection, response: Response, user_id: int) -> None:
    """Dọn token hết hạn của user, tạo token mới, lưu hash vào DB, commit, rồi mới đặt cookie."""
    token = secrets.token_urlsafe(32)
    now = _now()
    # Mọi mốc thời gian đều do _now().isoformat() ghi (cùng định dạng UTC) nên so chuỗi là đúng.
    db.execute(
        "DELETE FROM auth_tokens WHERE user_id = ? AND expires_at <= ?",
        (user_id, now.isoformat()),
    )
    db.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_hash_token(token), user_id, now.isoformat(), (now + TOKEN_TTL).isoformat()),
    )
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )


def lockout_end(failures: list[datetime]) -> datetime | None:
    """Thời điểm hết khoá theo danh sách lần sai (sắp tăng dần), hoặc None nếu chưa từng đủ để khoá.

    Khoá khi có LOGIN_MAX_FAILURES lần sai liên tiếp nằm trong LOGIN_WINDOW; hết khoá sau
    LOGIN_LOCKOUT tính từ lần sai thứ LOGIN_MAX_FAILURES đó. Hàm thuần: người gọi tự so với giờ
    hiện tại.
    """
    end = None
    n = LOGIN_MAX_FAILURES
    for i in range(n - 1, len(failures)):
        if failures[i] - failures[i - n + 1] <= LOGIN_WINDOW:
            end = failures[i] + LOGIN_LOCKOUT
    return end


def _login_locked_for(db: sqlite3.Connection, email_key: str, now: datetime) -> timedelta | None:
    """Còn bị khoá bao lâu (None = không khoá). Dọn luôn lần sai đã quá cũ của email này."""
    oldest = now - LOGIN_WINDOW - LOGIN_LOCKOUT
    db.execute(
        "DELETE FROM login_failures WHERE email_key = ? AND at < ?",
        (email_key, oldest.isoformat()),
    )
    rows = db.execute(
        "SELECT at FROM login_failures WHERE email_key = ? ORDER BY at", (email_key,)
    ).fetchall()
    end = lockout_end([datetime.fromisoformat(r["at"]) for r in rows])
    return end - now if end is not None and end > now else None


def _register_allowed() -> bool:
    return os.environ.get("FORMCOACH_ALLOW_REGISTER") == "1"


def user_for_token(db: sqlite3.Connection, token: str | None) -> User | None:
    """Người dùng của token trong cookie; không có / lạ / hết hạn → None. Dùng chung cho
    `current_user` (HTTP) và WebSocket (/api/live), để hai nơi kiểm tra y như nhau."""
    if not token:
        return None
    row = db.execute(
        "SELECT u.id, u.email, t.expires_at FROM auth_tokens t"
        " JOIN users u ON u.id = t.user_id WHERE t.token_hash = ?",
        (_hash_token(token),),
    ).fetchone()
    # So thời gian bằng datetime, không so chuỗi, để không phụ thuộc định dạng chuỗi ISO.
    if row is None or datetime.fromisoformat(row["expires_at"]) <= _now():
        return None
    return User(id=row["id"], email=row["email"])


def current_user(
    db: Db,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    """Dependency: người dùng của request. Không cookie, token lạ hoặc hết hạn → 401."""
    if not token:
        raise HTTPException(status_code=401, detail="chưa đăng nhập")
    user = user_for_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return user


def is_admin(user: User) -> bool:
    """Email có trong `FORMCOACH_ADMIN_EMAILS` không. Đọc lại mỗi lần để test đổi được.

    Danh sách nằm ở biến môi trường, không ở DB: chỉ 1–2 admin cố định, không cần đổi bảng.
    """
    raw = os.environ.get("FORMCOACH_ADMIN_EMAILS", "")
    admins = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return user.email.lower() in admins


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    """Dependency: như `current_user` (401 nếu chưa đăng nhập), thêm 403 nếu không phải admin."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="chỉ admin được dùng công cụ dữ liệu")
    return user


@router.get("/options")
def options() -> dict[str, Any]:
    """Cấu hình màn đăng nhập (không cần đăng nhập): web ẩn nút "Tạo tài khoản" khi tắt đăng ký."""
    return {"allow_register": _register_allowed()}


@router.post("/register", status_code=201)
def register(body: Credentials, response: Response, db: Db) -> dict[str, Any]:
    """Tạo tài khoản rồi đăng nhập luôn. 403: đang tắt đăng ký; 409: email đã có."""
    if not _register_allowed():
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
    """Đăng nhập. Sai email hay sai mật khẩu đều cùng một thông báo 401.

    429 (kèm Retry-After, giây) khi email đang bị khoá vì sai quá nhiều lần: không kiểm tra mật
    khẩu (kể cả đúng), không ghi thêm lần sai, nên thời gian khoá không bị kéo dài.
    """
    email_key = body.email.lower()
    now = _now()
    remaining = _login_locked_for(db, email_key, now)
    if remaining is not None:
        db.commit()  # giữ phần dọn bản ghi cũ; get_db sẽ rollback khi ném lỗi
        seconds = math.ceil(remaining.total_seconds())
        raise HTTPException(
            status_code=429,
            detail="đăng nhập sai quá nhiều lần, thử lại sau",
            headers={"Retry-After": str(seconds)},
        )
    row = db.execute(
        "SELECT id, email, password_hash FROM users WHERE lower(email) = lower(?)",
        (body.email,),
    ).fetchone()
    stored = row["password_hash"] if row else _dummy_hash()
    if not verify_password(body.password, stored) or row is None:
        db.execute(
            "INSERT INTO login_failures (email_key, at) VALUES (?, ?)", (email_key, now.isoformat())
        )
        # Commit trước khi ném 401: get_db rollback mọi thứ khi route lỗi, kể cả lần sai này.
        db.commit()
        raise HTTPException(status_code=401, detail="email hoặc mật khẩu không đúng")
    db.execute("DELETE FROM login_failures WHERE email_key = ?", (email_key,))
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
        db.commit()
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=_cookie_secure(), httponly=True, samesite="lax"
    )
    return {"logged_out": True}


@router.get("/me")
def me(user: Annotated[User, Depends(current_user)]) -> dict[str, Any]:
    """Người dùng đang đăng nhập (web dùng để biết có cần hiện màn đăng nhập không, và có hiện
    công cụ dữ liệu không: `is_admin`)."""
    return {"id": user.id, "email": user.email, "is_admin": is_admin(user)}
