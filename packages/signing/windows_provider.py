"""Windows PKCS#11 signing provider — dò .dll trong System32 / SysWOW64."""
from __future__ import annotations

import os
from pathlib import Path

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

WINDOWS_PKCS11_PATHS_ENV = "THREET_READER_WINDOWS_PKCS11_PATHS"
WINDOWS_VENDOR_DIR_HINTS = (
    "viettel",
    "vnpt",
    "fpt",
    "bkav",
    "safenet",
    "etoken",
    "token",
    "pkcs11",
    "smartcard",
    "eps2003",
)


def _split_configured_paths(value: str | None) -> list[str]:
    if not value:
        return []
    return [entry.strip().strip('"') for entry in value.split(os.pathsep) if entry.strip()]


def _candidate_search_dirs() -> list[str]:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    configured_entries = _split_configured_paths(os.environ.get(WINDOWS_PKCS11_PATHS_ENV))

    search_dirs = [
        os.path.join(system_root, "System32"),
        os.path.join(system_root, "SysWOW64"),
    ]
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if base:
            search_dirs.append(base)

    for entry in configured_entries:
        if os.path.isdir(entry):
            search_dirs.append(entry)
        else:
            parent = str(Path(entry).parent)
            if parent and parent not in (".", ""):
                search_dirs.append(parent)

    deduped: list[str] = []
    seen: set[str] = set()
    for directory in search_dirs:
        normalized = os.path.normcase(os.path.normpath(directory))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(directory)
    return deduped


def _candidate_vendor_dirs(base_dir: str) -> list[str]:
    dirs = [base_dir]
    try:
        with os.scandir(base_dir) as entries:
            first_level = [
                entry.path
                for entry in entries
                if entry.is_dir() and any(hint in entry.name.lower() for hint in WINDOWS_VENDOR_DIR_HINTS)
            ]
    except OSError:
        return dirs

    dirs.extend(first_level)
    for vendor_dir in first_level:
        try:
            with os.scandir(vendor_dir) as entries:
                dirs.extend(entry.path for entry in entries if entry.is_dir())
        except OSError:
            continue

    deduped: list[str] = []
    seen: set[str] = set()
    for directory in dirs:
        normalized = os.path.normcase(os.path.normpath(directory))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(directory)
    return deduped


def _candidate_paths() -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    configured_entries = _split_configured_paths(os.environ.get(WINDOWS_PKCS11_PATHS_ENV))

    for entry in configured_entries:
        if os.path.isfile(entry):
            normalized = os.path.normcase(os.path.normpath(entry))
            if normalized not in seen:
                seen.add(normalized)
                paths.append(entry)

    search_dirs = _candidate_search_dirs()
    for dll in WINDOWS_PKCS11_CANDIDATES:
        for root_dir in search_dirs:
            for d in _candidate_vendor_dirs(root_dir):
                p = os.path.join(d, dll)
                normalized = os.path.normcase(os.path.normpath(p))
                if os.path.exists(p) and normalized not in seen:
                    seen.add(normalized)
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
