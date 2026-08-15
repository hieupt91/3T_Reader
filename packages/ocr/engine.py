"""OCR engine - recognize text through Tesseract."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class OCRResult:
    text: str
    page: int
    word_count: int
    error: Optional[str] = None


@dataclass
class OCRRuntimeStatus:
    available: bool
    tesseract_cmd: str = ""
    tessdata_dir: str = ""
    languages: list[str] | None = None
    missing_vietnamese: bool = False
    error: str = ""


def _hidden_process_kwargs() -> dict:
    """Prevent bundled Tesseract from flashing a black console on Windows."""
    if sys.platform != "win32":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _configure_pytesseract_no_window(pytesseract) -> None:
    """pytesseract does not set CREATE_NO_WINDOW itself on all versions."""
    module = pytesseract.pytesseract
    if getattr(module, "_3t_no_window", False):
        return
    original = module.subprocess_args

    def subprocess_args(include_stdout=True):
        kwargs = original(include_stdout)
        kwargs.update(_hidden_process_kwargs())
        return kwargs

    module.subprocess_args = subprocess_args
    module._3t_no_window = True
    error: str = ""


def _is_executable(path: str | os.PathLike[str] | None) -> bool:
    if not path:
        return False
    try:
        return os.path.isfile(path) and os.access(path, os.X_OK)
    except Exception:
        return False


def _candidate_tesseract_paths() -> list[str]:
    exe_name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    base_dir = Path(sys.executable).resolve().parent
    app_dir = Path(__file__).resolve().parents[2]

    candidates = [
        os.environ.get("OCR_TESSERACT_CMD"),
        os.environ.get("TESSERACT_CMD"),
        os.environ.get("TESSERACT_PATH"),
        str(base_dir / "_internal" / "Tesseract-OCR" / exe_name),
        str(base_dir / "Tesseract-OCR" / exe_name),
        str(base_dir / "tesseract" / exe_name),
        str(base_dir / exe_name),
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend([
            str(Path(meipass) / "Tesseract-OCR" / exe_name),
            str(Path(meipass) / "third_party" / "tesseract" / exe_name)
        ])
        
    # Thêm đường dẫn chuẩn theo TIEU_CHUAN_DONG_BO_WIN_MAC
    if sys.platform == "win32":
        candidates.append(str(app_dir / "bin_win" / "tesseract" / exe_name))
    elif sys.platform == "darwin":
        candidates.append(str(app_dir / "bin_mac" / "tesseract" / exe_name))

    candidates.extend([
        str(app_dir / "Tesseract-OCR" / exe_name),
        str(app_dir / "third_party" / "tesseract" / exe_name),
        str(app_dir / "assets" / "tesseract" / exe_name),
        shutil.which(exe_name),
        shutil.which("tesseract"),
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ])

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _tesseract_cmd() -> Optional[str]:
    """Find a usable tesseract executable."""
    for candidate in _candidate_tesseract_paths():
        if _is_executable(candidate):
            return str(candidate)
    return None


def _tessdata_dir(cmd: Optional[str] = None) -> Optional[str]:
    """Find a tessdata directory near the executable or from env."""
    env_dir = os.environ.get("TESSDATA_PREFIX")
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    cmd = cmd or _tesseract_cmd()
    if not cmd:
        return None

    cmd_path = Path(cmd)
    candidates = [
        cmd_path.parent / "tessdata",
        cmd_path.parent / "tesseract" / "tessdata",
        cmd_path.parent.parent / "tessdata",
        cmd_path.parent.parent / "Tesseract-OCR" / "tessdata",
        cmd_path.parent / "share" / "tessdata",
        cmd_path.parent / "share" / "tesseract-ocr" / "5" / "tessdata",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)
    return None


def is_available() -> bool:
    return _tesseract_cmd() is not None


def get_installed_langs() -> list[str]:
    """Return installed Tesseract language codes."""
    cmd = _tesseract_cmd()
    if not cmd:
        return []

    try:
        env = os.environ.copy()
        tessdata_dir = _tessdata_dir(cmd)
        if tessdata_dir:
            env["TESSDATA_PREFIX"] = tessdata_dir

        result = subprocess.run(
            [cmd, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            **_hidden_process_kwargs(),
        )
        lines = (result.stdout + result.stderr).splitlines()
        langs = []
        for line in lines:
            line = line.strip()
            if not line or line == "List of available tessdata:":
                continue
            langs.append(line)
        return langs
    except Exception:
        return []


def has_vietnamese() -> bool:
    langs = get_installed_langs()
    return "vie" in langs


def runtime_status() -> OCRRuntimeStatus:
    cmd = _tesseract_cmd()
    if not cmd:
        return OCRRuntimeStatus(
            available=False,
            languages=[],
            error="Chưa tìm thấy Tesseract OCR. Có thể dùng bản bundle đi kèm app hoặc cài Tesseract vào máy.",
        )
    tessdata = _tessdata_dir(cmd) or ""
    langs = get_installed_langs()
    return OCRRuntimeStatus(
        available=True,
        tesseract_cmd=cmd,
        tessdata_dir=tessdata,
        languages=langs,
        missing_vietnamese="vie" not in langs,
    )


def _preprocess_for_ocr(pil_image, *, denoise: bool = False):
    """Normalize an image before Tesseract: grayscale + contrast stretch,
    optional median denoise for scans. Binarization is left to Tesseract's
    internal Otsu, which handles anti-aliased renders better than a fixed
    threshold."""
    try:
        from PIL import ImageFilter, ImageOps

        img = pil_image.convert("L")
        img = ImageOps.autocontrast(img, cutoff=1)
        if denoise:
            img = img.filter(ImageFilter.MedianFilter(size=3))
        return img
    except Exception:
        return pil_image


def ocr_pil_image(pil_image, page_num: int = 1, high_quality: bool = False) -> OCRResult:
    """
    Recognize text from a PIL Image.
    high_quality=True scales the image up before OCR.
    """
    cmd = _tesseract_cmd()
    if not cmd:
        return OCRResult(text="", page=page_num, word_count=0, error="Tesseract chưa được cài đặt.")

    try:
        import pytesseract

        _configure_pytesseract_no_window(pytesseract)

        pytesseract.pytesseract.tesseract_cmd = cmd
        tessdata_dir = _tessdata_dir(cmd)

        langs = get_installed_langs()
        if "vie" in langs:
            lang = "vie+eng" if "eng" in langs else "vie"
        else:
            lang = "eng"

        psm = "6" if not high_quality else "3"
        config = f"--oem 1 --psm {psm}"
        if tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

        if high_quality:
            from PIL import Image

            w, h = pil_image.size
            scale = 2.0
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        pil_image = _preprocess_for_ocr(pil_image, denoise=high_quality)

        text = pytesseract.image_to_string(pil_image, lang=lang, config=config)
        text = text.strip()
        word_count = len(text.split()) if text else 0
        return OCRResult(text=text, page=page_num, word_count=word_count)
    except Exception as e:
        return OCRResult(text="", page=page_num, word_count=0, error=str(e))


def ocr_pdf_page(pdf_path: str, page_num: int, high_quality: bool = False) -> OCRResult:
    """Render a PDF page and OCR it. page_num starts at 1."""
    try:
        import pypdfium2 as pdfium
        from PIL import Image
        import io
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK

        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                # init_forms() needed for scan files with widget appearances
                try:
                    doc.init_forms()
                except Exception:
                    pass
                page = doc[page_num - 1]
                scale = 3.0 if high_quality else 2.0
                bitmap = page.render(scale=scale)
                pil_img = bitmap.to_pil().convert("RGB")
            finally:
                doc.close()

        return ocr_pil_image(pil_img, page_num=page_num, high_quality=False)
    except Exception as e:
        return OCRResult(text="", page=page_num, word_count=0, error=str(e))


def page_has_text(pdf_path: str, page_num: int, *, min_chars: int = 3) -> bool:
    """Quick check: does this page already have an extractable text layer?

    Used to skip pages that are already searchable (born-digital or already
    OCR'd) so auto-OCR never redoes work.
    """
    try:
        import pypdfium2 as pdfium
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK

        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                page = doc[page_num - 1]
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range().strip()
                finally:
                    textpage.close()
            finally:
                doc.close()
        return len(text) >= min_chars
    except Exception:
        # If we can't tell, don't block auto-OCR on this page.
        return False


def ocr_pdf_page_text_layer(pdf_path: str, page_num: int, *, scale: float = 2.0) -> bytes | None:
    """Render one page and return a Tesseract *text-only* PDF page: a single
    page containing only invisible, correctly-positioned text (no image),
    sized in points to match the rendered scale.

    Meant to be merged onto the original scanned page via
    `merge_text_layer_into_pdf`, so search/highlight/edit-existing-text all
    see a real text layer without altering the visible page image.
    Returns None if OCR is unavailable or recognized no text.
    """
    cmd = _tesseract_cmd()
    if not cmd:
        return None
    try:
        import pypdfium2 as pdfium
        import pytesseract
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK

        _configure_pytesseract_no_window(pytesseract)

        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                page = doc[page_num - 1]
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil().convert("RGB")
            finally:
                doc.close()

        pytesseract.pytesseract.tesseract_cmd = cmd
        tessdata_dir = _tessdata_dir(cmd)
        if tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

        langs = get_installed_langs()
        lang = "vie+eng" if "vie" in langs else "eng"
        pil_image = _preprocess_for_ocr(pil_image)

        # dpi tells Tesseract how many pixels-per-inch the render represents,
        # so the emitted PDF page comes out at the *same physical size* (in
        # points) as the original page — required for the overlay to align.
        dpi = max(70, int(round(scale * 72)))
        config = f"--oem 1 --psm 6 -c textonly_pdf=1 --dpi {dpi}"
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(
            pil_image, lang=lang, config=config, extension="pdf"
        )
        return bytes(pdf_bytes)
    except Exception:
        return None


def merge_text_layer_into_pdf(pdf, page_idx: int, text_layer_pdf_bytes: bytes) -> bool:
    """Overlay a Tesseract text-only PDF page onto `pdf.pages[page_idx]`.

    `pdf` is an already-open `pikepdf.Pdf`; caller is responsible for saving.
    Returns False if the text-only page has no content worth merging.
    """
    import io

    import pikepdf

    with pikepdf.Pdf.open(io.BytesIO(text_layer_pdf_bytes)) as text_pdf:
        if len(text_pdf.pages) == 0:
            return False
        text_page = text_pdf.pages[0]
        target_page = pdf.pages[page_idx]
        # Không truyền rect: mặc định pikepdf dùng trimbox/cropbox/mediabox
        # của target_page — đúng ý muốn vì text-only PDF đã được sinh ra
        # cùng kích thước điểm (points) với trang gốc (xem `dpi` ở trên).
        target_page.add_overlay(text_page)
    return True
