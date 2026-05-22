"""OCR engine — nhận dạng văn bản tiếng Việt qua Tesseract."""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class OCRResult:
    text: str           # Toàn bộ văn bản nhận dạng
    page: int           # Số trang (1-based)
    word_count: int     # Số từ nhận dạng được
    error: Optional[str] = None


def _tesseract_cmd() -> Optional[str]:
    """Tìm đường dẫn tesseract trên hệ thống."""
    import os
    candidates = [
        shutil.which("tesseract"),
        "/opt/homebrew/bin/tesseract",                          # Apple Silicon
        "/usr/local/bin/tesseract",                             # Intel Mac
        "/usr/bin/tesseract",                                   # Linux
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",        # Windows 64-bit
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",  # Windows 32-bit
    ]
    for p in candidates:
        if p and (shutil.which(p) or os.path.isfile(p)):
            return p
    return None


def is_available() -> bool:
    """Kiểm tra Tesseract OCR có sẵn trên máy không."""
    return _tesseract_cmd() is not None


def get_installed_langs() -> list[str]:
    """Trả về danh sách ngôn ngữ tesseract đã cài."""
    cmd = _tesseract_cmd()
    if not cmd:
        return []
    try:
        result = subprocess.run(
            [cmd, "--list-langs"],
            capture_output=True, text=True, timeout=10,
        )
        lines = (result.stdout + result.stderr).splitlines()
        return [l.strip() for l in lines if l.strip() and l.strip() != "List of available tessdata:"]
    except Exception:
        return []


def has_vietnamese() -> bool:
    langs = get_installed_langs()
    return "vie" in langs


def ocr_pil_image(pil_image, page_num: int = 1, high_quality: bool = False) -> OCRResult:
    """
    Nhận dạng văn bản từ PIL Image.
    high_quality=True → dùng DPI cao hơn (chậm hơn nhưng chính xác hơn).
    """
    cmd = _tesseract_cmd()
    if not cmd:
        return OCRResult(text="", page=page_num, word_count=0,
                         error="Tesseract chưa được cài đặt.")

    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd

        # Chọn ngôn ngữ: ưu tiên vie+eng, fallback eng
        langs = get_installed_langs()
        if "vie" in langs:
            lang = "vie+eng" if "eng" in langs else "vie"
        else:
            lang = "eng"

        # Cấu hình OCR
        # psm 6 = assume a single uniform block of text
        # psm 3 = fully automatic (tốt hơn cho tài liệu hỗn hợp)
        psm = "6" if not high_quality else "3"
        config = f"--oem 1 --psm {psm}"

        if high_quality:
            # Scale ảnh lên trước khi OCR → chính xác hơn
            w, h = pil_image.size
            scale = 2.0
            from PIL import Image
            pil_image = pil_image.resize(
                (int(w * scale), int(h * scale)),
                Image.LANCZOS,
            )

        text = pytesseract.image_to_string(pil_image, lang=lang, config=config)
        text = text.strip()
        word_count = len(text.split()) if text else 0
        return OCRResult(text=text, page=page_num, word_count=word_count)

    except Exception as e:
        return OCRResult(text="", page=page_num, word_count=0, error=str(e))


def ocr_pdf_page(pdf_path: str, page_num: int, high_quality: bool = False) -> OCRResult:
    """Render trang PDF rồi OCR. page_num bắt đầu từ 1."""
    try:
        import pypdfium2 as pdfium
        from PIL import Image
        import io

        doc = pdfium.PdfDocument(pdf_path)
        try:
            page = doc[page_num - 1]
            scale = 3.0 if high_quality else 2.0
            bitmap = page.render(scale=scale)
            pil_img = bitmap.to_pil().convert("RGB")
        finally:
            doc.close()

        return ocr_pil_image(pil_img, page_num=page_num, high_quality=False)

    except Exception as e:
        return OCRResult(text="", page=page_num, word_count=0, error=str(e))
