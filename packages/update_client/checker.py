from __future__ import annotations

import hashlib
import platform
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .manifest import UpdateManifest

_TIMEOUT = 10

# Nhúng THẲNG (không import từ packages.license_client.token_verifier) -
# cùng lý do và cùng danh sách key với Windows
# (packages/updater/update_client.py trên nhánh piper-vps-sync): import
# xuyên package có thể vỡ âm thầm trên bản build đóng gói (PyInstaller),
# khiến verify luôn fail mà không ai biết vì sao (xác nhận thật trên
# Windows 14/08/2026). PHẢI giữ giống hệt
# packages/license_client/token_verifier.py:_TRUSTED_ED25519_PUBLIC_KEYS_B64
# khi xoay key.
#
# QUAN TRỌNG - vá lỗ hổng bảo mật thật (15/08/2026): trước bản vá này,
# updater Mac hoàn toàn KHÔNG verify chữ ký hay SHA-256 gì cả -
# download_update() tải thẳng file về và chạy, tin tưởng 100% vào
# download_url mà không kiểm tra gì. Nếu domain/CDN từng bị chiếm quyền
# hoặc bị MITM, đây là đường thực thi mã độc trực tiếp. Xem
# docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md mục 3.
_EMBEDDED_PUBLIC_KEYS_B64: list[str] = [
    "y0jZ/wQHoQ+VvAQjYuhlmf0R63cMLgkTHp1wzXrcM08=",
    "PaBi70B9rG1UMSJUJrHElYYhZmNWYSLdL4hrotwWU8I=",
]


def _current_platform() -> str:
    if sys.platform == "darwin":
        return "mac"
    if sys.platform == "win32":
        return "windows"
    return "linux"


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _verify_signature(manifest_signature: str, manifest_json_bytes: bytes) -> bool:
    import warnings

    if not _EMBEDDED_PUBLIC_KEYS_B64:
        warnings.warn(
            "Updater: missing embedded Ed25519 public key; refusing unverified update.",
            stacklevel=2,
        )
        return False

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature

        sig_bytes = base64.b64decode(manifest_signature + "==")
    except Exception as exc:
        warnings.warn(f"Updater: invalid manifest signature: {exc}", stacklevel=2)
        return False

    for key_b64 in _EMBEDDED_PUBLIC_KEYS_B64:
        try:
            pub_bytes = base64.b64decode(key_b64 + "==")
            pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(sig_bytes, manifest_json_bytes)
            return True
        except InvalidSignature:
            continue
        except Exception:
            continue

    warnings.warn("Updater: invalid manifest signature (no trusted key matched).", stacklevel=2)
    return False


@dataclass
class UpdateInfo:
    available: bool
    current_version: str = ""
    latest_version: str = ""
    download_url: str = ""
    sha256: str = ""
    signature: str = ""
    mandatory: bool = False
    release_notes: str = ""
    error: Optional[str] = None


@dataclass
class UpdateResult:
    success: bool
    path: Optional[str] = None
    error: Optional[str] = None


def check_for_update(base_url: str, current_version: str, channel: str = "stable") -> UpdateInfo:
    try:
        import requests
        plat = _current_platform()
        url = (
            f"{base_url.rstrip('/')}/api/v1/update/check"
            f"?platform={plat}&current_version={current_version}"
        )
        resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "3T-Reader/1.0"})
        resp.raise_for_status()
        data = resp.json()

        latest = data.get("version") or data.get("latest_version") or ""
        if not latest or not _is_newer(latest, current_version):
            return UpdateInfo(available=False, current_version=current_version, latest_version=latest)

        return UpdateInfo(
            available=True,
            current_version=current_version,
            latest_version=latest,
            download_url=data.get("download_url", ""),
            sha256=data.get("sha256", ""),
            signature=data.get("signature", ""),
            mandatory=bool(data.get("mandatory", False)),
            release_notes=data.get("release_notes", ""),
        )
    except Exception as e:
        return UpdateInfo(available=False, current_version=current_version, error=str(e))


def download_update(
    info: UpdateInfo,
    progress_cb: Callable[[int], None] | None = None,
) -> UpdateResult:
    if not info.available or not info.download_url:
        return UpdateResult(success=False, error="Không có bản cập nhật để tải.")
    if not info.sha256:
        return UpdateResult(success=False, error="Manifest thiếu SHA-256 - từ chối cập nhật.")
    if not info.signature:
        return UpdateResult(success=False, error="Manifest thiếu chữ ký xác thực - từ chối cập nhật.")

    try:
        import json
        import requests

        resp = requests.get(info.download_url, timeout=120, stream=True, headers={"User-Agent": "3T-Reader/1.0"})
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0) or 0)
        done = 0

        default_suffix = ".exe" if sys.platform == "win32" else ".dmg"
        suffix = Path(info.download_url.split("?")[0]).suffix or default_suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="3TReader_update_")
        hasher = hashlib.sha256()
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            tmp.write(chunk)
            hasher.update(chunk)
            done += len(chunk)
            if progress_cb and total > 0:
                progress_cb(min(100, int(done * 100 / total)))
        tmp.close()

        actual_sha256 = hasher.hexdigest()
        if actual_sha256.lower() != info.sha256.lower():
            Path(tmp.name).unlink(missing_ok=True)
            return UpdateResult(
                success=False,
                error=f"SHA-256 không khớp: expected={info.sha256}, got={actual_sha256}",
            )

        manifest_bytes = json.dumps(
            {
                "version": info.latest_version,
                "download_url": info.download_url,
                "sha256": info.sha256,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if not _verify_signature(info.signature, manifest_bytes):
            Path(tmp.name).unlink(missing_ok=True)
            return UpdateResult(
                success=False,
                error="Chữ ký manifest không hợp lệ - tệp cập nhật bị từ chối.",
            )

        if progress_cb:
            progress_cb(100)
        return UpdateResult(success=True, path=tmp.name)
    except Exception as e:
        return UpdateResult(success=False, error=str(e))
