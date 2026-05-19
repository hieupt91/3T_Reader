"""Windows PKCS#11 signing provider — dò .dll trong System32 / SysWOW64."""
from __future__ import annotations

import os

from .provider import TokenInfo
from .shared import _safe_get_pkcs11_attr, extract_signer_identity_from_der, sign_pdf_with_session

# Danh sách DLL middleware phổ biến từ các CA Việt Nam trên Windows
WINDOWS_PKCS11_CANDIDATES = [
    "eps2003csp11.dll",
    "vnpt_ca_pkcs11.dll",
    "FPT_Token.dll",
    "acospkcs11.dll",
    "BkavCAPKCS11.dll",
    "eTPKCS11.dll",
    "eps2003csp11v2.dll",
    "cvP11.dll",
    "ViettelCA.dll",
    "ViettelPKCS11.dll",
    "viettelca11.dll",
    "viettel-ca_v6.dll",
    "viettel-ca_v6_s.dll",
]


def _candidate_paths() -> list[str]:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    search_dirs = [
        os.path.join(system_root, "System32"),
        os.path.join(system_root, "SysWOW64"),
    ]
    paths: list[str] = []
    seen: set[str] = set()
    for dll in WINDOWS_PKCS11_CANDIDATES:
        for d in search_dirs:
            p = os.path.join(d, dll)
            if os.path.exists(p) and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths


class WindowsPkcs11Provider:
    """SigningProvider implementation for Windows, detects .dll middleware."""

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
                msg = str(exc).lower()
                name = os.path.basename(path)
                if "error 126" in msg:
                    errors.append(f"{name}: lỗi 126 (thiếu DLL phụ thuộc hoặc sai x86/x64)")
                elif "module could not be found" in msg:
                    errors.append(f"{name}: không tìm thấy module")
                else:
                    errors.append(f"{name}: {str(exc)[:120]}")

        self._last_error = (
            "\n".join(errors[:4])
            if errors
            else "Không tìm thấy thư viện PKCS#11 phù hợp trong hệ thống."
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
