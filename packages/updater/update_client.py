from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_TIMEOUT = 15  # seconds

# Nhúng THẲNG danh sách key ở đây thay vì import từ
# packages.license_client.token_verifier - phiên bản import trước đó (xem
# git blame) bọc trong try/except rộng, và trên bản build đóng gói thật
# (PyInstaller + Nuitka, xem build_secure.py) import đó âm thầm raise và bị
# except nuốt mất, khiến _EMBEDDED_PUBLIC_KEYS_B64 luôn RỖNG -
# _verify_signature() luôn trả False, từ chối MỌI bản cập nhật hợp lệ, với
# MỌI user, không có cách nào tự phát hiện ra vì lỗi bị nuốt im lặng (xác
# nhận thực tế 14/08/2026: user thật thấy "Chữ ký manifest không hợp lệ"
# dù server ký đúng). Nhúng thẳng (không phụ thuộc import package khác) để
# updater không bao giờ phụ thuộc vào 1 chuỗi import xuyên package có thể
# vỡ âm thầm ở tầng đóng gói. PHẢI giữ giống hệt
# packages/license_client/token_verifier.py:_TRUSTED_ED25519_PUBLIC_KEYS_B64
# khi xoay key - test_update_client.py có check đối chiếu 2 danh sách này
# để bắt lệch ngay ở CI thay vì rơi vào đúng lỗi này lần nữa.
_EMBEDDED_PUBLIC_KEYS_B64: list[str] = [
    "y0jZ/wQHoQ+VvAQjYuhlmf0R63cMLgkTHp1wzXrcM08=",
    "PaBi70B9rG1UMSJUJrHElYYhZmNWYSLdL4hrotwWU8I=",
]


@dataclass
class UpdateInfo:
    available: bool
    current_version: str = ""
    latest_version: str = ""
    download_url: str = ""
    sha256: str = ""
    signature: str = ""
    release_notes: str = ""


@dataclass
class UpdateInfoV2:
    """B53: kết quả check_for_update_v2() - xem
    docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md. update_type "delta" chỉ khi
    server xác nhận base_version khớp VÀ đã bật delta_enabled; mọi trường
    hợp khác (kể cả lỗi mạng) coi như "full"/"none", KHÔNG bao giờ suy đoán
    delta khi thiếu thông tin."""

    available: bool
    update_type: str = "none"  # "full" | "delta" | "none"
    current_version: str = ""
    latest_version: str = ""
    base_version: str = ""
    download_url: str = ""
    sha256: str = ""
    signature: str = ""
    code_package_url: str = ""
    code_package_sha256: str = ""
    code_signature: str = ""
    release_notes: str = ""


@dataclass
class UpdateResult:
    success: bool
    path: str = ""
    error: str = ""


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
    core = version.strip().lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in core.split("."))
    except ValueError:
        return (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_semver(latest) > _parse_semver(current)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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

    # Thử lần lượt từng key tin cậy (hỗ trợ xoay key, cùng cách
    # verify_token_offline() làm với license token) - server có thể ký
    # bằng bất kỳ key nào còn hợp lệ trong danh sách.
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


def check_for_update(
    base_url: str,
    current_version: str,
    platform: str = "mac",
) -> UpdateInfo:
    try:
        url = f"{base_url.rstrip('/')}/api/v1/update/check"
        params = {
            "platform": platform,
            "current_version": current_version,
        }
        data = _get(url, params=params)

        latest = data.get("version") or data.get("latest_version") or ""
        if not latest:
            return UpdateInfo(available=False, current_version=current_version)

        return UpdateInfo(
            available=_is_newer(latest, current_version),
            current_version=current_version,
            latest_version=latest,
            download_url=data.get("download_url") or data.get("url") or "",
            sha256=data.get("sha256", ""),
            signature=data.get("signature", ""),
            release_notes=data.get("release_notes", ""),
        )
    except Exception:
        return UpdateInfo(available=False, current_version=current_version)


def download_update(
    update_info: UpdateInfo,
    progress_cb: Callable[[int], None] | None = None,
) -> UpdateResult:
    if not update_info.available or not update_info.download_url:
        return UpdateResult(success=False, error="Khong co ban cap nhat de tai xuong.")
    if not update_info.sha256:
        return UpdateResult(success=False, error="Manifest thieu SHA-256 - tu choi cap nhat.")
    if not update_info.signature:
        return UpdateResult(success=False, error="Manifest thieu chu ky xac thuc - tu choi cap nhat.")

    try:
        import json
        import requests

        url_path = update_info.download_url.split("?")[0]
        filename = url_path.split("/")[-1] or "3t_reader_update"
        tmp_dir = Path(tempfile.mkdtemp(prefix="3t_reader_update_"))
        dest = tmp_dir / filename

        resp = requests.get(
            update_info.download_url,
            headers={"User-Agent": "3T-Reader-Updater/1.0"},
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0) or 0)
        done = 0

        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(min(100, int(done * 100 / total)))

        actual_sha256 = _sha256_file(dest)
        if actual_sha256.lower() != update_info.sha256.lower():
            dest.unlink(missing_ok=True)
            return UpdateResult(
                success=False,
                error=f"SHA-256 khong khop: expected={update_info.sha256}, got={actual_sha256}",
            )

        manifest_bytes = json.dumps(
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
                error="Chu ky manifest khong hop le - tep cap nhat bi tu choi.",
            )

        if progress_cb:
            progress_cb(100)
        return UpdateResult(success=True, path=str(dest))
    except Exception as exc:
        return UpdateResult(success=False, error=str(exc))


def check_for_update_v2(
    base_url: str,
    current_version: str,
    current_base_version: str,
    platform: str = "windows",
) -> UpdateInfoV2:
    """B53: gọi /api/v2/update/check (route riêng, song song v1) - xem
    docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md. Bất kỳ lỗi nào (mạng, JSON
    hỏng, thiếu field) đều rơi về available=False/update_type="none" - CHƯA
    Việc ghi đè được thực hiện ở ``delta_runtime.py`` bởi helper process sau
    khi GUI thoát; module này chỉ tải/xác thực/gỡ nén để UI có thể fallback về
    full installer nếu bất kỳ bước nào thất bại."""
    try:
        url = f"{base_url.rstrip('/')}/api/v2/update/check"
        params = {
            "platform": platform,
            "current_version": current_version,
            "current_base_version": current_base_version,
        }
        data = _get(url, params=params)

        latest = data.get("latest_version") or ""
        update_type = data.get("update_type") or "none"
        if not latest or update_type == "none":
            return UpdateInfoV2(available=False, update_type="none", current_version=current_version, latest_version=latest)

        return UpdateInfoV2(
            available=True,
            update_type=update_type if update_type in ("delta", "full") else "full",
            current_version=current_version,
            latest_version=latest,
            base_version=data.get("base_version", ""),
            download_url=data.get("download_url", ""),
            sha256=data.get("sha256", ""),
            signature=data.get("signature", ""),
            code_package_url=data.get("code_package_url", ""),
            code_package_sha256=data.get("code_package_sha256", ""),
            code_signature=data.get("code_signature", ""),
            release_notes=data.get("release_notes", ""),
        )
    except Exception:
        return UpdateInfoV2(available=False, update_type="none", current_version=current_version)


def _safe_extract_code_package(archive_path: Path, extract_dir: Path) -> None:
    """Extract without Zip Slip/symlink entries; a signed archive is still
    untrusted input until its layout has been checked locally."""
    import stat
    import zipfile

    with zipfile.ZipFile(archive_path) as zf:
        members = zf.infolist()
        if not members:
            raise ValueError("Code package rong.")
        for member in members:
            candidate = Path(member.filename.replace("\\", "/"))
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError("Code package chua duong dan khong an toan.")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Code package khong duoc chua symbolic link.")
        for member in members:
            if member.is_dir():
                continue
            destination = extract_dir / Path(member.filename)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as source, destination.open("wb") as target:
                while chunk := source.read(65536):
                    target.write(chunk)


def stage_code_package(
    update_info: UpdateInfoV2,
    progress_cb: Callable[[int], None] | None = None,
) -> UpdateResult:
    """B53: tải + verify SHA-256 + verify code_signature + giải nén code
    package vào 1 thư mục TẠM riêng - KHÔNG ghi đè bất cứ gì vào bản cài
    hiện tại. `UpdateResult.path` trỏ tới thư mục đã giải nén sẵn sàng để 1
    bước "apply" (chưa viết - xem check_for_update_v2 docstring) dùng sau.
    Bất kỳ bước verify nào lỗi đều xoá sạch thư mục tạm và trả lỗi - caller
    PHẢI tự fallback sang download_update() (full installer) khi
    success=False, không có cách nào khác để hoàn tất update từ kết quả lỗi
    này."""
    if update_info.update_type != "delta" or not update_info.code_package_url:
        return UpdateResult(success=False, error="Khong co code package de tai.")
    if not update_info.code_package_sha256:
        return UpdateResult(success=False, error="Manifest thieu SHA-256 code package - tu choi cap nhat.")
    if not update_info.code_signature:
        return UpdateResult(success=False, error="Manifest thieu chu ky code package - tu choi cap nhat.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="3t_reader_codepkg_"))
    try:
        import json
        import requests

        url_path = update_info.code_package_url.split("?")[0]
        filename = url_path.split("/")[-1] or "code_package.zip"
        archive_path = tmp_dir / filename

        resp = requests.get(
            update_info.code_package_url,
            headers={"User-Agent": "3T-Reader-Updater/1.0"},
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0) or 0)
        done = 0

        with archive_path.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(min(90, int(done * 90 / total)))

        actual_sha256 = _sha256_file(archive_path)
        if actual_sha256.lower() != update_info.code_package_sha256.lower():
            raise ValueError(f"SHA-256 code package khong khop: expected={update_info.code_package_sha256}, got={actual_sha256}")

        code_payload_bytes = json.dumps(
            {
                "base_version": update_info.base_version,
                "code_package_sha256": update_info.code_package_sha256,
                "code_package_url": update_info.code_package_url,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if not _verify_signature(update_info.code_signature, code_payload_bytes):
            raise ValueError("Chu ky code package khong hop le.")

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()
        _safe_extract_code_package(archive_path, extract_dir)

        if progress_cb:
            progress_cb(100)
        return UpdateResult(success=True, path=str(extract_dir))
    except Exception as exc:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
        return UpdateResult(success=False, error=str(exc))
