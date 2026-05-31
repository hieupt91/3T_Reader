from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_TIMEOUT = 15  # seconds
_PRODUCT = "3T_READER"
_CHANNEL = "stable"

# Ed25519 public key nhúng sẵn — phải khớp với key trên VPS.
# Nếu packages.license_client.token_verifier không import được,
# chữ ký manifest sẽ bị bỏ qua (skip với cảnh báo).
_EMBEDDED_PUBLIC_B64: Optional[str] = None
try:
    from packages.license_client.token_verifier import _ED25519_PUBLIC_B64  # type: ignore[import]
    _EMBEDDED_PUBLIC_B64 = _ED25519_PUBLIC_B64
except Exception:
    pass  # Sig check sẽ bị skip — xem _verify_signature()


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class UpdateInfo:
    """Kết quả kiểm tra phiên bản mới."""

    available: bool
    current_version: str = ""
    latest_version: str = ""
    download_url: str = ""
    sha256: str = ""
    signature: str = ""
    release_notes: str = ""


@dataclass
class UpdateResult:
    """Kết quả tải xuống bản cập nhật."""

    success: bool
    path: str = ""
    error: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get(url: str, params: dict | None = None) -> dict:
    import requests

    resp = requests.get(
        url,
        params=params,
        headers={"User-Agent": "3T-Reader-Updater/1.0"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_semver(version: str) -> tuple[int, ...]:
    """Chuyển chuỗi semver 'X.Y.Z' thành tuple số nguyên để so sánh.
    Phần hậu tố (e.g. '-beta.1') được bỏ qua."""
    core = version.strip().lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in core.split("."))
    except ValueError:
        return (0,)


def _is_newer(latest: str, current: str) -> bool:
    """Trả về True nếu *latest* mới hơn *current*."""
    return _parse_semver(latest) > _parse_semver(current)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_signature(manifest_signature: str, manifest_json_bytes: bytes) -> bool:
    """Xác thực chữ ký Ed25519 trên JSON manifest thô.

    Fail-closed: bất kỳ lý do nào không xác thực được (thiếu public key embed,
    cryptography lib không import được, signature/key sai định dạng, verify
    fail) đều trả về False để từ chối bản cập nhật. Đây là cánh cổng cuối
    trước khi `download_update` cho phép chạy installer; fail-open ở đây có
    nghĩa attacker MITM/CDN compromise có thể ship .exe tuỳ ý.
    """
    import warnings

    if _EMBEDDED_PUBLIC_B64 is None:
        warnings.warn(
            "Updater: thiếu Ed25519 public key — từ chối bản cập nhật chưa xác thực.",
            stacklevel=2,
        )
        return False

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_bytes = base64.b64decode(_EMBEDDED_PUBLIC_B64 + "==")
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)

        # signature được base64-encode (standard, không urlsafe)
        sig_bytes = base64.b64decode(manifest_signature + "==")
        pub_key.verify(sig_bytes, manifest_json_bytes)
        return True
    except Exception as exc:
        warnings.warn(f"Updater: chữ ký manifest không hợp lệ — {exc}", stacklevel=2)
        return False


# ── Public API ───────────────────────────────────────────────────────────────


def check_for_update(
    base_url: str,
    current_version: str,
    platform: str = "mac",
) -> UpdateInfo:
    """Kiểm tra phiên bản mới từ VPS.

    Gọi endpoint:
        GET <base_url>/api/v1/updates/manifest
            ?product=3T_READER&platform=<platform>&channel=stable&version=<current_version>

    Trả về UpdateInfo(available=False) nếu có bất kỳ lỗi mạng hoặc parse nào.

    Parameters
    ----------
    base_url:
        URL gốc của VPS, ví dụ ``"https://license.3t.com.vn"``.
    current_version:
        Phiên bản hiện tại của ứng dụng, ví dụ ``"1.2.0"``.
    platform:
        Nền tảng, mặc định ``"mac"``. Các giá trị hợp lệ: ``"mac"``, ``"win"``.
    """
    try:
        url = f"{base_url.rstrip('/')}/api/v1/updates/manifest"
        params = {
            "product": _PRODUCT,
            "platform": platform,
            "channel": _CHANNEL,
            "version": current_version,
        }
        data = _get(url, params=params)

        latest = data.get("version", "")
        if not latest:
            return UpdateInfo(available=False, current_version=current_version)

        available = _is_newer(latest, current_version)

        return UpdateInfo(
            available=available,
            current_version=current_version,
            latest_version=latest,
            download_url=data.get("download_url", ""),
            sha256=data.get("sha256", ""),
            signature=data.get("signature", ""),
            release_notes=data.get("release_notes", ""),
        )

    except Exception:
        return UpdateInfo(available=False, current_version=current_version)


def download_update(update_info: UpdateInfo) -> UpdateResult:
    """Tải xuống tệp cập nhật, xác thực SHA-256 và chữ ký Ed25519.

    Tệp được lưu vào thư mục tạm của hệ thống. Đường dẫn tệp được
    trả về trong ``UpdateResult.path`` nếu thành công.

    Parameters
    ----------
    update_info:
        Kết quả từ :func:`check_for_update`. Phải có
        ``available=True`` và ``download_url`` hợp lệ.
    """
    if not update_info.available or not update_info.download_url:
        return UpdateResult(success=False, error="Không có bản cập nhật để tải xuống.")

    try:
        import requests

        # Xác định tên tệp từ URL
        url_path = update_info.download_url.split("?")[0]
        filename = url_path.split("/")[-1] or "3t_reader_update"
        tmp_dir = Path(tempfile.mkdtemp(prefix="3t_reader_update_"))
        dest = tmp_dir / filename

        # Tải xuống theo từng chunk để tiết kiệm RAM
        resp = requests.get(
            update_info.download_url,
            headers={"User-Agent": "3T-Reader-Updater/1.0"},
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()

        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)

        # Xác thực SHA-256
        if update_info.sha256:
            actual_sha256 = _sha256_file(dest)
            if actual_sha256.lower() != update_info.sha256.lower():
                dest.unlink(missing_ok=True)
                return UpdateResult(
                    success=False,
                    error=f"SHA-256 không khớp: expected={update_info.sha256}, got={actual_sha256}",
                )

        # Xác thực chữ ký Ed25519 trên manifest (signature ký lên phần metadata,
        # không phải tệp nhị phân). Manifest bytes = JSON của các trường chính.
        if update_info.signature:
            import json as _json
            manifest_bytes = _json.dumps(
                {
                    "version": update_info.latest_version,
                    "download_url": update_info.download_url,
                    "sha256": update_info.sha256,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")

            if not _verify_signature(update_info.signature, manifest_bytes):
                dest.unlink(missing_ok=True)
                return UpdateResult(
                    success=False,
                    error="Chữ ký manifest không hợp lệ — tệp cập nhật bị từ chối.",
                )

        return UpdateResult(success=True, path=str(dest))

    except Exception as exc:
        return UpdateResult(success=False, error=str(exc))
