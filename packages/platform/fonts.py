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


def _windows_font_path(bold: bool = False, italic: bool = False, family: str = "") -> str | None:
    import os
    family = (family or "").lower()
    fonts_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
    
    font_map = {
        "arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
        "times new roman": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
        "calibri": ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
        "tahoma": ("tahoma.ttf", "tahomabd.ttf", "tahoma.ttf", "tahomabd.ttf"),
        "segoe ui": ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
        "cambria": ("cambria.ttc", "cambriab.ttf", "cambriai.ttf", "cambriaz.ttf"),
        "consolas": ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
        "comic sans ms": ("comic.ttf", "comicbd.ttf", "comici.ttf", "comicz.ttf"),
        "courier new": ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
        "verdana": ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
    }

    candidates = []
    if italic and bold:
        candidates = ["arialbi.ttf", "timesbi.ttf", "calibriz.ttf", "segoeuiz.ttf"]
    elif italic:
        candidates = ["ariali.ttf", "timesi.ttf", "calibrii.ttf", "segoeuii.ttf"]
    elif bold:
        candidates = ["arialbd.ttf", "timesbd.ttf", "calibrib.ttf", "segoeuib.ttf", "tahomabd.ttf"]
    else:
        candidates = ["arial.ttf", "times.ttf", "calibri.ttf", "segoeui.ttf", "tahoma.ttf"]

    if "times" in family or "serif" in family:
        if italic and bold:
            candidates = ["timesbi.ttf", "timesbd.ttf", "timesi.ttf", "times.ttf"] + candidates
        elif italic:
            candidates = ["timesi.ttf", "times.ttf"] + candidates
        elif bold:
            candidates = ["timesbd.ttf", "times.ttf"] + candidates
        else:
            candidates = ["times.ttf"] + candidates

    for key, (r, b, i, bi) in font_map.items():
        if key in family:
            if italic and bold:
                candidates.insert(0, bi)
                candidates.insert(1, b)
            elif italic:
                candidates.insert(0, i)
                candidates.insert(1, r)
            elif bold:
                candidates.insert(0, b)
                candidates.insert(1, r)
            else:
                candidates.insert(0, r)
            break

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
        return _windows_font_path(bold, family=name)
    return get_vietnamese_font_path(bold=bold, family=name)


def _macos_font_path(family: str = "") -> str | None:
    family = (family or "").lower()
    candidates = _MACOS_CANDIDATES
    if "times" in family or "serif" in family:
        candidates = ["Times New Roman.ttf", "Georgia.ttf"] + candidates

    for name in candidates:
        for d in _MACOS_SEARCH_DIRS:
            path = d / name
            if path.exists():
                return str(path)
    return None


def _linux_font_path(family: str = "") -> str | None:
    family = (family or "").lower()
    candidates = _LINUX_CANDIDATES
    if "times" in family or "serif" in family:
        candidates = ["LiberationSerif-Regular.ttf", "FreeSerif.ttf"] + candidates

    for name in candidates:
        for d in _LINUX_SEARCH_DIRS:
            if not d.exists():
                continue
            for match in d.rglob(name):
                return str(match)
    return None


def get_vietnamese_font_path(bold: bool = False, italic: bool = False, family: str = "") -> str | None:
    """Return path to a Vietnamese-compatible font installed on this OS, or None."""
    if sys.platform == "win32":
        return _windows_font_path(bold, italic, family)
    if sys.platform == "darwin":
        return _macos_font_path(family)
    return _linux_font_path(family)
