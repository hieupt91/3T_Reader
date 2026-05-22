from __future__ import annotations

import io
import os
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

    def watermark_pdf(self, input_path: str, output_path: str, text: str,
                      color: tuple = (0.6, 0.6, 0.6), angle: float = 45.0,
                      apply_to_pages: list[int] | None = None) -> None:
        import pikepdf
        with pikepdf.Pdf.open(input_path) as pdf:
            n = len(pdf.pages)
            targets = apply_to_pages if apply_to_pages else list(range(1, n + 1))
            for pn in targets:
                if pn < 1 or pn > n:
                    continue
                page = pdf.pages[pn - 1]
                w, h = _page_size(page)
                wm_bytes = _build_watermark_overlay(w, h, text, color, angle)
                with pikepdf.Pdf.open(io.BytesIO(wm_bytes)) as wm_pdf:
                    page.add_overlay(wm_pdf.pages[0])
            pdf.save(output_path)

    def delete_pages(self, input_path: str, output_path: str, page_numbers: list[int]) -> None:
        import pikepdf
        with pikepdf.Pdf.open(input_path) as pdf:
            for pn in sorted(set(page_numbers), reverse=True):
                if 1 <= pn <= len(pdf.pages):
                    del pdf.pages[pn - 1]
            pdf.save(output_path)

    def rotate_pages(self, input_path: str, output_path: str, page_rotations: dict) -> None:
        import pikepdf
        with pikepdf.Pdf.open(input_path) as pdf:
            for pn, degrees in page_rotations.items():
                if 1 <= pn <= len(pdf.pages):
                    page = pdf.pages[pn - 1]
                    current = int(page.get("/Rotate", 0))
                    page["/Rotate"] = (current + int(degrees)) % 360
            pdf.save(output_path)

    def merge_pdfs(self, input_paths: list[str], output_path: str) -> None:
        import pikepdf
        out = pikepdf.Pdf.new()
        try:
            for path in input_paths:
                with pikepdf.Pdf.open(path) as src:
                    out.pages.extend(src.pages)
            out.save(output_path)
        finally:
            out.close()

    def split_pdf(self, input_path: str, output_dir: str,
                  page_ranges: list[tuple]) -> list[str]:
        import pikepdf
        base = os.path.splitext(os.path.basename(input_path))[0]
        out_paths: list[str] = []
        with pikepdf.Pdf.open(input_path) as src:
            n = len(src.pages)
            for i, (start, end) in enumerate(page_ranges, start=1):
                part = pikepdf.Pdf.new()
                try:
                    for pn in range(max(1, start), min(end, n) + 1):
                        part.pages.append(src.pages[pn - 1])
                    fname = f"{base}_p{start}-{end}.pdf" if start != end else f"{base}_p{start}.pdf"
                    fpath = os.path.join(output_dir, fname)
                    part.save(fpath)
                    out_paths.append(fpath)
                finally:
                    part.close()
        return out_paths

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
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    drew_anything = False

    for op in ops:
        left, bottom, right, top = [float(v) for v in op.get("box", (0, 0, 0, 0))]
        box_width = max(1.0, right - left)
        box_height = max(1.0, top - bottom)

        if op.get("type") == "text":
            text = op.get("text", "")
            if not text:
                continue
            font_size = float(op.get("font_size", 12))
            c.setFont("Helvetica", font_size)
            _draw_text_box(c, text, left, bottom, box_width, box_height, font_size)
            drew_anything = True
        elif op.get("type") == "image":
            image_path = op.get("image_path")
            if not image_path or not os.path.exists(image_path):
                continue
            c.drawImage(
                ImageReader(image_path),
                left,
                bottom,
                width=box_width,
                height=box_height,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            drew_anything = True

    if not drew_anything:
        return b""

    c.save()
    return buffer.getvalue()


def _build_watermark_overlay(width: float, height: float, text: str,
                              color: tuple, angle: float) -> bytes:
    from reportlab.lib import colors as rl_colors
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width, height))
    r, g, b = (color + (0.6, 0.6, 0.6))[:3]
    c.setFillColor(rl_colors.Color(r, g, b, alpha=0.30))
    font_size = max(18.0, min(width, height) / 6)
    c.setFont("Helvetica-Bold", font_size)
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(angle)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    return buf.getvalue()


def _draw_text_box(c, text: str, left: float, bottom: float, width: float, height: float, font_size: float) -> None:
    leading = max(font_size * 1.2, font_size + 2)
    y = bottom + height - font_size
    min_y = bottom
    max_chars = max(1, int(width / max(font_size * 0.55, 1)))

    for raw_line in text.splitlines() or [text]:
        line = raw_line.strip()
        while line:
            if y < min_y:
                return
            chunk = line[:max_chars]
            if len(line) > max_chars and " " in chunk:
                split_at = chunk.rfind(" ")
                chunk = chunk[:split_at]
            c.drawString(left, y, chunk)
            line = line[len(chunk):].lstrip()
            y -= leading
        if raw_line == "":
            y -= leading
