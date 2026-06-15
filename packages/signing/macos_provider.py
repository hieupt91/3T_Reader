"""macOS PKCS#11 signing provider — dò .dylib / .so middleware đã cài trên máy."""
from __future__ import annotations

import os
from pathlib import Path

from .provider import TokenInfo
from .shared import _safe_get_pkcs11_attr, extract_signer_identity_from_der, sign_pdf_with_session

# Tên thư viện middleware từ các CA Việt Nam và driver phổ biến trên macOS.
# Chỉ detect file ĐÃ CÀI trên máy; không bundle bất kỳ .dylib nào.
MACOS_PKCS11_CANDIDATES = [
    # VNPT
    "eps2003csp11.dylib",
    "vnpt_ca_pkcs11.dylib",
    # Viettel CA v6 (FeiTian ePass2003Auto)
    "viettel-ca_v6.dylib",
    "viettel-ca_v5.dylib",
    "viettel-ca.dylib",
    "ViettelCA.dylib",
    "ViettelPKCS11.dylib",
    # FPT
    "FPT_Token.dylib",
    # BKAV
    "BkavCAPKCS11.dylib",
    # SafeNet eToken (một số CA VN dùng)
    "eTPKCS11.dylib",
    "bit4xpki.dylib",
    "bit4ipki.dylib",
    "libbit4xpki.dylib",
    "libbit4ipki.dylib",
    # OpenSC — driver mã nguồn mở phổ biến trên macOS
    "opensc-pkcs11.so",
    "opensc-pkcs11.dylib",
]

_SEARCH_DIRS: list[str] = [
    "/usr/lib",
    "/usr/local/lib",
    "/usr/lib/pkcs11",
    "/usr/local/lib/pkcs11",
    "/opt/homebrew/lib",          # Apple Silicon Homebrew
    "/usr/local/Cellar",          # Intel Homebrew
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


def _ensure_token_manager_running() -> None:
    """Thử khởi động Viettel CA Token Manager nếu chưa chạy."""
    import subprocess

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
    """SigningProvider implementation for macOS, detects .dylib/.so middleware."""

    def __init__(self) -> None:
        self._last_error: str = ""

    def get_last_error(self) -> str:
        return self._last_error

    def detect_driver(self) -> str | None:
        self._last_error = ""
        import pkcs11 as p11

        loadable: list[str] = []   # lib nạp được (dù chưa có token)
        errors:   list[str] = []

        for path in _candidate_paths():
            try:
                lib = p11.lib(path)
                if any(True for _ in lib.get_tokens()):
                    return path          # ✅ có token → dùng ngay
                loadable.append(path)   # lib OK nhưng chưa thấy token
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {str(exc)[:80]}")

        # Có driver nhưng không thấy token → thử khởi động Token Manager
        if loadable:
            _ensure_token_manager_running()
            import time; time.sleep(2)
            for path in loadable:
                try:
                    lib = p11.lib(path)
                    if any(True for _ in lib.get_tokens()):
                        return path
                except Exception:
                    pass

            # Vẫn không thấy → báo lỗi cụ thể hơn
            names = ", ".join(os.path.basename(p) for p in loadable)
            self._last_error = (
                f"Đã tìm thấy thư viện ký số ({names}) nhưng không phát hiện USB Token.\n\n"
                "Vui lòng:\n"
                "  1. Cắm USB Token vào máy\n"
                "  2. Mở 'Viettel-CA Token Manager V6.0' (nếu chưa mở)\n"
                "  3. Rút USB ra rồi cắm lại, đợi 3 giây\n"
                "  4. Thử ký lại"
            )
            return None

        # Không tìm thấy driver nào
        detail = "\n".join(errors[:3]) if errors else (
            "Không tìm thấy thư viện PKCS#11 phù hợp.\n"
            "Vui lòng cài đặt driver từ nhà cung cấp chữ ký số."
        )
        self._last_error = (
            detail
            + "\n\n💡 Với Viettel CA v6 trên macOS:\n"
            "  • Tải và cài driver tại viettel-ca.vn\n"
            "  • Mở 'Viettel-CA Token Manager V6.0' trước khi ký"
        )
        return None

    def list_tokens(self, pin: str | None = None) -> list[TokenInfo]:
        info = self.get_token_info(pin)
        return [info] if info else []

    def select_token(self, token_info: TokenInfo | None) -> None:
        pass  # Token selection is simplified on macOS for now

    def get_token_info(self, pin: str | None = None) -> TokenInfo | None:
        lib_path = self.detect_driver()
        if not lib_path:
            return None
        try:
            import pkcs11 as p11
            from pkcs11.constants import Attribute, ObjectClass

            lib = p11.lib(lib_path)
            token = next(lib.get_tokens(), None)
            if token is None:
                return None

            open_kwargs: dict = {"rw": False}
            if pin:
                open_kwargs["user_pin"] = pin

            with token.open(**open_kwargs) as session:
                certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
                for cert in reversed(certs):
                    cert_der = _safe_get_pkcs11_attr(cert, Attribute.VALUE)
                    identity = extract_signer_identity_from_der(cert_der)
                    if identity:
                        return TokenInfo(
                            driver=os.path.basename(lib_path),
                            signer_name=identity.get("name", ""),
                            tax_code=identity.get("tax_code", ""),
                            driver_path=lib_path,
                            serial=str(getattr(token, "serial", "")).strip(),
                            cert_serial=identity.get("serial_hex", ""),
                        )
        except Exception:
            return None
        return None

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

        lib_path = self.detect_driver()
        if not lib_path:
            raise RuntimeError(
                "Không tìm thấy USB Token!\n"
                "Vui lòng cắm thiết bị chữ ký vào và thử lại.\n\n"
                f"Chi tiết: {self.get_last_error()}"
            )
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

        lib_path = self.detect_driver()
        if not lib_path:
            raise RuntimeError(
                "Không tìm thấy USB Token!\n"
                "Vui lòng cắm thiết bị chữ ký vào và thử lại.\n\n"
                f"Chi tiết: {self.get_last_error()}"
            )
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
