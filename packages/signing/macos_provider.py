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
    # Viettel
    "ViettelCA.dylib",
    "ViettelPKCS11.dylib",
    # FPT
    "FPT_Token.dylib",
    # BKAV
    "BkavCAPKCS11.dylib",
    # SafeNet eToken (một số CA VN dùng)
    "eTPKCS11.dylib",
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


class MacOSPkcs11Provider:
    """SigningProvider implementation for macOS, detects .dylib/.so middleware."""

    def __init__(self) -> None:
        self._last_error: str = ""

    def get_last_error(self) -> str:
        return self._last_error

    def detect_driver(self) -> str | None:
        self._last_error = ""
        errors: list[str] = []
        for path in _candidate_paths():
            try:
                import pkcs11 as p11

                lib = p11.lib(path)
                if any(True for _ in lib.get_tokens()):
                    return path
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {str(exc)[:120]}")

        self._last_error = (
            "\n".join(errors[:4])
            if errors
            else (
                "Không tìm thấy thư viện PKCS#11 phù hợp trong hệ thống.\n"
                "Vui lòng cài đặt driver / middleware cho USB Token từ nhà cung cấp chữ ký số."
            )
        )
        return None

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
        session = token.open(user_pin=pin, rw=False)
        try:
            await sign_pdf_with_session(
                session,
                lib_path,
                input_path,
                output_path,
                signer_name=signer_name,
                page_number=page_number,
                box=box,
            )
        finally:
            session.close()
