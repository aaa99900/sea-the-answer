"""Password policy and the existing salted scrypt format (no silent truncation)."""

import hashlib
import hmac
from secrets import token_hex

from .errors import require


def validate_password(value, username=""):
    require(isinstance(value, str) and 12 <= len(value) <= 128,
            "비밀번호는 12~128자로 입력해 주세요.")
    require(value.strip() and value.casefold() not in {
        username.casefold(), "password1234", "123456789012", "admin12345678",
    }, "아이디나 기본 비밀번호 대신 본인만 아는 비밀번호를 입력해 주세요.")
    return value


def hash_password(value):
    salt = token_hex(16)
    return salt + ":" + hashlib.scrypt(value.encode(), salt=salt.encode(),
                                      n=16384, r=8, p=1, dklen=64).hex()


def verify_password(value, encoded):
    if not isinstance(value, str) or not 0 < len(value) <= 128:
        return False
    try:
        salt, expected = encoded.split(":", 1)
        actual = hashlib.scrypt(value.encode(), salt=salt.encode(),
                                n=16384, r=8, p=1, dklen=64).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


# Unknown accounts still perform a password hash without revealing their existence.
DUMMY_PASSWORD = hash_password(token_hex(32))
