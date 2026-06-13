from __future__ import annotations

import os
import sys
from pathlib import Path

_WINDOWS_CANDIDATES = [
    "arial.ttf",
    "segoeui.ttf",
    "tahoma.ttf",
    "times.ttf",
]

_WINDOWS_BOLD_CANDIDATES = [
    "arialbd.ttf",
    "segoeuib.ttf",
    "tahomabd.ttf",
    "tahoma.ttf",   # fallback to regular if bold variant missing
    "arial.ttf",
    "segoeui.ttf",
]

_MACOS_CANDIDATES = [
    "Arial.ttf",
    "Arial Unicode.ttf",
    "Times New Roman.ttf",
    "Georgia.ttf",
    "Verdana.ttf",
    "Tahoma.ttf",
]

_LINUX_CANDIDATES = [
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "FreeSans.ttf",
    "Arial.ttf",
]

_MACOS_SEARCH_DIRS = [
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path.home() / "Library" / "Fonts",
]

_LINUX_SEARCH_DIRS = [
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local" / "share" / "fonts",
]


def _windows_font_path(bold: bool = False) -> str | None:
    import os
    fonts_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
    candidates = _WINDOWS_BOLD_CANDIDATES if bold else _WINDOWS_CANDIDATES
    for name in candidates:
        path = fonts_dir / name
        if path.exists():
            return str(path)
    return None


def get_system_font_path(name: str = "", *, bold: bool = False) -> str | None:
    """Return a matching system font path when available.

    Kept for smoke-test/backward compatibility; feature code should prefer
    get_vietnamese_font_path() when text may contain Vietnamese.
    """
    wanted = (name or "").strip().lower()
    if sys.platform == "win32":
        if wanted:
            fonts_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
            for path in fonts_dir.glob("*.ttf"):
                stem = path.stem.lower()
                if wanted in stem:
                    return str(path)
        return _windows_font_path(bold)
    return get_vietnamese_font_path(bold=bold)


def _macos_font_path() -> str | None:
    for name in _MACOS_CANDIDATES:
        for d in _MACOS_SEARCH_DIRS:
            path = d / name
            if path.exists():
                return str(path)
    return None


def _linux_font_path() -> str | None:
    for name in _LINUX_CANDIDATES:
        for d in _LINUX_SEARCH_DIRS:
            if not d.exists():
                continue
            for match in d.rglob(name):
                return str(match)
    return None


def get_vietnamese_font_path(bold: bool = False) -> str | None:
    """Return path to a Vietnamese-compatible font installed on this OS, or None."""
    if sys.platform == "win32":
        return _windows_font_path(bold)
    if sys.platform == "darwin":
        return _macos_font_path()
    return _linux_font_path()
