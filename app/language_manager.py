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

_MOJIBAKE_MARKERS = (
    "Ã", "Â", "Ä", "Æ", "áº", "á»", "à¸", "à¹", "è¯", "ì", "í",
)

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
    "th": {
        "menu.file": "ไฟล์",
        "menu.navigate": "นำทาง",
        "menu.view": "มุมมอง",
        "menu.tools": "เครื่องมือ",
        "menu.page": "หน้า",
        "menu.security": "ความปลอดภัย",
        "menu.sign": "ลายเซ็น",
        "menu.ocr": "OCR",
        "menu.ai": "AI",
        "menu.license": "License",
        "menu.language": "ภาษา",
        "menu.help": "ช่วยเหลือ",
        "lang.vietnamese": "เวียดนาม",
        "lang.english": "อังกฤษ",
        "lang.french": "ฝรั่งเศส",
        "lang.chinese": "จีน",
        "lang.korean": "เกาหลี",
        "lang.thai": "ไทย",
        "lang.download": "เลือกแพ็กภาษา...",
        "tab.file_view": "ไฟล์และมุมมอง",
        "tab.annotate": "คำอธิบายประกอบ",
        "tab.page": "หน้า",
        "tab.security_export": "ความปลอดภัยและส่งออก",
        "tab.ocr_ai": "OCR และ AI",
        "tab.sign": "ลายเซ็น",
        "status.no_file": "ยังไม่ได้เปิดไฟล์",
        "status.page": "หน้า: -",
    },
}

ACTION_TRANSLATIONS = {
    "vi": {
        "action.open": "Mở tệp",
        "action.new_pdf": "PDF mới",
        "action.recent": "Gần đây",
        "action.save": "Lưu",
        "action.save_as": "Lưu mới",
        "action.print": "In",
        "action.prev": "Trang trước",
        "action.next": "Trang sau",
        "action.zoom_in": "Phóng to",
        "action.zoom_out": "Thu nhỏ",
        "action.fit": "Vừa trang",
        "action.theme": "Giao diện",
        "action.fullscreen": "Toàn màn",
        "action.highlight": "Tô sáng",
        "action.insert_text": "Chèn chữ",
        "action.insert_image": "Chèn ảnh",
        "action.draw": "Vẽ tự do",
        "action.redact": "Xóa trắng",
        "action.delete_object": "Xóa obj",
        "action.select_object": "Chọn & Xoay",
        "action.undo": "Hoàn tác",
        "action.watermark": "Watermark",
        "action.remove_watermark": "Xóa watermark",
        "action.set_password": "Đặt mật khẩu",
        "action.remove_password": "Xóa mật khẩu",
        "action.compress": "Nén PDF",
        "action.export_image": "Ảnh",
        "action.export_text": "Văn bản",
        "action.ocr_page": "OCR trang",
        "action.ocr_document": "OCR tài liệu",
        "action.chat_pdf": "Chat PDF",
        "action.summary": "Tóm tắt",
        "action.translate": "Dịch",
        "action.semantic_search": "Tìm nghĩa",
        "action.ai_settings": "Cài đặt AI",
        "action.sign": "Ký số",
        "action.signature_field": "Ô ký",
        "action.hand_sign": "Ký tay/dấu",
        "action.verify": "Kiểm tra",
    },
    "en": {
        "action.open": "Open file",
        "action.new_pdf": "New PDF",
        "action.recent": "Recent",
        "action.save": "Save",
        "action.save_as": "Save as",
        "action.print": "Print",
        "action.prev": "Previous page",
        "action.next": "Next page",
        "action.zoom_in": "Zoom in",
        "action.zoom_out": "Zoom out",
        "action.fit": "Fit page",
        "action.theme": "Theme",
        "action.fullscreen": "Full screen",
        "action.highlight": "Highlight",
        "action.insert_text": "Insert text",
        "action.insert_image": "Insert image",
        "action.draw": "Free draw",
        "action.redact": "Redact",
        "action.delete_object": "Delete obj",
        "action.select_object": "Select & Rotate",
        "action.undo": "Undo",
        "action.watermark": "Watermark",
        "action.remove_watermark": "Remove watermark",
        "action.set_password": "Set password",
        "action.remove_password": "Remove password",
        "action.compress": "Compress PDF",
        "action.export_image": "Image",
        "action.export_text": "Text",
        "action.ocr_page": "OCR page",
        "action.ocr_document": "OCR document",
        "action.chat_pdf": "Chat PDF",
        "action.summary": "Summary",
        "action.translate": "Translate",
        "action.semantic_search": "Semantic search",
        "action.ai_settings": "AI settings",
        "action.sign": "Sign",
        "action.signature_field": "Signature field",
        "action.hand_sign": "Hand sign/stamp",
        "action.verify": "Verify",
    },
    "fr": {
        "action.open": "Ouvrir",
        "action.new_pdf": "Nouveau PDF",
        "action.recent": "Récents",
        "action.save": "Enregistrer",
        "action.save_as": "Enregistrer sous",
        "action.print": "Imprimer",
        "action.prev": "Page précédente",
        "action.next": "Page suivante",
        "action.zoom_in": "Agrandir",
        "action.zoom_out": "Réduire",
        "action.fit": "Ajuster",
        "action.theme": "Thème",
        "action.fullscreen": "Plein écran",
        "action.highlight": "Surligner",
        "action.insert_text": "Insérer texte",
        "action.insert_image": "Insérer image",
        "action.draw": "Dessin libre",
        "action.redact": "Masquer",
        "action.delete_object": "Supprimer obj",
        "action.select_object": "Sélectionner",
        "action.undo": "Annuler",
        "action.watermark": "Filigrane",
        "action.remove_watermark": "Supprimer filigrane",
        "action.set_password": "Définir mot de passe",
        "action.remove_password": "Supprimer mot de passe",
        "action.compress": "Compresser PDF",
        "action.export_image": "Image",
        "action.export_text": "Texte",
        "action.ocr_page": "OCR page",
        "action.ocr_document": "OCR document",
        "action.chat_pdf": "Chat PDF",
        "action.summary": "Résumé",
        "action.translate": "Traduire",
        "action.semantic_search": "Recherche sémantique",
        "action.ai_settings": "Réglages IA",
        "action.sign": "Signer",
        "action.signature_field": "Champ signature",
        "action.hand_sign": "Signature/cachet",
        "action.verify": "Vérifier",
    },
    "zh": {
        "action.open": "打开文件",
        "action.new_pdf": "新建 PDF",
        "action.recent": "最近",
        "action.save": "保存",
        "action.save_as": "另存为",
        "action.print": "打印",
        "action.prev": "上一页",
        "action.next": "下一页",
        "action.zoom_in": "放大",
        "action.zoom_out": "缩小",
        "action.fit": "适合页面",
        "action.theme": "主题",
        "action.fullscreen": "全屏",
        "action.highlight": "高亮",
        "action.insert_text": "插入文本",
        "action.insert_image": "插入图片",
        "action.draw": "自由绘制",
        "action.redact": "遮盖",
        "action.delete_object": "删除对象",
        "action.select_object": "选择/旋转",
        "action.undo": "撤销",
        "action.watermark": "水印",
        "action.remove_watermark": "删除水印",
        "action.set_password": "设置密码",
        "action.remove_password": "删除密码",
        "action.compress": "压缩 PDF",
        "action.export_image": "图片",
        "action.export_text": "文本",
        "action.ocr_page": "OCR 当前页",
        "action.ocr_document": "OCR 文档",
        "action.chat_pdf": "PDF 聊天",
        "action.summary": "摘要",
        "action.translate": "翻译",
        "action.semantic_search": "语义搜索",
        "action.ai_settings": "AI 设置",
        "action.sign": "签名",
        "action.signature_field": "签名框",
        "action.hand_sign": "手写/印章",
        "action.verify": "验证",
    },
    "ko": {
        "action.open": "파일 열기",
        "action.new_pdf": "새 PDF",
        "action.recent": "최근",
        "action.save": "저장",
        "action.save_as": "다른 이름 저장",
        "action.print": "인쇄",
        "action.prev": "이전 페이지",
        "action.next": "다음 페이지",
        "action.zoom_in": "확대",
        "action.zoom_out": "축소",
        "action.fit": "페이지 맞춤",
        "action.theme": "테마",
        "action.fullscreen": "전체 화면",
        "action.highlight": "강조",
        "action.insert_text": "텍스트 삽입",
        "action.insert_image": "이미지 삽입",
        "action.draw": "자유 그리기",
        "action.redact": "가리기",
        "action.delete_object": "개체 삭제",
        "action.select_object": "선택/회전",
        "action.undo": "실행 취소",
        "action.watermark": "워터마크",
        "action.remove_watermark": "워터마크 삭제",
        "action.set_password": "비밀번호 설정",
        "action.remove_password": "비밀번호 삭제",
        "action.compress": "PDF 압축",
        "action.export_image": "이미지",
        "action.export_text": "텍스트",
        "action.ocr_page": "OCR 페이지",
        "action.ocr_document": "OCR 문서",
        "action.chat_pdf": "PDF 채팅",
        "action.summary": "요약",
        "action.translate": "번역",
        "action.semantic_search": "의미 검색",
        "action.ai_settings": "AI 설정",
        "action.sign": "서명",
        "action.signature_field": "서명 필드",
        "action.hand_sign": "수기/도장",
        "action.verify": "검증",
    },
    "th": {
        "action.open": "เปิดไฟล์",
        "action.new_pdf": "PDF ใหม่",
        "action.recent": "ล่าสุด",
        "action.save": "บันทึก",
        "action.save_as": "บันทึกเป็น",
        "action.print": "พิมพ์",
        "action.prev": "หน้าก่อน",
        "action.next": "หน้าถัดไป",
        "action.zoom_in": "ซูมเข้า",
        "action.zoom_out": "ซูมออก",
        "action.fit": "พอดีหน้า",
        "action.theme": "ธีม",
        "action.fullscreen": "เต็มจอ",
        "action.highlight": "ไฮไลต์",
        "action.insert_text": "แทรกข้อความ",
        "action.insert_image": "แทรกรูป",
        "action.draw": "วาดอิสระ",
        "action.redact": "ปิดทับ",
        "action.delete_object": "ลบวัตถุ",
        "action.select_object": "เลือก/หมุน",
        "action.undo": "ย้อนกลับ",
        "action.watermark": "ลายน้ำ",
        "action.remove_watermark": "ลบลายน้ำ",
        "action.set_password": "ตั้งรหัสผ่าน",
        "action.remove_password": "ลบรหัสผ่าน",
        "action.compress": "บีบอัด PDF",
        "action.export_image": "รูปภาพ",
        "action.export_text": "ข้อความ",
        "action.ocr_page": "OCR หน้า",
        "action.ocr_document": "OCR เอกสาร",
        "action.chat_pdf": "แชท PDF",
        "action.summary": "สรุป",
        "action.translate": "แปล",
        "action.semantic_search": "ค้นหาเชิงความหมาย",
        "action.ai_settings": "ตั้งค่า AI",
        "action.sign": "ลงนาม",
        "action.signature_field": "ช่องลงนาม",
        "action.hand_sign": "ลายเซ็น/ตรา",
        "action.verify": "ตรวจสอบ",
    },
}

for _code, _strings in ACTION_TRANSLATIONS.items():
    BUILTIN_TRANSLATIONS.setdefault(_code, {}).update(_strings)


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
        return _normalize_language_pack_payload(data, expected_code=code)
    except Exception:
        return {}


def save_language_pack(code: str, data: dict[str, str]) -> Path:
    path = language_pack_path(code)
    payload = {"code": code, "strings": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def _normalize_language_pack_payload(data, *, expected_code: str) -> dict[str, str]:
    if isinstance(data, dict) and data.get("code") and str(data.get("code")) != expected_code:
        return {}
    if isinstance(data, dict) and isinstance(data.get("strings"), dict):
        data = data["strings"]
    if not isinstance(data, dict):
        return {}
    strings = {str(k): str(v) for k, v in data.items()}
    sample = "\n".join(strings.values())
    if any(marker in sample for marker in _MOJIBAKE_MARKERS):
        return {}
    return strings


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

        import ssl
        ssl_context = ssl._create_unverified_context()
        
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(context=ssl_context),
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
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    normalized = _normalize_language_pack_payload(payload, expected_code=code)
                    if not normalized:
                        raise RuntimeError("Downloaded language pack failed validation")
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
