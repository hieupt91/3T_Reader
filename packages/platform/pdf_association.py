r"""Windows PDF file-association icon-cache self-heal.

installer_script.iss refreshes Explorer's icon cache (SHChangeNotify +
ie4uinit -ClearIconCache/-show) exactly once, right after Setup.exe
finishes. If the user later changes the default .pdf handler through
Windows Settings > Default apps (a system UI this app cannot hook into
directly - Windows writes HKCU\...\FileExts\.pdf\UserChoice itself, no
app code runs), nothing re-triggers that refresh and Explorer keeps
showing the stale icon even though 3T Reader is now the real default.

refresh_pdf_icon_if_default_changed() detects that transition on every
app startup (cheap registry read) and re-runs the same refresh the
installer does, only when the default ProgId actually changed since the
last launch.
"""

import json
import os
import sys

from .paths import get_app_data_dir

try:
    import winreg as _winreg  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - non-Windows platforms
    _winreg = None

_OUR_PROGID = "3TReader.PDF"
_STATE_FILE = os.path.join(get_app_data_dir(), "pdf_association_state.json")


def _current_pdf_progid() -> str:
    try:
        with _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice",
        ) as key:
            value, _ = _winreg.QueryValueEx(key, "ProgId")
            if value:
                return str(value)
    except OSError:
        pass
    try:
        with _winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT, ".pdf") as key:
            value, _ = _winreg.QueryValueEx(key, "")
            return str(value or "")
    except OSError:
        return ""


def _last_seen_progid() -> str:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return str(json.load(f).get("last_pdf_progid") or "")
    except Exception:
        return ""


def _save_seen_progid(progid: str) -> None:
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_pdf_progid": progid}, f)
    except Exception:
        pass


def _refresh_explorer_icon_cache() -> None:
    try:
        import ctypes

        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except Exception:
        pass
    try:
        import subprocess

        ie4uinit = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "ie4uinit.exe")
        for arg in ("-ClearIconCache", "-show"):
            subprocess.run(
                [ie4uinit, arg], timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


def refresh_pdf_icon_if_default_changed() -> None:
    """Call once at startup. No-op outside Windows or on any error."""
    if sys.platform != "win32" or _winreg is None:
        return
    try:
        current = _current_pdf_progid()
        if not current:
            return
        last_seen = _last_seen_progid()
        if current == last_seen:
            return
        _save_seen_progid(current)
        if current == _OUR_PROGID:
            _refresh_explorer_icon_cache()
    except Exception:
        pass
