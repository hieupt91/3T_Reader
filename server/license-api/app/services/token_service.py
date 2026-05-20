from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass
class TokenService:
    secret: str

    def sign(self, payload: dict) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        body_b64 = _b64url(body)
        sig = hmac.new(self.secret.encode("utf-8"), body_b64.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body_b64}.{sig}"

    def verify(self, token: str) -> dict:
        body_b64, sig = token.split(".", 1)
        expected = hmac.new(self.secret.encode("utf-8"), body_b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Invalid token signature")
        body = _b64url_decode(body_b64)
        return json.loads(body.decode("utf-8"))
