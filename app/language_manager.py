from __future__ import annotations

import json
import os
import urllib.request
from urllib.error import HTTPError, URLError
from contextlib import closing
from pathlib import Path

from packages.qt_compat.QtCore import QSettings
from packages.qt_compat.QtWidgets import QProgressDialog

from app.config import APP_DATA_DIR_NAME, LANGUAGE_PACK_BASE_URL, VPS_LICENSE_BASE_URL


LANGUAGE_SETTINGS_KEY = "3TReader/language"
DEFAULT_LANGUAGE = "vi"

LANGUAGE_LABELS = {
    "vi": "Tiếng Việt",
    "en": "English",
    "fr": "Français",
    "zh": "中文",
    "ko": "한국어",
    "th": "ไทย",
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
        "lang.french": "Tiếng Pháp",
        "lang.chinese": "Tiếng Trung",
        "lang.korean": "Tiếng Hàn",
        "lang.thai": "Tiếng Thái",
        "lang.download": "Chọn gói ngôn ngữ...",
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
        "lang.french": "French",
        "lang.chinese": "Chinese",
        "lang.korean": "Korean",
        "lang.thai": "Thai",
        "lang.download": "Choose language packs...",
        "tab.file_view": "File & View",
        "tab.annotate": "Annotate",
        "tab.page": "Page",
        "tab.security_export": "Security & Export",
        "tab.ocr_ai": "OCR & AI",
        "tab.sign": "Sign",
        "status.no_file": "No file opened",
        "status.page": "Page: -",
    },
    "fr": {
        "menu.file": "Fichier",
        "menu.navigate": "Navigation",
        "menu.view": "Affichage",
        "menu.tools": "Outils",
        "menu.page": "Page",
        "menu.security": "Sécurité",
        "menu.sign": "Signature",
        "menu.ocr": "OCR",
        "menu.ai": "IA",
        "menu.license": "Licence",
        "menu.language": "Langue",
        "menu.help": "Aide",
        "lang.vietnamese": "Vietnamien",
        "lang.english": "Anglais",
        "lang.french": "Français",
        "lang.chinese": "Chinois",
        "lang.korean": "Coréen",
        "lang.thai": "Thaï",
        "lang.download": "Choisir les paquets de langue...",
        "tab.file_view": "Fichier et affichage",
        "tab.annotate": "Annotations",
        "tab.page": "Page",
        "tab.security_export": "Sécurité et export",
        "tab.ocr_ai": "OCR et IA",
        "tab.sign": "Signature",
        "status.no_file": "Aucun fichier ouvert",
        "status.page": "Page : -",
    },
    "zh": {
        "menu.file": "文件",
        "menu.navigate": "导航",
        "menu.view": "视图",
        "menu.tools": "工具",
        "menu.page": "页面",
        "menu.security": "安全",
        "menu.sign": "签名",
        "menu.ocr": "OCR",
        "menu.ai": "AI",
        "menu.license": "许可证",
        "menu.language": "语言",
        "menu.help": "帮助",
        "lang.vietnamese": "越南语",
        "lang.english": "英语",
        "lang.french": "法语",
        "lang.chinese": "中文",
        "lang.korean": "韩语",
        "lang.thai": "泰语",
        "lang.download": "选择语言包...",
        "tab.file_view": "文件和查看",
        "tab.annotate": "批注",
        "tab.page": "页面",
        "tab.security_export": "安全和导出",
        "tab.ocr_ai": "OCR 和 AI",
        "tab.sign": "签名",
        "status.no_file": "未打开文件",
        "status.page": "页面：-",
    },
    "ko": {
        "menu.file": "파일",
        "menu.navigate": "탐색",
        "menu.view": "보기",
        "menu.tools": "도구",
        "menu.page": "페이지",
        "menu.security": "보안",
        "menu.sign": "서명",
        "menu.ocr": "OCR",
        "menu.ai": "AI",
        "menu.license": "라이선스",
        "menu.language": "언어",
        "menu.help": "도움말",
        "lang.vietnamese": "베트남어",
        "lang.english": "영어",
        "lang.french": "프랑스어",
        "lang.chinese": "중국어",
        "lang.korean": "한국어",
        "lang.thai": "태국어",
        "lang.download": "언어 팩 선택...",
        "tab.file_view": "파일 및 보기",
        "tab.annotate": "주석",
        "tab.page": "페이지",
        "tab.security_export": "보안 및 내보내기",
        "tab.ocr_ai": "OCR 및 AI",
        "tab.sign": "서명",
        "status.no_file": "열린 파일 없음",
        "status.page": "페이지: -",
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


def language_pack_urls(code: str) -> list[str]:
    code = code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE
    primary = language_pack_url(code)
    urls = [primary]

    static_base = f"{VPS_LICENSE_BASE_URL.rstrip('/')}/downloads/language"
    static_alt_base = static_base.replace("reader.3tcomputer.com", "license.3tcomputer.com")

    for base in (static_base, static_alt_base):
        alt = f"{base}/{code}.json"
        if alt not in urls:
            urls.append(alt)
    return urls


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
    builtin = BUILTIN_TRANSLATIONS.get(code, {})
    if code == DEFAULT_LANGUAGE and key in builtin:
        return builtin[key]

    pack = load_language_pack(code)
    if key in pack:
        return pack[key]
    return builtin.get(key, fallback)


def download_language_pack(code: str, parent=None) -> tuple[bool, str]:
    code = code if code in LANGUAGE_LABELS else DEFAULT_LANGUAGE
    save_path = language_pack_path(code)
    tmp_path = save_path.with_suffix(save_path.suffix + ".download")

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

    def _headers(url: str) -> dict[str, str]:
        origin = url.rsplit("/", 1)[0]
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": f"{origin}/",
            "Origin": origin,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _describe_error(url: str, exc: Exception) -> str:
        if isinstance(exc, HTTPError):
            return f"HTTPError {exc.code} {exc.reason} for {url}"
        if isinstance(exc, URLError):
            return f"URLError {exc.reason} for {url}"
        return f"{exc.__class__.__name__} for {url}: {exc}"

    try:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
        last_exc: Exception | None = None
        attempted: list[str] = []
        for url in language_pack_urls(code):
            attempted.append(url)
            try:
                req = urllib.request.Request(url, headers=_headers(url))
                with closing(opener.open(req, timeout=30)) as resp, open(tmp_path, "wb") as out:
                    total_size = int(resp.headers.get("Content-Length", "0") or "0")
                    if progress is not None and total_size > 0:
                        progress.setValue(0)
                    block_num = 0
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                        block_num += 1
                        _reporthook(block_num, len(chunk), total_size)
                if tmp_path.exists() and tmp_path.stat().st_size > 0:
                    tmp_path.replace(save_path)
                    if progress is not None:
                        progress.setValue(100)
                        progress.close()
                    return True, str(save_path)
                last_exc = RuntimeError("Downloaded language pack is empty")
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
                last_exc = RuntimeError(_describe_error(url, exc))
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                continue
        tried = ", ".join(attempted) if attempted else "(none)"
        raise last_exc or RuntimeError(f"Unable to download language pack. Tried: {tried}")
    except Exception as exc:
        if progress is not None:
            progress.close()
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        tried = ", ".join(language_pack_urls(code))
        return False, f"{exc} | tried={tried}"
