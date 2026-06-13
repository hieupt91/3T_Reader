"""Windows PKCS#11 signing provider."""
from __future__ import annotations

import os
import json
import re
import struct
import subprocess
import concurrent.futures
import sys
import time
from pathlib import Path

from .provider import TokenInfo
from .shared import _safe_get_pkcs11_attr, extract_signer_identity_from_der, sign_pdf_with_session

try:
    import winreg as _winreg  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - non-Windows platforms
    _winreg = None


WINDOWS_PKCS11_CANDIDATES = [
    "eps2003csp11.dll",
    "eps2003csp11v2.dll",
    "vnpt_ca_pkcs11.dll",
    "vnptca_pkcs11.dll",
    "vnptca_p11_v8.dll",
    "vnptca_p11_v8_s.dll",
    "vnpt-ca_v6.dll",
    "vnpt-ca_v6_s.dll",
    "FPT_Token.dll",
    "acospkcs11.dll",
    "BkavCAPKCS11.dll",
    "eTPKCS11.dll",
    "cvP11.dll",
    "ViettelCA.dll",
    "ViettelPKCS11.dll",
    "viettelca11.dll",
    "viettel-ca_v6.dll",
    "viettel-ca_v6_s.dll",
    "bit4xpki.dll",
    "bit4ipki.dll",
    "bit4id.dll",
    "IDPrimePKCS11.dll",
    "aetpkss1.dll",
]

WINDOWS_PKCS11_PATHS_ENV = "THREET_READER_WINDOWS_PKCS11_PATHS"
WINDOWS_VENDOR_DIR_HINTS = (
    "viettel",
    "vnpt",
    "fpt",
    "bkav",
    "newca",
    "easyca",
    "efy",
    "nacencomm",
    "cyberlotus",
    "smartsign",
    "mobifone",
    "vinaphone",
    "vietnampost",
    "ca2",
    "safenet",
    "etoken",
    "token",
    "pkcs11",
    "smartcard",
    "eps2003",
    "bit4",
    "idprime",
)
WINDOWS_GENERIC_DLL_HINTS = (
    "pkcs",
    "csp11",
    "cryptoki",
    "etoken",
    "aetpk",
    "idprime",
    "bit4",
    "pki",
    "usbtoken",
    "viettel",
    "vnpt",
    "fpt",
    "bkav",
    "newca",
    "easyca",
    "efy",
    "nacencomm",
    "cyberlotus",
    "smartsign",
)
WINDOWS_REGISTRY_HINTS = WINDOWS_VENDOR_DIR_HINTS + (
    "cryptoki",
    "token manager",
    "digital signature",
    "usb token",
    "smart card",
)
WINDOWS_REGISTRY_UNINSTALL_KEYS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
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
    for env_name in (
        "ProgramFiles",
        "ProgramFiles(x86)",
        "CommonProgramFiles",
        "CommonProgramFiles(x86)",
        "ProgramData",
        "LOCALAPPDATA",
    ):
        base = os.environ.get(env_name)
        if base:
            search_dirs.append(base)

    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        path_dir = path_dir.strip().strip('"')
        if path_dir:
            search_dirs.append(path_dir)

    for entry in configured_entries:
        if os.path.isdir(entry):
            search_dirs.append(entry)
        else:
            parent = str(Path(entry).parent)
            if parent and parent not in (".", ""):
                search_dirs.append(parent)

    return _dedupe_paths(search_dirs)


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

    return _dedupe_paths(dirs)


def _registry_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore").strip()
        except Exception:
            return value.hex().upper()
    return str(value).strip()


def _registry_candidate_dir(value) -> str | None:
    text = _registry_text(value)
    if not text:
        return None

    text = text.strip().strip('"').strip()
    if not text:
        return None

    quoted = re.search(r'"([^"]+)"', text)
    candidates: list[str] = []
    if quoted:
        candidates.append(quoted.group(1))

    head = text.split(",", 1)[0].strip()
    if head:
        candidates.append(head.strip('"'))

    head = text.split(" ", 1)[0].strip()
    if head:
        candidates.append(head.strip('"'))

    for candidate in candidates:
        candidate = os.path.expandvars(os.path.expanduser(candidate))
        if os.path.isdir(candidate):
            return candidate
        if os.path.isfile(candidate):
            parent = str(Path(candidate).parent)
            if parent and os.path.isdir(parent):
                return parent
        if candidate.lower().endswith((".exe", ".dll", ".ocx", ".sys")):
            parent = str(Path(candidate).parent)
            if parent and os.path.isdir(parent):
                return parent
    return None


def _registry_install_dirs() -> list[str]:
    if _winreg is None:
        return []

    dirs: list[str] = []
    seen: set[str] = set()

    def add(path: str | None) -> None:
        if not path:
            return
        normalized = os.path.normcase(os.path.normpath(path))
        if normalized in seen:
            return
        if os.path.isdir(path):
            seen.add(normalized)
            dirs.append(path)

    for root in (_winreg.HKEY_LOCAL_MACHINE, _winreg.HKEY_CURRENT_USER):
        for uninstall_key in WINDOWS_REGISTRY_UNINSTALL_KEYS:
            try:
                with _winreg.OpenKey(root, uninstall_key) as uninstall_root:
                    subkey_count = _winreg.QueryInfoKey(uninstall_root)[0]
                    for index in range(subkey_count):
                        try:
                            subkey_name = _winreg.EnumKey(uninstall_root, index)
                        except OSError:
                            continue
                        try:
                            with _winreg.OpenKey(uninstall_root, subkey_name) as app_key:
                                display_name = _registry_text(_registry_value(app_key, "DisplayName"))
                                publisher = _registry_text(_registry_value(app_key, "Publisher"))
                                haystack = f"{display_name} {publisher}".lower()
                                if haystack and not any(hint in haystack for hint in WINDOWS_REGISTRY_HINTS):
                                    continue

                                for value_name in (
                                    "InstallLocation",
                                    "DisplayIcon",
                                    "UninstallString",
                                    "QuietUninstallString",
                                    "InstallSource",
                                ):
                                    add(_registry_candidate_dir(_registry_value(app_key, value_name)))
                        except OSError:
                            continue
            except OSError:
                continue

    return _dedupe_paths(dirs)


def _registry_value(key, value_name: str):
    try:
        value, _ = _winreg.QueryValueEx(key, value_name)
        return value
    except OSError:
        return None


def _candidate_paths() -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    configured_entries = _split_configured_paths(os.environ.get(WINDOWS_PKCS11_PATHS_ENV))

    def add(path: str) -> None:
        normalized = os.path.normcase(os.path.normpath(path))
        if normalized not in seen and (
            os.path.isfile(path)
            or (path.lower().endswith(".dll") and os.path.exists(path))
        ):
            seen.add(normalized)
            paths.append(path)

    for entry in configured_entries:
        add(entry)

    for root_dir in _registry_install_dirs():
        for directory in _candidate_vendor_dirs(root_dir):
            for dll in WINDOWS_PKCS11_CANDIDATES:
                add(os.path.join(directory, dll))
            for path in _generic_pkcs11_dlls(directory, recursive=True):
                add(path)

    for dll in WINDOWS_PKCS11_CANDIDATES:
        for root_dir in _candidate_search_dirs():
            for directory in _candidate_vendor_dirs(root_dir):
                add(os.path.join(directory, dll))

    for root_dir in _candidate_search_dirs():
        for directory in _candidate_vendor_dirs(root_dir):
            for path in _generic_pkcs11_dlls(directory):
                add(path)

    return paths


def _generic_pkcs11_dlls(directory: str, *, recursive: bool = False, max_depth: int = 4) -> list[str]:
    matches: list[str] = []

    def looks_like_pkcs11_dll(name: str) -> bool:
        lowered = name.lower()
        if not lowered.endswith(".dll"):
            return False
        stem = lowered[:-4]
        return (
            any(hint in lowered for hint in WINDOWS_GENERIC_DLL_HINTS)
            or stem.endswith("p11")
            or "_p11" in stem
            or "-p11" in stem
            or "p11_" in stem
            or "p11-" in stem
        )

    def scan(path: str, depth: int) -> None:
        try:
            entries = list(os.scandir(path))
        except OSError:
            return
        for entry in entries:
            try:
                if entry.is_file() and looks_like_pkcs11_dll(entry.name):
                    matches.append(entry.path)
                elif recursive and depth < max_depth and entry.is_dir():
                    scan(entry.path, depth + 1)
            except OSError:
                continue

    scan(directory, 0)
    return matches


def _dedupe_paths(paths: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = os.path.normcase(os.path.normpath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(path)
    return deduped


def _dll_arch_matches_process(path: str) -> tuple[bool, str]:
    try:
        with open(path, "rb") as fh:
            if fh.read(2) != b"MZ":
                return True, ""
            fh.seek(0x3C)
            pe_offset = struct.unpack("<I", fh.read(4))[0]
            fh.seek(pe_offset)
            if fh.read(4) != b"PE\x00\x00":
                return True, ""
            machine = struct.unpack("<H", fh.read(2))[0]
    except OSError:
        return True, ""
    except Exception:
        return True, ""

    process_bits = 64 if sys.maxsize > 2**32 else 32
    dll_bits = {
        0x014C: 32,
        0x8664: 64,
        0xAA64: 64,
    }.get(machine)
    if dll_bits and dll_bits != process_bits:
        return False, f"DLL {dll_bits}-bit khong tuong thich voi app/Python {process_bits}-bit"
    return True, ""


def _probe_driver_for_token(path: str) -> tuple[bool, str]:
    code = (
        "import sys\n"
        "try:\n"
        "    import pkcs11 as p11\n"
        "    lib = p11.lib(sys.argv[1])\n"
        "    print('TOKEN' if any(True for _ in lib.get_tokens()) else 'NO_TOKEN')\n"
        "except Exception as exc:\n"
        "    print('ERROR:' + str(exc))\n"
    )
    command = (
        [sys.executable, "--pkcs11-probe-token", path]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-c", code, path]
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return False, "driver phan hoi qua lau"
    except Exception as exc:
        return False, str(exc)

    stdout_lines = result.stdout.splitlines()
    if "TOKEN" in stdout_lines:
        return True, ""

    combined = "\n".join(
        part.strip()
        for part in (result.stdout, result.stderr)
        if part and part.strip()
    )
    if combined.startswith("ERROR:"):
        return False, combined[6:][:160]
    return False, combined[:160] if combined else "NO_TOKEN"


def probe_driver_for_token_worker_main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("ERROR:missing driver path")
        return 2
    try:
        import pkcs11 as p11

        lib = p11.lib(args[0])
        print("TOKEN" if any(True for _ in lib.get_tokens()) else "NO_TOKEN")
        return 0
    except Exception as exc:
        print("ERROR:" + str(exc))
        return 1


def _probe_driver_tokens(path: str) -> tuple[list[dict], str]:
    code = r'''
import json
import sys

def clean(value):
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", errors="ignore").strip()
            if text and all(31 < ord(ch) < 127 for ch in text):
                return text
        except Exception:
            pass
        return value.hex().upper()
    return str(value or "").strip()

try:
    import pkcs11 as p11
    from pkcs11.constants import Attribute, ObjectClass
    from packages.signing.shared import _safe_get_pkcs11_attr, extract_signer_identity_from_der

    lib_path = sys.argv[1]
    lib = p11.lib(lib_path)
    tokens = []
    for index, token in enumerate(lib.get_tokens()):
        signer_name = ""
        tax_code = ""
        issuer_name = ""
        cert_serial = ""
        try:
            with token.open(rw=False) as session:
                certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
                for cert in reversed(certs):
                    identity = extract_signer_identity_from_der(_safe_get_pkcs11_attr(cert, Attribute.VALUE))
                    if identity:
                        signer_name = identity.get("name", "")
                        tax_code = identity.get("tax_code", "")
                        issuer_name = identity.get("issuer_name", "")
                        cert_serial = identity.get("serial_hex", "")
                        break
        except Exception:
            pass
        tokens.append({
            "index": index,
            "label": clean(getattr(token, "label", "")),
            "serial": clean(getattr(token, "serial", "")),
            "manufacturer": clean(getattr(token, "manufacturer_id", "")),
            "model": clean(getattr(token, "model", "")),
            "signer_name": signer_name,
            "tax_code": tax_code,
            "issuer_name": issuer_name,
            "cert_serial": cert_serial,
        })
    print(json.dumps({"tokens": tokens}, ensure_ascii=True))
except Exception as exc:
    print(json.dumps({"error": str(exc)}, ensure_ascii=True))
'''
    command = (
        [sys.executable, "--pkcs11-list-tokens", path]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-c", code, path]
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return [], "driver phan hoi qua lau"
    except Exception as exc:
        return [], str(exc)

    output = (result.stdout or "").strip().splitlines()
    if not output:
        detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
        return [], detail[:160] if detail else "NO_TOKEN"
    try:
        payload = json.loads(output[-1])
    except Exception:
        detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
        return [], detail[:160] if detail else "NO_TOKEN"
    if payload.get("error"):
        return [], str(payload["error"])[:160]
    return list(payload.get("tokens") or []), ""


def probe_driver_tokens_worker_main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(json.dumps({"error": "missing driver path"}, ensure_ascii=True))
        return 2
    try:
        import pkcs11 as p11
        from pkcs11.constants import Attribute, ObjectClass

        lib = p11.lib(args[0])
        tokens = []
        for index, token in enumerate(lib.get_tokens()):
            signer_name = ""
            tax_code = ""
            issuer_name = ""
            cert_serial = ""
            try:
                with token.open(rw=False) as session:
                    certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
                    for cert in reversed(certs):
                        identity = extract_signer_identity_from_der(_safe_get_pkcs11_attr(cert, Attribute.VALUE))
                        if identity:
                            signer_name = identity.get("name", "")
                            tax_code = identity.get("tax_code", "")
                            issuer_name = identity.get("issuer_name", "")
                            cert_serial = identity.get("serial_hex", "")
                            break
            except Exception:
                pass
            tokens.append({
                "index": index,
                "label": _clean_token_value(getattr(token, "label", "")),
                "serial": _clean_token_value(getattr(token, "serial", "")),
                "manufacturer": _clean_token_value(getattr(token, "manufacturer_id", "")),
                "model": _clean_token_value(getattr(token, "model", "")),
                "signer_name": signer_name,
                "tax_code": tax_code,
                "issuer_name": issuer_name,
                "cert_serial": cert_serial,
            })
        print(json.dumps({"tokens": tokens}, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 1


def _clean_token_value(value) -> str:
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", errors="ignore").strip()
            if text and all(31 < ord(ch) < 127 for ch in text):
                return text
        except Exception:
            pass
        return value.hex().upper()
    return str(value or "").strip()


def _append_unique_error(errors: list[str], msg: str) -> None:
    if msg and msg not in errors:
        errors.append(msg)


def _get_token_by_info(lib, token_info: TokenInfo):
    tokens = list(lib.get_tokens())
    for token in tokens:
        serial = _clean_token_value(getattr(token, "serial", ""))
        if token_info.serial and serial == token_info.serial:
            return token
    if 0 <= token_info.token_index < len(tokens):
        return tokens[token_info.token_index]
    return tokens[0] if tokens else None


def _token_info_from_payload(lib_path: str, payload: dict) -> TokenInfo:
    return TokenInfo(
        driver=os.path.basename(lib_path),
        signer_name=str(payload.get("signer_name") or ""),
        tax_code=str(payload.get("tax_code") or ""),
        driver_path=lib_path,
        token_index=int(payload.get("index") or 0),
        token_label=str(payload.get("label") or ""),
        serial=str(payload.get("serial") or ""),
        manufacturer=str(payload.get("manufacturer") or ""),
        model=str(payload.get("model") or ""),
        issuer_name=str(payload.get("issuer_name") or ""),
        cert_serial=str(payload.get("cert_serial") or ""),
    )


class WindowsPkcs11Provider:
    """SigningProvider implementation for Windows."""

    def __init__(self) -> None:
        self._last_error: str = ""
        self._selected_token: TokenInfo | None = None
        self._tokens_cache: list[TokenInfo] = []
        self._tokens_cache_error: str = ""
        self._tokens_cache_until: float = 0.0
        self._tokens_cache_ttl_seconds: float = 8.0

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
        if now < self._tokens_cache_until:
            self._last_error = self._tokens_cache_error
            return list(self._tokens_cache)

        self._last_error = ""
        errors: list[str] = []
        tokens: list[TokenInfo] = []

        paths = list(_candidate_paths())
        valid_paths = []
        for path in paths:
            arch_ok, arch_error = _dll_arch_matches_process(path)
            if not arch_ok:
                _append_unique_error(errors, f"{os.path.basename(path)}: {arch_error}")
            else:
                valid_paths.append(path)

        def probe_path(path):
            try:
                return path, _probe_driver_tokens(path), None
            except Exception as exc:
                return path, None, exc

        if valid_paths:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(valid_paths)) as executor:
                futures = [executor.submit(probe_path, p) for p in valid_paths]
                for future in concurrent.futures.as_completed(futures):
                    path, result, exc = future.result()
                    name = os.path.basename(path)
                    if exc:
                        msg = str(exc).lower()
                        if "error 126" in msg:
                            _append_unique_error(errors, f"{name}: loi 126 (thieu DLL phu thuoc hoac sai x86/x64)")
                        elif "not a valid win32" in msg or "bad exe format" in msg or "%1 is not a valid win32" in msg:
                            _append_unique_error(errors, f"{name}: sai kien truc x86/x64 so voi Python/app dang chay")
                        elif "module could not be found" in msg:
                            _append_unique_error(errors, f"{name}: khong tim thay module")
                        else:
                            _append_unique_error(errors, f"{name}: {str(exc)[:120]}")
                    else:
                        token_payloads, detail = result
                        if token_payloads:
                            tokens.extend(_token_info_from_payload(path, payload) for payload in token_payloads)
                        if detail:
                            _append_unique_error(errors, f"{name}: {detail}")

        self._last_error = "" if tokens else (
            "\n".join(errors[:8])
            if errors
            else "Khong tim thay thu vien PKCS#11 phu hop trong he thong."
        )
        self._tokens_cache = list(tokens)
        self._tokens_cache_error = self._last_error
        self._tokens_cache_until = now + self._tokens_cache_ttl_seconds
        return tokens

    def select_token(self, token_info: TokenInfo | None) -> None:
        self._selected_token = token_info

    def invalidate_token_cache(self) -> None:
        self._tokens_cache = []
        self._tokens_cache_error = ""
        self._tokens_cache_until = 0.0

    def _tokens_from_driver(self, lib_path: str, *, pin: str | None = None) -> list[TokenInfo]:
        import pkcs11 as p11

        lib = p11.lib(lib_path)
        return [
            self._token_info_from_token(lib_path, index, token, pin=pin)
            for index, token in enumerate(lib.get_tokens())
        ]

    def _token_info_from_token(self, lib_path: str, index: int, token, *, pin: str | None = None) -> TokenInfo:
        signer_name = ""
        tax_code = ""
        issuer_name = ""
        cert_serial = ""
        try:
            from pkcs11.constants import Attribute, ObjectClass

            open_kwargs: dict = {"rw": False}
            if pin:
                open_kwargs["user_pin"] = pin
            with token.open(**open_kwargs) as session:
                certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
                for cert in reversed(certs):
                    cert_der = _safe_get_pkcs11_attr(cert, Attribute.VALUE)
                    identity = extract_signer_identity_from_der(cert_der)
                    if identity:
                        signer_name = identity.get("name", "")
                        tax_code = identity.get("tax_code", "")
                        issuer_name = identity.get("issuer_name", "")
                        cert_serial = identity.get("serial_hex", "")
                        break
        except Exception:
            pass

        return TokenInfo(
            driver=os.path.basename(lib_path),
            signer_name=signer_name,
            tax_code=tax_code,
            driver_path=lib_path,
            token_index=index,
            token_label=_clean_token_value(getattr(token, "label", "")),
            serial=_clean_token_value(getattr(token, "serial", "")),
            manufacturer=_clean_token_value(getattr(token, "manufacturer_id", "")),
            model=_clean_token_value(getattr(token, "model", "")),
            issuer_name=issuer_name,
            cert_serial=cert_serial,
        )

    def is_token_present(self) -> bool:
        return bool(self.list_tokens())

    def get_token_info(self, pin: str | None = None) -> TokenInfo | None:
        if self._selected_token:
            try:
                import pkcs11 as p11

                lib = p11.lib(self._selected_token.driver_path)
                token = _get_token_by_info(lib, self._selected_token)
                if token is None:
                    return self._selected_token
                refreshed = self._token_info_from_token(
                    self._selected_token.driver_path,
                    self._selected_token.token_index,
                    token,
                    pin=pin,
                )
                self._selected_token = refreshed
                return refreshed
            except Exception:
                return self._selected_token

        tokens = self.list_tokens(pin=pin)
        if not tokens:
            return None
        self._selected_token = tokens[0]
        return tokens[0]

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
    ) -> None:
        import pkcs11 as p11

        token_info = self._selected_token or self.get_token_info()
        if not token_info or not token_info.driver_path:
            raise RuntimeError(
                "Khong tim thay USB Token!\n"
                "Vui long cam thiet bi chu ky va thu lai.\n\n"
                f"Chi tiet: {self.get_last_error()}"
            )

        lib_path = token_info.driver_path
        lib = p11.lib(lib_path)
        token = _get_token_by_info(lib, token_info)
        if token is None:
            raise RuntimeError("USB Token da chon khong con duoc phat hien. Vui long cam lai token va thu lai.")

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
                token_serial=token_info.serial or token_info.cert_serial,
                field_name=field_name,
                reason=reason,
                location=location,
                contact_info=contact_info,
                tsa_url=tsa_url,
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
    ) -> None:
        import pkcs11 as p11

        token_info = self._selected_token or self.get_token_info()
        if not token_info or not token_info.driver_path:
            raise RuntimeError(
                "Khong tim thay USB Token!\n"
                "Vui long cam thiet bi chu ky va thu lai.\n\n"
                f"Chi tiet: {self.get_last_error()}"
            )

        lib_path = token_info.driver_path
        lib = p11.lib(lib_path)
        token = _get_token_by_info(lib, token_info)
        if token is None:
            raise RuntimeError("USB Token da chon khong con duoc phat hien. Vui long cam lai token va thu lai.")

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
                        token_serial=token_info.serial or token_info.cert_serial,
                        field_name=job.get("field_name"),
                        reason=job.get("reason"),
                        location=job.get("location"),
                        contact_info=job.get("contact_info"),
                        tsa_url=tsa_url,
                    )
                except Exception as e:
                    raise RuntimeError(f"Loi khi ky file {job.get('input_path')}: {e}")
        finally:
            if session is not None:
                session.close()

