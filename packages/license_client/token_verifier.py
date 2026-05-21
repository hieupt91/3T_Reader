from __future__ import annotations

import base64
import json

# Public key tương ứng với private key trên VPS
# Thay đổi nếu regenerate keypair
_ED25519_PUBLIC_B64 = "y0jZ/wQHoQ+VvAQjYuhlmf0R63cMLgkTHp1wzXrcM08="


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_token_offline(token: str) -> dict:
    """
    Verify chữ ký Ed25519 của token mà KHÔNG cần gọi server.
    Trả về payload dict nếu hợp lệ, raise ValueError nếu không hợp lệ.
    """
    parts = token.split(".")
    if len(parts) != 3 or not parts[2].startswith("ed."):
        raise ValueError("Token không phải định dạng Ed25519.")

    body_b64, sig_b64, alg = parts
    pub_b64_in_token = alg[3:]  # bỏ "ed."

    # Kiểm tra public key trong token khớp với key đã nhúng trong app
    expected_pub = base64.b64decode(_ED25519_PUBLIC_B64 + "==")
    token_pub = base64.b64decode(pub_b64_in_token + "==")
    if token_pub != expected_pub:
        raise ValueError("Public key trong token không khớp.")

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_key = Ed25519PublicKey.from_public_bytes(expected_pub)
        sig_bytes = _b64url_decode(sig_b64)
        pub_key.verify(sig_bytes, body_b64.encode("ascii"))
    except Exception as e:
        raise ValueError(f"Chữ ký không hợp lệ: {e}")

    body = _b64url_decode(body_b64)
    return json.loads(body.decode("utf-8"))


def is_ed25519_token(token: str) -> bool:
    """Kiểm tra token có phải Ed25519 format không."""
    parts = token.split(".")
    return len(parts) == 3 and parts[2].startswith("ed.")
