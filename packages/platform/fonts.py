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
    "Arial Unicode MS.ttf",
    "ArialMT.ttf",
    "Times New Roman.ttf",
    "TimesNewRomanPSMT.ttf",
    "Georgia.ttf",
    "Verdana.ttf",
    "Tahoma.ttf",
    "Helvetica.ttf",
    "Helvetica Neue.ttf",
]

_MACOS_BOLD_CANDIDATES = [
    "Arial Bold.ttf",
    "Arial-BoldMT.ttf",
    "Times New Roman Bold.ttf",
    "TimesNewRomanPS-BoldMT.ttf",
    "Georgia Bold.ttf",
    "Verdana Bold.ttf",
    "Verdana-Bold.ttf",
    # fallback to regular
    "Arial.ttf",
    "Times New Roman.ttf",
    "Georgia.ttf",
]

_MACOS_ITALIC_CANDIDATES = [
    "Arial Italic.ttf",
    "Arial-ItalicMT.ttf",
    "Times New Roman Italic.ttf",
    "TimesNewRomanPS-ItalicMT.ttf",
    "Georgia Italic.ttf",
    "Verdana Italic.ttf",
    # fallback to regular
    "Arial.ttf",
    "Times New Roman.ttf",
]

_MACOS_BOLD_ITALIC_CANDIDATES = [
    "Arial Bold Italic.ttf",
    "Arial-BoldItalicMT.ttf",
    "Times New Roman Bold Italic.ttf",
    "TimesNewRomanPS-BoldItalicMT.ttf",
    "Georgia Bold Italic.ttf",
    # fallback
    "Arial Bold.ttf",
    "Arial.ttf",
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


def _macos_font_path(bold: bool = False, italic: bool = False, family: str = "",
                     serif: bool | None = None) -> str | None:
    """Resolve a macOS font path that supports Vietnamese Unicode (full bold/italic support)."""
    family = (family or "").lower()

    # Chọn danh sách ứng cử viên theo style
    if bold and italic:
        candidates = list(_MACOS_BOLD_ITALIC_CANDIDATES)
    elif bold:
        candidates = list(_MACOS_BOLD_CANDIDATES)
    elif italic:
        candidates = list(_MACOS_ITALIC_CANDIDATES)
    else:
        candidates = list(_MACOS_CANDIDATES)

    # Ưu tiên font theo family hint
    _times_entry = {
        "": "Times New Roman.ttf",
        "bold": "Times New Roman Bold.ttf",
        "italic": "Times New Roman Italic.ttf",
        "bold_italic": "Times New Roman Bold Italic.ttf",
    }
    _arial_entry = {
        "": "Arial.ttf",
        "bold": "Arial Bold.ttf",
        "italic": "Arial Italic.ttf",
        "bold_italic": "Arial Bold Italic.ttf",
    }
    # Thứ tự quan trọng: "sans" phải đứng TRƯỚC "serif" vì chuỗi "sans-serif"
    # chứa cả "serif" — kẻo font sans bị map nhầm sang Times.
    # Các font PDF hay gặp nhưng macOS không cài (Cambria, Calibri, Segoe...)
    # map về font cùng họ gần nhất để text sửa không bị lộ khác font.
    family_map = {
        "times": _times_entry,
        "cambria": _times_entry,
        "constantia": _times_entry,
        "book antiqua": _times_entry,
        "palatino": _times_entry,
        "garamond": _times_entry,
        "georgia": {
            "": "Georgia.ttf",
            "bold": "Georgia Bold.ttf",
        },
        "arial": _arial_entry,
        "helvetica": _arial_entry,
        "calibri": _arial_entry,
        "segoe": _arial_entry,
        "roboto": _arial_entry,
        "tahoma": _arial_entry,
        "verdana": {
            "": "Verdana.ttf",
            "bold": "Verdana Bold.ttf",
        },
        "sans": _arial_entry,
        "serif": {
            "": "Times New Roman.ttf",
            "bold": "Times New Roman Bold.ttf",
        },
    }
    style_key = ("bold_italic" if bold and italic else
                 "bold" if bold else
                 "italic" if italic else "")
    hint_matched = False
    for hint, style_dict in family_map.items():
        if hint in family:
            preferred = style_dict.get(style_key) or style_dict.get("") or ""
            if preferred:
                candidates.insert(0, preferred)
            hint_matched = True
            break

    # Font lạ (không có trong map): dùng cờ serif từ chính PDF để chọn đúng họ
    # chữ — không cần liệt kê từng font. serif=True → Times, False → Arial.
    if not hint_matched and serif is not None:
        generic = _times_entry if serif else _arial_entry
        preferred = generic.get(style_key) or generic.get("") or ""
        if preferred:
            candidates.insert(0, preferred)

    # Tìm file tồn tại trong thư mục hệ thống của macOS
    for name in candidates:
        for d in _MACOS_SEARCH_DIRS:
            path = d / name
            if path.exists():
                return str(path)

    # Thử thêm Supplemental fonts (macOS 10.15+)
    supplemental = Path("/System/Library/Fonts/Supplemental")
    if supplemental.exists():
        for name in candidates:
            p = supplemental / name
            if p.exists():
                return str(p)

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


def get_vietnamese_font_path(bold: bool = False, italic: bool = False, family: str = "",
                             serif: bool | None = None) -> str | None:
    """Return path to a Vietnamese-compatible font installed on this OS, or None.

    Trên macOS, hàm này tìm font hỗ trợ đầy đủ Unicode (bao gồm tiếng Việt) và
    phân biệt đúng các style Bold / Italic theo yêu cầu của PyMuPDF 1.24+.
    `serif`: cờ phân họ từ PDF (span flags bit 4) — fallback cho font lạ
    không có trong family_map, để chữ thay vẫn đúng họ serif/sans.
    """
    if sys.platform == "win32":
        return _windows_font_path(bold, italic, family)
    if sys.platform == "darwin":
        # FIX: Truyền đầy đủ bold + italic thay vì chỉ truyền family
        return _macos_font_path(bold=bold, italic=italic, family=family, serif=serif)
    return _linux_font_path(family)
