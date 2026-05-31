from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_TIMEOUT = 15  # seconds

_EMBEDDED_PUBLIC_B64: Optional[str] = None
try:
    from packages.license_client.token_verifier import _ED25519_PUBLIC_B64  # type: ignore[import]

    _EMBEDDED_PUBLIC_B64 = _ED25519_PUBLIC_B64
except Exception:
    pass


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

    if _EMBEDDED_PUBLIC_B64 is None:
        warnings.warn(
            "Updater: missing embedded Ed25519 public key; refusing unverified update.",
            stacklevel=2,
        )
        return False

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_bytes = base64.b64decode(_EMBEDDED_PUBLIC_B64 + "==")
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        sig_bytes = base64.b64decode(manifest_signature + "==")
        pub_key.verify(sig_bytes, manifest_json_bytes)
        return True
    except Exception as exc:
        warnings.warn(f"Updater: invalid manifest signature: {exc}", stacklevel=2)
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
