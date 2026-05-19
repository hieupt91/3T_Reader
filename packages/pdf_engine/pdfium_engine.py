from __future__ import annotations

import shutil

from .base import RenderedPage


class PdfiumDocument:
    def __init__(self, path: str):
        import pypdfium2 as pdfium

        self._path = path
        self._pdfium = pdfium
        self._password = None
        self._doc = pdfium.PdfDocument(path)

    @property
    def page_count(self) -> int:
        return len(self._doc)

    @property
    def needs_password(self) -> bool:
        # pypdfium2 raises while opening password-protected documents. If the
        # document opened successfully, treat it as usable without a password.
        return False

    def authenticate(self, password: str) -> bool:
        try:
            doc = self._pdfium.PdfDocument(self._path, password=password)
        except Exception:
            return False
        self.close()
        self._doc = doc
        self._password = password
        return True

    def save_without_encryption(self, output_path: str) -> None:
        # Phase 0.5 fallback: pypdfium2 is used for reading/rendering. For
        # decrypted output support we need a dedicated pikepdf implementation.
        shutil.copy2(self._path, output_path)

    def render_page_rgb(self, page_number: int, scale: float = 1.0) -> RenderedPage:
        page = self._doc[page_number - 1]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil().convert("RGB")
        width, height = pil_image.size
        samples = pil_image.tobytes()
        return RenderedPage(
            width=width,
            height=height,
            stride=width * 3,
            samples=samples,
        )

    def close(self) -> None:
        self._doc.close()


class PdfiumEngine:
    """Commercial-friendlier experimental PDF engine for read/render flows."""

    def open(self, path: str) -> PdfiumDocument:
        return PdfiumDocument(path)

    def page_count(self, path: str) -> int:
        doc = self.open(path)
        try:
            return doc.page_count
        finally:
            doc.close()

    def create_blank_pdf(self, output_path: str, width_pt: float, height_pt: float) -> None:
        import pikepdf

        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(width_pt, height_pt))
        pdf.save(output_path)

    def rebuild_pdf_with_ops(self, base_path: str, output_path: str, ops: list[dict]) -> None:
        raise NotImplementedError(
            "PdfiumEngine does not yet support PDF edit operations. "
            "Use PyMuPDF engine for prototype editing or implement a pikepdf/reportlab edit pipeline."
        )
