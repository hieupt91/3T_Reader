from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from packages.qt_compat.QtCore import QSettings
from packages.qt_compat.QtWidgets import QProgressDialog

from app.config import APP_DATA_DIR_NAME, LANGUAGE_PACK_BASE_URL


LANGUAGE_SETTINGS_KEY = "3TReader/language"
DEFAULT_LANGUAGE = "vi"

LANGUAGE_LABELS = {
    "vi": "Tiếng Việt",
    "en": "English",
}

BUILTIN_TRANSLATIONS = {
    "vi": {
        "menu.file": "Tệp",
        "menu.navigate": "Điều hướng",
        "menu.view": "Xem",
        "menu.tools": "Công cụ",
        "menu.page": "Trang",
        "menu.security": "Bảo mật",
        "menu.sign": "Chữ ký số",
        "menu.ocr": "OCR",
        "menu.ai": "AI",
        "menu.license": "License",
        "menu.language": "Ngôn ngữ",
        "menu.help": "Trợ giúp",
        "lang.vietnamese": "Tiếng Việt",
        "lang.english": "English",
        "lang.download": "Tải gói ngôn ngữ...",
        "tab.file_view": "Tệp & Xem",
        "tab.annotate": "Chú thích",
        "tab.page": "Trang",
        "tab.security_export": "Bảo mật & Xuất",
        "tab.ocr_ai": "OCR & AI",
        "tab.sign": "Ký số",
        "status.no_file": "Chưa mở tệp",
        "status.page": "Trang: -",
    },
    "en": {
        "menu.file": "File",
        "menu.navigate": "Navigate",
        "menu.view": "View",
        "menu.tools": "Tools",
        "menu.page": "Page",
        "menu.security": "Security",
        "menu.sign": "Sign",
        "menu.ocr": "OCR",
        "menu.ai": "AI",
        "menu.license": "License",
        "menu.language": "Language",
        "menu.help": "Help",
        "lang.vietnamese": "Vietnamese",
        "lang.english": "English",
        "lang.download": "Download language pack...",
        "tab.file_view": "File & View",
        "tab.annotate": "Annotate",
        "tab.page": "Page",
        "tab.security_export": "Security & Export",
        "tab.ocr_ai": "OCR & AI",
        "tab.sign": "Sign",
        "status.no_file": "No file opened",
        "status.page": "Page: -",
    },
}


def _settings() -> QSettings:
    return QSettings()


def get_selected_language() -> str:
    code = str(_settings().value(LANGUAGE_SETTINGS_KEY, DEFAULT_LANGUAGE) or DEFAULT_LANGUAGE)
    return code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE


def set_selected_language(code: str) -> None:
    code = code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE
    _settings().setValue(LANGUAGE_SETTINGS_KEY, code)


def available_languages() -> list[dict[str, str]]:
    return [
        {"code": code, "label": label, "url": language_pack_url(code)}
        for code, label in LANGUAGE_LABELS.items()
    ]


def language_pack_url(code: str) -> str:
    code = code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE
    return f"{LANGUAGE_PACK_BASE_URL.rstrip('/')}/{code}.json"


def language_pack_dir() -> Path:
    from app.config import APP_DATA_DIR_NAME  # local import to avoid cycles
    from packages.platform import get_app_data_dir

    root = Path(get_app_data_dir()) / "language_packs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def language_pack_path(code: str) -> Path:
    return language_pack_dir() / f"{code}.json"


def load_language_pack(code: str) -> dict[str, str]:
    path = language_pack_path(code)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("strings"), dict):
            data = data["strings"]
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_language_pack(code: str, data: dict[str, str]) -> Path:
    path = language_pack_path(code)
    payload = {"code": code, "strings": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def get_translation(code: str, key: str, fallback: str) -> str:
    code = code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE
    pack = load_language_pack(code)
    if key in pack:
        return pack[key]
    return BUILTIN_TRANSLATIONS.get(code, {}).get(key, fallback)


def download_language_pack(code: str, parent=None) -> tuple[bool, str]:
    code = code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE
    url = language_pack_url(code)
    save_path = language_pack_path(code)

    progress = None
    if parent is not None:
        progress = QProgressDialog("Dang tai goi ngon ngu...", "Huy", 0, 100, parent)
        progress.setWindowTitle("Ngon ngu")
        progress.setMinimumDuration(0)
        progress.show()

    def _reporthook(block_num, block_size, total_size):
        if progress is not None:
            if progress.wasCanceled():
                raise RuntimeError("Cancelled")
            if total_size > 0:
                percent = min(100, int(block_num * block_size * 100 / total_size))
                progress.setValue(percent)

    try:
        urllib.request.urlretrieve(url, save_path, _reporthook)
        if progress is not None:
            progress.setValue(100)
            progress.close()
        return True, str(save_path)
    except Exception as exc:
        if progress is not None:
            progress.close()
        if save_path.exists():
            try:
                save_path.unlink()
            except OSError:
                pass
        return False, str(exc)
