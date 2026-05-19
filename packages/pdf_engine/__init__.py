from .base import PdfDocument, PdfEngine, RenderedPage
from .pymupdf_engine import PyMuPdfEngine

_default_engine = PyMuPdfEngine()


def get_pdf_engine() -> PdfEngine:
    return _default_engine


__all__ = [
    "PdfDocument",
    "PdfEngine",
    "PyMuPdfEngine",
    "RenderedPage",
    "get_pdf_engine",
]
