from __future__ import annotations

import base64
import json

# Danh sách public key được tin cậy cho token V1 (license offline verify).
# Hỗ trợ NHIỀU key song song để xoay key an toàn: khi cần đổi private key
# trên VPS, thêm key mới vào ĐẦU danh sách nhưng GIỮ NGUYÊN key cũ cho tới
# khi đa số client đã cập nhật bản build có key mới — token ký bằng key cũ
# HOẶC key mới đều verify offline được, không ai bị rơi về online-only giữa
# chừng. Chỉ xoá key cũ khỏi danh sách khi chắc chắn không còn client nào
# dùng nữa (xem docs/HANDOFF_MULTIKEY_ED25519_2026-08.md).
_TRUSTED_ED25519_PUBLIC_KEYS_B64 = [
    "y0jZ/wQHoQ+VvAQjYuhlmf0R63cMLgkTHp1wzXrcM08=",  # key gốc, đang dùng từ 07/2026
]


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_token_offline(token: str) -> dict:
    """
    Verify chữ ký Ed25519 của token mà KHÔNG cần gọi server.
    Trả về payload dict nếu hợp lệ, raise ValueError nếu không hợp lệ.
    """
    parts = token.split(".")
    # Format: body.sig.ed.pubkey (4 parts)
    if len(parts) != 4 or parts[2] != "ed":
        raise ValueError("Token không phải định dạng Ed25519.")

    body_b64, sig_b64, _, pub_b64_in_token = parts
    token_pub = base64.b64decode(pub_b64_in_token + "==")

    # Public key trong token phải khớp MỘT trong các key đã nhúng trong app.
    trusted_pubs = [base64.b64decode(k + "==") for k in _TRUSTED_ED25519_PUBLIC_KEYS_B64]
    if token_pub not in trusted_pubs:
        raise ValueError("Public key trong token không khớp.")

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_key = Ed25519PublicKey.from_public_bytes(token_pub)
        sig_bytes = _b64url_decode(sig_b64)
        pub_key.verify(sig_bytes, body_b64.encode("ascii"))
    except Exception as e:
        raise ValueError(f"Chữ ký không hợp lệ: {e}")

    body = _b64url_decode(body_b64)
    return json.loads(body.decode("utf-8"))


def is_ed25519_token(token: str) -> bool:
    """Kiểm tra token có phải Ed25519 format không."""
    parts = token.split(".")
    return len(parts) == 4 and parts[2] == "ed"
