from __future__ import annotations

import base64
import hashlib
import hmac
import os

_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return ":".join([
        _PREFIX,
        str(_ITERATIONS),
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    ])


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if not stored.startswith(_PREFIX + ":"):
        return hmac.compare_digest(password, stored)
    try:
        _prefix, iterations, salt_b64, digest_b64 = stored.split(":", 3)
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def needs_rehash(stored: str) -> bool:
    return not stored.startswith(_PREFIX + ":")
