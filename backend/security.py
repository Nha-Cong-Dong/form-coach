"""Băm và kiểm tra mật khẩu bằng scrypt (`hashlib.scrypt`, thư viện chuẩn).

scrypt cố ý chậm và tốn RAM: lộ DB thì kẻ gian cũng không thử được hàng tỉ mật khẩu mỗi giây.
Mỗi mật khẩu có salt ngẫu nhiên riêng nên hai người cùng mật khẩu vẫn ra hai chuỗi khác nhau.

Chuỗi lưu trong `users.password_hash`: `scrypt$n$r$p$salt$hash` (salt và hash dạng base64).
Tham số nằm trong chuỗi nên sau này tăng độ khó thì mật khẩu cũ vẫn kiểm tra được.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# n = 2^14, r = 8, p = 1: cùng mức Django dùng cho scrypt, ~16 MB RAM và vài chục ms mỗi lần băm.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
HASH_BYTES = 32


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    # scrypt cần khoảng 128 * r * n byte RAM; mặc định hashlib chỉ cho 32 MB nên nới theo tham số.
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=256 * r * n,
        dklen=HASH_BYTES,
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    """Băm mật khẩu với salt ngẫu nhiên mới; trả chuỗi `scrypt$n$r$p$salt$hash`."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """True nếu mật khẩu khớp chuỗi đã lưu. Chuỗi hỏng hoặc lạ → False, không ném lỗi."""
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest, validate=True)
        actual = _scrypt(password, base64.b64decode(salt, validate=True), int(n), int(r), int(p))
    except ValueError:  # thiếu phần, số sai, base64 sai, tham số scrypt không hợp lệ
        return False
    # So sánh hết mọi byte dù sai ở đâu, để thời gian chạy không lộ đúng được bao nhiêu byte.
    return hmac.compare_digest(actual, expected)
