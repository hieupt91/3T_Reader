import os

from .base import PdfDocument, PdfEngine, RenderedPage
from .pdfium_engine import PdfiumEngine
from .pymupdf_engine import PyMuPdfEngine


def _build_default_engine() -> PdfEngine:
    engine_name = os.environ.get("THREET_READER_PDF_ENGINE", "pymupdf").strip().lower()
    if engine_name in {"pdfium", "pypdfium2"}:
        return PdfiumEngine()
    return PyMuPdfEngine()


_default_engine = _build_default_engine()


def get_pdf_engine() -> PdfEngine:
    return _default_engine


__all__ = [
    "PdfDocument",
    "PdfEngine",
    "PdfiumEngine",
    "PyMuPdfEngine",
    "RenderedPage",
    "get_pdf_engine",
]
