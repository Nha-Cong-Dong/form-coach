import base64
import hashlib

import pytest

from backend.security import SCRYPT_N, hash_password, verify_password


def test_correct_password_verifies() -> None:
    assert verify_password("dung-mat-khau", hash_password("dung-mat-khau"))


def test_wrong_password_is_rejected() -> None:
    stored = hash_password("dung-mat-khau")
    assert not verify_password("sai-mat-khau", stored)
    assert not verify_password("Dung-mat-khau", stored)  # phân biệt hoa thường
    assert not verify_password("", stored)


def test_same_password_gives_different_hashes() -> None:
    # Salt ngẫu nhiên: hai người cùng mật khẩu không lộ ra là trùng nhau.
    a, b = hash_password("cung-mat-khau"), hash_password("cung-mat-khau")
    assert a != b
    assert verify_password("cung-mat-khau", a) and verify_password("cung-mat-khau", b)


def test_stored_format() -> None:
    scheme, n, r, p, salt, digest = hash_password("x").split("$")
    assert (scheme, int(n), int(r), int(p)) == ("scrypt", SCRYPT_N, 8, 1)
    assert len(base64.b64decode(salt)) == 16
    assert len(base64.b64decode(digest)) == 32


def test_unicode_password() -> None:
    assert verify_password("mật khẩu có dấu 💪", hash_password("mật khẩu có dấu 💪"))
    assert not verify_password("mat khau co dau 💪", hash_password("mật khẩu có dấu 💪"))


def test_parameters_are_read_from_stored_string() -> None:
    # Chuỗi băm với tham số khác (như bản cũ trước khi tăng độ khó) vẫn kiểm tra được.
    salt = b"0123456789abcdef"
    digest = hashlib.scrypt(b"pw", salt=salt, n=2**10, r=8, p=1, dklen=32)
    b64 = base64.b64encode
    old = f"scrypt${2**10}$8$1${b64(salt).decode()}${b64(digest).decode()}"
    assert verify_password("pw", old)
    assert not verify_password("pw2", old)


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "khong-phai-hash",
        "bcrypt$16384$8$1$AAAA$AAAA",  # thuật toán khác
        "scrypt$16384$8$1$AAAA",  # thiếu phần
        "scrypt$abc$8$1$AAAA$AAAA",  # n không phải số
        "scrypt$1000$8$1$AAAA$AAAA",  # n không phải luỹ thừa của 2
        "scrypt$16384$8$1$!!!$AAAA",  # base64 sai
    ],
)
def test_malformed_stored_string_returns_false(stored: str) -> None:
    assert verify_password("pw", stored) is False
