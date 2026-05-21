from __future__ import annotations

import io
import os
import shutil

from .base import RenderedPage
from packages.platform.fonts import get_vietnamese_font_path


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
    """Commercial-friendlier PDF engine based on PDFium + pikepdf overlays."""

    def open(self, path: str) -> PdfiumDocument:
        return PdfiumDocument(path)

    def page_count(self, path: str) -> int:
        doc = self.open(path)
        try:
            return doc.page_count
        finally:
            doc.close()

    def create_blank_pdf(self, output_path: str, width_pt: float, height_pt: float) -> None:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument.new()
        doc.new_page(width_pt, height_pt)
        doc.save(output_path)
        doc.close()

    def rebuild_pdf_with_ops(self, base_path: str, output_path: str, ops: list[dict]) -> None:
        import pikepdf

        grouped_ops = _group_ops_by_page(ops)
        with pikepdf.Pdf.open(base_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                page_ops = grouped_ops.get(page_index)
                if not page_ops:
                    continue

                width, height = _page_size(page)
                overlay_bytes = _build_overlay_pdf(width, height, page_ops)
                if not overlay_bytes:
                    continue

                with pikepdf.Pdf.open(io.BytesIO(overlay_bytes)) as overlay_pdf:
                    page.add_overlay(overlay_pdf.pages[0])

            pdf.save(output_path)


def _group_ops_by_page(ops: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for op in ops:
        page_number = int(op.get("page_number", 1))
        grouped.setdefault(page_number, []).append(op)
    return grouped


def _page_size(page) -> tuple[float, float]:
    media_box = [float(v) for v in page.MediaBox]
    return (media_box[2] - media_box[0], media_box[3] - media_box[1])


def _build_overlay_pdf(width: float, height: float, ops: list[dict]) -> bytes:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    drew_anything = False
    vietnamese_font = get_vietnamese_font_path()
    font_name = "Helvetica"
    if vietnamese_font:
        try:
            pdfmetrics.registerFont(TTFont("THREETReaderVnFont", vietnamese_font))
            font_name = "THREETReaderVnFont"
        except Exception:
            font_name = "Helvetica"

    for op in ops:
        left, bottom, right, top = [float(v) for v in op.get("box", (0, 0, 0, 0))]
        box_width = max(1.0, right - left)
        box_height = max(1.0, top - bottom)
        rotation = int(op.get("rotation", 0)) % 360

        if op.get("type") == "text":
            text = op.get("text", "")
            if not text:
                continue
            font_size = float(op.get("font_size", 12))
            font_color = op.get("font_color", (0.0, 0.0, 0.0))
            try:
                r, g, b = [float(v) for v in font_color]
            except Exception:
                r, g, b = (0.0, 0.0, 0.0)
            c.setFillColorRGB(r, g, b)
            c.setFont(font_name, font_size)
            _draw_rotated_text_box(
                c,
                text,
                left,
                bottom,
                box_width,
                box_height,
                font_size,
                rotation,
                bold=bool(op.get("bold", False)),
                underline=bool(op.get("underline", False)),
            )
            drew_anything = True
        elif op.get("type") == "image":
            image_path = op.get("image_path")
            if not image_path or not os.path.exists(image_path):
                continue
            _draw_rotated_image(c, ImageReader(image_path), left, bottom, box_width, box_height, rotation)
            drew_anything = True

    if not drew_anything:
        return b""

    c.save()
    return buffer.getvalue()


def _draw_text_box(
    c,
    text: str,
    left: float,
    bottom: float,
    width: float,
    height: float,
    font_size: float,
    *,
    bold: bool = False,
    underline: bool = False,
) -> None:
    leading = max(font_size * 1.2, font_size + 2)
    y = bottom + height - font_size
    min_y = bottom
    max_chars = max(1, int(width / max(font_size * 0.55, 1)))

    lines = text.split("\n") if text else [text]
    for raw_line in lines:
        line = raw_line.rstrip("\r")
        while line:
            if y < min_y:
                return
            chunk = line[:max_chars]
            if len(line) > max_chars and " " in chunk:
                split_at = chunk.rfind(" ")
                chunk = chunk[:split_at]
            c.drawString(left, y, chunk)
            if bold:
                c.drawString(left + 0.5, y, chunk)
            if underline:
                underline_y = y - max(1.0, font_size * 0.12)
                c.setLineWidth(max(0.8, font_size * 0.06))
                c.line(left, underline_y, left + min(width, max(font_size, len(chunk) * font_size * 0.55)), underline_y)
            line = line[len(chunk):].lstrip()
            y -= leading
        if raw_line == "":
            y -= leading


def _draw_rotated_text_box(
    c,
    text: str,
    left: float,
    bottom: float,
    width: float,
    height: float,
    font_size: float,
    rotation: int,
    *,
    bold: bool = False,
    underline: bool = False,
) -> None:
    if rotation == 0:
        _draw_text_box(c, text, left, bottom, width, height, font_size, bold=bold, underline=underline)
        return
    cx = left + (width / 2.0)
    cy = bottom + (height / 2.0)
    c.saveState()
    c.translate(cx, cy)
    c.rotate(rotation)
    _draw_text_box(
        c,
        text,
        -(width / 2.0),
        -(height / 2.0),
        width,
        height,
        font_size,
        bold=bold,
        underline=underline,
    )
    c.restoreState()


def _draw_rotated_image(c, image_reader, left: float, bottom: float, width: float, height: float, rotation: int) -> None:
    if rotation == 0:
        c.drawImage(
            image_reader,
            left,
            bottom,
            width=width,
            height=height,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
        return
    cx = left + (width / 2.0)
    cy = bottom + (height / 2.0)
    c.saveState()
    c.translate(cx, cy)
    c.rotate(rotation)
    c.drawImage(
        image_reader,
        -(width / 2.0),
        -(height / 2.0),
        width=width,
        height=height,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )
    c.restoreState()
