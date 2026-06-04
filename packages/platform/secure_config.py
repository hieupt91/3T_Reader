"""Secure config storage — encrypts sensitive values (API keys, tokens) at rest.

Uses Fernet symmetric encryption with a machine-derived key so that
config files cannot be copied to another machine and decrypted.

The encryption key is derived from:
  - hostname
  - username (login name)
  - a fixed application secret

This is NOT military-grade security — it protects against casual file
theft and accidental exposure, not against a targeted attacker with
access to the running machine.  For full disk encryption the OS handles
that separately.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

_SALT = b"3T_Reader_SecureConfig_v1"
_KEY_CACHE: bytes | None = None


def _machine_entropy() -> str:
    """Collect machine-specific entropy that is stable across reboots."""
    parts = [
        os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", ""),
        os.environ.get("USERNAME", "") or os.environ.get("USER", ""),
    ]
    if sys.platform == "win32":
        # Windows: machine GUID from registry (stable across reboots)
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            parts.append(str(guid))
        except Exception:
            pass
    else:
        # POSIX: use machine-id
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                parts.append(Path(p).read_text().strip())
                break
            except OSError:
                continue
    return "|".join(parts)


def _derive_key() -> bytes:
    """Derive a Fernet-compatible key from machine entropy."""
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE
    entropy = _machine_entropy().encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", entropy, _SALT, iterations=480_000, dklen=32)
    import base64
    _KEY_CACHE = base64.urlsafe_b64encode(dk)
    return _KEY_CACHE


def _get_fernet():
    from cryptography.fernet import Fernet
    return Fernet(_derive_key())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext string back to plaintext."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception:
        # If decryption fails (e.g. file copied from another machine),
        # return empty string so the caller knows the key is unusable.
        return ""


# --- High-level config helpers ---

# Keys whose values are sensitive and should be encrypted
_SENSITIVE_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "HF_API_KEY",
    "3T_AI_TOKEN",
})


def is_sensitive(key: str) -> bool:
    """Return True if *key* holds a secret that should be encrypted."""
    return key in _SENSITIVE_KEYS


def save_secure_config(config_path: str, data: dict) -> None:
    """Write *data* to *config_path*, encrypting sensitive values.

    Non-sensitive values are stored as-is so the file remains partially
    human-readable (provider choice, model names, URLs, etc.).
    """
    out = {}
    for k, v in data.items():
        if is_sensitive(k) and v:
            out[k] = {"__encrypted__": True, "value": encrypt_value(str(v))}
        else:
            out[k] = v
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def load_secure_config(config_path: str) -> dict:
    """Read *config_path* and decrypt any encrypted values.

    Falls back gracefully: if a value cannot be decrypted (machine change,
    corrupted data), it is set to an empty string.
    """
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict) and v.get("__encrypted__"):
            out[k] = decrypt_value(v.get("value", ""))
        else:
            out[k] = v
    return out
