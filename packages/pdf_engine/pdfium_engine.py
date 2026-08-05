from __future__ import annotations

import io
import os
import shutil
import threading

from .base import RenderedPage

# PDFium không thread-safe: gọi FPDF_* đồng thời từ 2 thread khác nhau (kể cả
# trên 2 PdfDocument riêng biệt) có thể phá hỏng trạng thái nội bộ của thư viện
# C, gây access violation sập tiến trình (đã tái hiện 3/3 lần: luồng
# ThumbnailLoader render thumbnail đụng luồng auto-OCR đọc cùng lúc). Mọi lệnh
# gọi pypdfium2 trong app phải qua lock này.
PDFIUM_LOCK = threading.RLock()


class PdfiumDocument:
    def __init__(self, path: str):
        import pypdfium2 as pdfium

        self._path = path
        self._pdfium = pdfium
        self._password = None
        self._doc = None
        self._needs_password = False

        try:
            with PDFIUM_LOCK:
                self._doc = pdfium.PdfDocument(path)
                self._init_forms_for_render()
        except Exception as exc:
            if self._is_password_protected(path):
                self._needs_password = True
            else:
                raise exc

    def _init_forms_for_render(self) -> None:
        if self._doc is None or not hasattr(self._doc, "init_forms"):
            return
        try:
            self._doc.init_forms()
        except Exception:
            # Malformed form data must not make ordinary PDF rendering fail.
            pass

    @property
    def page_count(self) -> int:
        if self._doc is None:
            raise RuntimeError("PDF can mat khau de mo.")
        return len(self._doc)

    @property
    def needs_password(self) -> bool:
        return self._needs_password

    def _is_password_protected(self, path: str) -> bool:
        try:
            import pikepdf
        except Exception:
            return False
        try:
            with pikepdf.Pdf.open(path):
                return False
        except pikepdf.PasswordError:
            return True
        except Exception:
            return False

    def authenticate(self, password: str) -> bool:
        try:
            import pikepdf
            with pikepdf.Pdf.open(self._path, password=password):
                pass
        except Exception:
            return False

        self.close()
        try:
            with PDFIUM_LOCK:
                self._doc = self._pdfium.PdfDocument(self._path, password=password)
                self._init_forms_for_render()
        except Exception:
            self._doc = None
        self._password = password
        self._needs_password = False
        return True

    def save_without_encryption(self, output_path: str) -> None:
        if self._password:
            import pikepdf

            with pikepdf.Pdf.open(self._path, password=self._password) as pdf:
                pdf.save(output_path)
        else:
            shutil.copy2(self._path, output_path)

    def render_page_rgb(self, page_number: int, scale: float = 1.0) -> RenderedPage:
        if self._doc is None:
            raise RuntimeError("PDF cần mật khẩu để mở.")
        with PDFIUM_LOCK:
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

    def page_size(self, page_number: int) -> tuple[float, float]:
        if self._doc is None:
            raise RuntimeError("PDF cần mật khẩu để mở.")
        try:
            with PDFIUM_LOCK:
                page = self._doc[page_number - 1]
                width, height = page.get_size()
            return float(width), float(height)
        except Exception:
            return 595.0, 842.0

    def close(self) -> None:
        if self._doc is not None:
            with PDFIUM_LOCK:
                self._doc.close()
            self._doc = None


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

        with PDFIUM_LOCK:
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
        op_type = op.get("type")
        left, bottom, right, top = [float(v) for v in op.get("box", (0, 0, 0, 0))]
        box_width = max(1.0, right - left)
        box_height = max(1.0, top - bottom)
        # UI rotation is expressed in the browser/CSS direction.
        # ReportLab uses PDF coordinates, so invert the angle here to keep
        # saved output visually aligned with the on-screen preview.
        rotation = -float(op.get("rotation", 0) or 0)

        redact_box = op.get("redact_box") if op_type != "redact" else op.get("box")
        if redact_box:
            _draw_redaction_box(
                c,
                redact_box,
                padding=float(op.get("redact_padding", 0.0) or 0.0),
                fill=_rgb_tuple(op.get("fill_color", (1, 1, 1))),
            )
            drew_anything = True
            if op_type == "redact":
                continue

        if op_type == "text":
            text = op.get("text", "")
            if not text:
                continue
            font_size = float(op.get("font_size", 12))
            font_name = _resolve_reportlab_font(
                bool(op.get("bold")),
                str(op.get("font_family", "")),
                italic=bool(op.get("italic")),
                serif=op.get("font_serif"),
            )
            color = _rgb_tuple(op.get("font_color", (0, 0, 0)))
            baseline = op.get("baseline")
            if baseline and not rotation:
                bx, by = [float(v) for v in baseline[:2]]
                _draw_single_line_text(
                    c,
                    text,
                    bx,
                    by,
                    font_size,
                    font_name=font_name,
                    color=color,
                    underline=bool(op.get("underline")),
                )
            else:
                _with_optional_rotation(
                    c,
                    left,
                    bottom,
                    box_width,
                    box_height,
                    rotation,
                    lambda: _draw_text_box(
                        c,
                        text,
                        left if not rotation else -box_width / 2,
                        bottom if not rotation else -box_height / 2,
                        box_width,
                        box_height,
                        font_size,
                        font_name=font_name,
                        color=color,
                        underline=bool(op.get("underline")),
                    ),
                )
            drew_anything = True
        elif op_type == "image":
            image_path = op.get("image_path")
            image_data_url = op.get("image_data_url", "")
            image = None

            if image_path and os.path.exists(image_path):
                image = ImageReader(image_path)
            elif image_data_url and image_data_url.startswith("data:image/"):
                import base64
                try:
                    b64_data = image_data_url.split(",", 1)[1]
                    image_bytes = base64.b64decode(b64_data)
                    image = ImageReader(io.BytesIO(image_bytes))
                except Exception as e:
                    print(f"Error reading image from data_url: {e}")
                    continue

            if not image:
                continue

            _with_optional_rotation(
                c,
                left,
                bottom,
                box_width,
                box_height,
                rotation,
                lambda: c.drawImage(
                    image,
                    left if not rotation else -box_width / 2,
                    bottom if not rotation else -box_height / 2,
                    width=box_width,
                    height=box_height,
                    preserveAspectRatio=True,
                    anchor="c",
                    mask="auto",
                ),
            )
            drew_anything = True
        elif op_type == "rect":
            fill = _rgb_tuple(op.get("fill_color", (1, 1, 1)))
            stroke = _rgb_tuple(op.get("stroke_color", fill))
            c.setFillColorRGB(*fill)
            c.setStrokeColorRGB(*stroke)
            c.rect(left, bottom, box_width, box_height, stroke=1, fill=1)
            drew_anything = True

    if not drew_anything:
        return b""

    c.save()
    return buffer.getvalue()


def _draw_redaction_box(c, box, *, padding: float = 0.0,
                        fill: tuple[float, float, float] = (1, 1, 1)) -> None:
    left, bottom, right, top = [float(v) for v in box]
    left -= padding
    bottom -= padding
    right += padding
    top += padding
    c.setFillColorRGB(*fill)
    c.setStrokeColorRGB(*fill)
    c.rect(left, bottom, max(1.0, right - left), max(1.0, top - bottom), stroke=0, fill=1)


def _build_watermark_overlay(width: float, height: float, text: str,
                              color: tuple, angle: float) -> bytes:
    from reportlab.lib import colors as rl_colors
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width, height))
    r, g, b = (color + (0.6, 0.6, 0.6))[:3]
    c.setFillColor(rl_colors.Color(r, g, b, alpha=0.30))
    font_size = max(18.0, min(width, height) / 6)
    c.setFont(_resolve_reportlab_font(True), font_size)
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(angle)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    return buf.getvalue()


def _rgb_tuple(value) -> tuple[float, float, float]:
    try:
        r, g, b = value[:3]
    except Exception:
        return (0.0, 0.0, 0.0)
    return tuple(max(0.0, min(1.0, float(v))) for v in (r, g, b))


def _resolve_reportlab_font(bold: bool = False, family: str = "", italic: bool = False,
                            serif: bool | None = None) -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if bold and italic:
        fallback = "Helvetica-BoldOblique"
    elif italic:
        fallback = "Helvetica-Oblique"
    elif bold:
        fallback = "Helvetica-Bold"
    else:
        fallback = "Helvetica"
    try:
        import hashlib
        from packages.platform.fonts import get_vietnamese_font_path
        font_path = get_vietnamese_font_path(bold=bold, italic=italic, family=family, serif=serif)
        if not font_path:
            return fallback
        suffix = hashlib.md5(font_path.encode("utf-8")).hexdigest()[:8]
        font_name = f"ThreeTUnicode{'Bold' if bold else ''}{'Italic' if italic else ''}_{suffix}"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception:
        return fallback


def _with_optional_rotation(c, left: float, bottom: float, width: float, height: float,
                            rotation: float, draw_fn) -> None:
    if not rotation:
        draw_fn()
        return
    c.saveState()
    try:
        c.translate(left + width / 2, bottom + height / 2)
        c.rotate(rotation)
        draw_fn()
    finally:
        c.restoreState()


def _draw_text_box(c, text: str, left: float, bottom: float, width: float, height: float,
                   font_size: float, *, font_name: str = "Helvetica",
                   color: tuple[float, float, float] = (0, 0, 0),
                   underline: bool = False) -> None:
    """Draw *text* inside a box, wrapping at word boundaries using actual string widths.

    Uses ``c.stringWidth()`` for accurate proportional-font measurement instead
    of the previous character-count heuristic.
    """
    leading = max(font_size * 1.2, font_size + 2)
    y = max(bottom, bottom + height - font_size)
    min_y = bottom
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*color)
    c.setFont(font_name, font_size)

    for raw_line in text.splitlines() or [text]:
        line = raw_line.strip()
        while line:
            if y < min_y:
                return
            # Find the longest substring that fits within *width*
            # by measuring actual string width (handles proportional fonts).
            if c.stringWidth(line, font_name, font_size) <= width:
                chunk = line
            else:
                # Binary search for the longest prefix that fits
                lo, hi = 1, len(line)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if c.stringWidth(line[:mid], font_name, font_size) <= width:
                        lo = mid
                    else:
                        hi = mid - 1
                # Try to break at last space within the fitted prefix
                chunk = line[:lo]
                if lo < len(line) and " " in chunk:
                    split_at = chunk.rfind(" ")
                    if split_at > 0:
                        chunk = chunk[:split_at]
            c.drawString(left, y, chunk)
            if underline:
                text_width = c.stringWidth(chunk, font_name, font_size)
                c.line(left, y - max(1.0, font_size * 0.12), left + text_width, y - max(1.0, font_size * 0.12))
            line = line[len(chunk):].lstrip()
            y -= leading
        if raw_line == "":
            y -= leading


def _draw_single_line_text(c, text: str, x: float, baseline_y: float,
                           font_size: float, *, font_name: str = "Helvetica",
                           color: tuple[float, float, float] = (0, 0, 0),
                           underline: bool = False) -> None:
    c.setFillColorRGB(*color)
    c.setStrokeColorRGB(*color)
    c.setFont(font_name, font_size)
    line = str(text).splitlines()[0] if str(text).splitlines() else str(text)
    c.drawString(x, baseline_y, line)
    if underline:
        text_width = c.stringWidth(line, font_name, font_size)
        c.line(x, baseline_y - max(1.0, font_size * 0.12), x + text_width, baseline_y - max(1.0, font_size * 0.12))
