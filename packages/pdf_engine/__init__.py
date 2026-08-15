from .base import PdfDocument, PdfEngine, RenderedPage
from .pdfium_engine import PdfiumEngine

# B2 (2026-08-14, Giai đoạn 3): PyMuPDF (AGPL-3.0) đã gỡ hoàn toàn khỏi
# codebase - không còn engine thay thế qua biến môi trường
# THREET_READER_PDF_ENGINE nữa, PdfiumEngine (pypdfium2, BSD-3) là engine
# duy nhất. Xem docs/ROADMAP_PDF_ENGINE_MIGRATION.md.
_default_engine = PdfiumEngine()


def get_pdf_engine() -> PdfEngine:
    return _default_engine


__all__ = [
    "PdfDocument",
    "PdfEngine",
    "PdfiumEngine",
    "RenderedPage",
    "get_pdf_engine",
]
