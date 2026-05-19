from __future__ import annotations

from .base import RenderedPage


class PyMuPdfDocument:
    def __init__(self, path: str):
        import fitz

        self._fitz = fitz
        self._doc = fitz.open(path)

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    @property
    def needs_password(self) -> bool:
        return bool(self._doc.needs_pass)

    def authenticate(self, password: str) -> bool:
        return bool(self._doc.authenticate(password))

    def save_without_encryption(self, output_path: str) -> None:
        self._doc.save(output_path, encryption=self._fitz.PDF_ENCRYPT_NONE)

    def render_page_rgb(self, page_number: int, scale: float = 1.0) -> RenderedPage:
        page = self._doc.load_page(page_number - 1)
        pix = page.get_pixmap(matrix=self._fitz.Matrix(scale, scale), alpha=False)
        return RenderedPage(
            width=pix.width,
            height=pix.height,
            stride=pix.stride,
            samples=bytes(pix.samples),
        )

    def close(self) -> None:
        self._doc.close()


class PyMuPdfEngine:
    """Prototype adapter.

    PyMuPDF/MuPDF has AGPL/commercial licensing implications. Keep all direct
    usage here or in files still marked for migration so replacement remains
    controlled before commercial release.
    """

    def open(self, path: str) -> PyMuPdfDocument:
        return PyMuPdfDocument(path)

    def page_count(self, path: str) -> int:
        doc = self.open(path)
        try:
            return doc.page_count
        finally:
            doc.close()

    def create_blank_pdf(self, output_path: str, width_pt: float, height_pt: float) -> None:
        import fitz

        doc = fitz.open()
        try:
            doc.new_page(width=width_pt, height=height_pt)
            doc.save(output_path)
        finally:
            doc.close()

    def rebuild_pdf_with_ops(self, base_path: str, output_path: str, ops: list[dict]) -> None:
        import fitz

        doc = fitz.open(base_path)
        try:
            for op in ops:
                page_no = int(op.get("page_number", 1))
                if page_no < 1 or page_no > doc.page_count:
                    continue

                page = doc[page_no - 1]
                pdf_left, pdf_bottom, pdf_right, pdf_top = op.get("box", (0, 0, 0, 0))
                page_h = page.rect.height
                rect = fitz.Rect(pdf_left, page_h - pdf_top, pdf_right, page_h - pdf_bottom)

                if op.get("type") == "text":
                    page.insert_textbox(
                        rect,
                        op.get("text", ""),
                        fontsize=op.get("font_size", 12),
                        fontname="helv",
                        color=op.get("font_color", (0, 0, 0)),
                        align=0,
                    )
                elif op.get("type") == "image":
                    image_path = op.get("image_path")
                    if image_path:
                        page.insert_image(rect, filename=image_path, keep_proportion=True)

            doc.save(output_path)
        finally:
            doc.close()
