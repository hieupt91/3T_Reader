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
        import os as _os

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

                try:
                    op_type = op.get("type")

                    if op_type == "text":
                        text = op.get("text", "").strip()
                        if not text:
                            continue
                        from packages.platform.fonts import get_vietnamese_font_path
                        is_bold = bool(op.get("bold"))
                        font_path = get_vietnamese_font_path(bold=is_bold)
                        color = op.get("font_color", (0, 0, 0))
                        fs = max(6, op.get("font_size", 12))
                        rotation = int(op.get("rotation", 0))

                        # insert_textbox nhận fontfile= (không nhận font= object trong 1.27.x)
                        font_kwargs = {"fontfile": font_path} if font_path else {"fontname": "helv"}

                        if rotation != 0:
                            cx = (rect.x0 + rect.x1) / 2
                            cy = (rect.y0 + rect.y1) / 2
                            mat = fitz.Matrix(1, 0, 0, 1, 0, 0).prerotate(rotation)
                            page.insert_textbox(
                                rect, text,
                                fontsize=fs,
                                **font_kwargs,
                                color=color,
                                align=0,
                                morph=(fitz.Point(cx, cy), mat),
                            )
                        else:
                            page.insert_textbox(
                                rect, text,
                                fontsize=fs,
                                **font_kwargs,
                                color=color,
                                align=0,
                            )
                        if op.get("underline"):
                            ul_y = rect.y0 + fs * 1.15
                            if ul_y <= rect.y1:
                                page.draw_line(
                                    fitz.Point(rect.x0, ul_y),
                                    fitz.Point(rect.x1, ul_y),
                                    color=color,
                                    width=max(0.5, fs * 0.07),
                                )

                    elif op_type == "image":
                        image_path = op.get("image_path", "")
                        if not image_path or not _os.path.exists(image_path):
                            continue
                        rotation = int(op.get("rotation", 0))
                        page.insert_image(rect, filename=image_path,
                                          keep_proportion=True, rotate=rotation)

                    elif op_type == "rect":
                        fill = op.get("fill_color", (1.0, 1.0, 1.0))
                        stroke = op.get("stroke_color", fill)
                        page.draw_rect(rect, color=stroke, fill=fill, width=0)

                except Exception:
                    continue  # skip bad op, không crash toàn bộ rebuild

            try:
                doc.save(output_path)
            except Exception as e:
                raise RuntimeError(f"Không lưu được file PDF: {e}") from e
        finally:
            doc.close()
