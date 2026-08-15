"""macOS PKCS#11 signing provider — dò .dylib / .so middleware đã cài trên máy."""
from __future__ import annotations

import os
import time
import subprocess
import concurrent.futures
from pathlib import Path

from .provider import TokenInfo
from .shared import _safe_get_pkcs11_attr, extract_signer_identity_from_der, sign_pdf_with_session

MACOS_PKCS11_CANDIDATES = [
    "eps2003csp11.dylib",
    "vnpt_ca_pkcs11.dylib",
    "viettel-ca_v6.dylib",
    "viettel-ca_v5.dylib",
    "viettel-ca.dylib",
    "ViettelCA.dylib",
    "ViettelPKCS11.dylib",
    "FPT_Token.dylib",
    "BkavCAPKCS11.dylib",
    "eTPKCS11.dylib",
    "bit4xpki.dylib",
    "bit4ipki.dylib",
    "libbit4xpki.dylib",
    "libbit4ipki.dylib",
    "opensc-pkcs11.so",
    "opensc-pkcs11.dylib",
]

_SEARCH_DIRS: list[str] = [
    "/usr/lib",
    "/usr/local/lib",
    "/usr/lib/pkcs11",
    "/usr/local/lib/pkcs11",
    "/opt/homebrew/lib",
    "/usr/local/Cellar",
    str(Path.home() / "Library" / "PKCS11"),
    "/Library/Security/tokend",
]

def _candidate_paths() -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for lib_name in MACOS_PKCS11_CANDIDATES:
        for d in _SEARCH_DIRS:
            p = os.path.join(d, lib_name)
            if os.path.exists(p) and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths

def _is_usb_token_plugged() -> bool:
    try:
        out = subprocess.check_output(["ioreg", "-p", "IOUSB", "-w0"], text=True).lower()
        keywords = ["token", "smartcard", "ccid", "viettel", "vnpt", "epass", "mca", "bit4", "safenet", "aladdin", "gemalto", "athena", "fpt", "bkav"]
        return any(k in out for k in keywords)
    except Exception:
        return True

def _ensure_token_manager_running() -> None:
    token_manager = "/Applications/Viettel-CA Token Manager V6.0.app"
    if not os.path.exists(token_manager):
        return
    try:
        result = subprocess.run(
            ["pgrep", "-f", "Viettel-CA Token Manager"],
            capture_output=True,
        )
        if result.returncode != 0:
            subprocess.Popen(["open", token_manager])
    except Exception:
        pass

class MacOSPkcs11Provider:
    def __init__(self) -> None:
        self._last_error: str = ""
        self._tokens_cache: list[TokenInfo] = []
        self._tokens_cache_until: float = 0
        self._tokens_cache_error: str = ""
        self._selected_token: TokenInfo | None = None

    def get_last_error(self) -> str:
        return self._last_error

    def detect_driver(self) -> str | None:
        if self._selected_token and self._selected_token.driver_path:
            return self._selected_token.driver_path
        tokens = self.list_tokens()
        if tokens:
            self._selected_token = tokens[0]
            return tokens[0].driver_path
        return None

    def list_tokens(self, pin: str | None = None) -> list[TokenInfo]:
        now = time.monotonic()
        
        # Chỉ quét khi có USB Token thực sự được cắm vào máy (tránh bật app Viettel liên tục)
        if not _is_usb_token_plugged():
            self._tokens_cache = []
            self._tokens_cache_error = "Không tìm thấy USB Token. Vui lòng cắm thiết bị."
            self._last_error = self._tokens_cache_error
            self._tokens_cache_until = now + 1.0
            return []

        if now < self._tokens_cache_until:
            self._last_error = self._tokens_cache_error
            return list(self._tokens_cache)

        self._last_error = ""
        
        from packages.signing.windows_provider import _probe_driver_tokens
        
        tokens: list[TokenInfo] = []
        errors: list[str] = []
        valid_paths = _candidate_paths()

        def probe_path(path):
            try:
                return path, _probe_driver_tokens(path), None
            except Exception as e:
                return path, None, str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(probe_path, valid_paths))

        for path, probe_result, probe_exc in results:
            if probe_exc:
                errors.append(f"{os.path.basename(path)}: {probe_exc}")
                continue
            if not probe_result:
                continue
            token_dicts, error_msg = probe_result
            if error_msg and error_msg != "NO_TOKEN":
                errors.append(f"{os.path.basename(path)}: {error_msg}")
            for tdict in token_dicts:
                tokens.append(TokenInfo(
                    driver=os.path.basename(path),
                    signer_name=tdict.get("signer_name", ""),
                    tax_code=tdict.get("tax_code", ""),
                    driver_path=path,
                    serial=tdict.get("serial", ""),
                    cert_serial=tdict.get("cert_serial", ""),
                ))

        if not tokens and valid_paths:
            _ensure_token_manager_running()

        self._tokens_cache = tokens
        # Cache 60s nếu token đang cắm, vì nếu rút ra ioreg sẽ tự động bắt được và xoá cache ngay!
        self._tokens_cache_until = now + 60.0
        
        if not tokens:
            detail = "\n".join(errors[:3]) if errors else (
                "Không tìm thấy thư viện PKCS#11 phù hợp.\n"
                "Vui lòng cài đặt driver từ nhà cung cấp chữ ký số."
            )
            self._tokens_cache_error = (
                detail
                + "\n\n💡 Với Viettel CA v6 trên macOS:\n"
                "  • Tải và cài driver tại viettel-ca.vn\n"
                "  • Mở 'Viettel-CA Token Manager V6.0' trước khi ký"
            )
            self._last_error = self._tokens_cache_error

        return list(tokens)

    def select_token(self, token_info: TokenInfo | None) -> None:
        self._selected_token = token_info

    def get_token_info(self, pin: str | None = None) -> TokenInfo | None:
        tokens = self.list_tokens(pin)
        return tokens[0] if tokens else None

    async def sign_pdf(
        self,
        input_path: str,
        output_path: str,
        pin: str,
        *,
        signer_name: str,
        page_number: int,
        box: tuple[float, float, float, float],
        field_name: str | None = None,
        reason: str | None = None,
        location: str | None = None,
        contact_info: str | None = None,
        tsa_url: str | None = None,
        enable_ltv: bool = False,
    ) -> None:
        import pkcs11 as p11

        token_info = self._selected_token or self.get_token_info()
        if not token_info or not token_info.driver_path:
            raise RuntimeError(
                "Không tìm thấy USB Token!\n"
                "Vui lòng cắm thiết bị chữ ký vào và thử lại.\n\n"
                f"Chi tiết: {self.get_last_error()}"
            )
        lib_path = token_info.driver_path
        lib = p11.lib(lib_path)
        token = next(lib.get_tokens())
        session = None
        try:
            session = token.open(user_pin=pin, rw=False)
            await sign_pdf_with_session(
                session,
                lib_path,
                input_path,
                output_path,
                signer_name=signer_name,
                page_number=page_number,
                box=box,
                field_name=field_name,
                reason=reason,
                location=location,
                contact_info=contact_info,
                tsa_url=tsa_url,
                enable_ltv=enable_ltv,
            )
        finally:
            if session is not None:
                session.close()

    async def sign_pdf_batch(
        self,
        jobs: list[dict],
        pin: str,
        *,
        tsa_url: str | None = None,
        enable_ltv: bool = False,
    ) -> None:
        import pkcs11 as p11

        token_info = self._selected_token or self.get_token_info()
        if not token_info or not token_info.driver_path:
            raise RuntimeError(
                "Không tìm thấy USB Token!\n"
                "Vui lòng cắm thiết bị chữ ký vào và thử lại.\n\n"
                f"Chi tiết: {self.get_last_error()}"
            )
        lib_path = token_info.driver_path
        lib = p11.lib(lib_path)
        token = next(lib.get_tokens())
        session = None
        try:
            session = token.open(user_pin=pin, rw=False)
            for job in jobs:
                try:
                    await sign_pdf_with_session(
                        session,
                        lib_path,
                        job["input_path"],
                        job["output_path"],
                        signer_name=job.get("signer_name", ""),
                        page_number=job.get("page_number", 1),
                        box=job.get("box", (50, 50, 300, 100)),
                        field_name=job.get("field_name"),
                        reason=job.get("reason"),
                        location=job.get("location"),
                        contact_info=job.get("contact_info"),
                        tsa_url=tsa_url,
                        enable_ltv=enable_ltv,
                    )
                except Exception as e:
                    raise RuntimeError(f"Lỗi khi ký file {job.get('input_path')}: {e}")
        finally:
            if session is not None:
                session.close()
