import os

from .base import PdfDocument, PdfEngine, RenderedPage
from .pdfium_engine import PdfiumEngine


def _build_default_engine() -> PdfEngine:
    engine_name = os.environ.get("THREET_READER_PDF_ENGINE", "").strip().lower()
    if engine_name in {"pymupdf", "fitz", "legacy"}:
        from .pymupdf_engine import PyMuPdfEngine
        return PyMuPdfEngine()
    return PdfiumEngine()


_default_engine = _build_default_engine()


def get_pdf_engine() -> PdfEngine:
    return _default_engine


def __getattr__(name: str):
    if name == "PyMuPdfEngine":
        from .pymupdf_engine import PyMuPdfEngine
        return PyMuPdfEngine
    raise AttributeError(name)


__all__ = [
    "PdfDocument",
    "PdfEngine",
    "PdfiumEngine",
    "RenderedPage",
    "get_pdf_engine",
]
