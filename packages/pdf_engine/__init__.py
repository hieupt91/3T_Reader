import os

from .base import PdfDocument, PdfEngine, RenderedPage
from .pdfium_engine import PdfiumEngine


def _build_default_engine() -> PdfEngine:
    engine_name = os.environ.get("THREET_READER_PDF_ENGINE", "").strip().lower()
    if engine_name in {"pymupdf", "fitz", "legacy"}:
        from .pymupdf_engine import PyMuPdfEngine
        return PyMuPdfEngine()
    if engine_name == "pdfium":
        return PdfiumEngine()
    # Auto-detect: dùng PdfiumEngine nếu pikepdf có sẵn, không thì PyMuPdfEngine
    try:
        import pikepdf  # noqa: F401
        return PdfiumEngine()
    except ImportError:
        return PyMuPdfEngine()


_default_engine = _build_default_engine()


def get_pdf_engine() -> PdfEngine:
    return _default_engine


__all__ = [
    "PdfDocument",
    "PdfEngine",
    "PdfiumEngine",
    "RenderedPage",
    "get_pdf_engine",
]
