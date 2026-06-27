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

    def page_size(self, page_number: int) -> tuple[float, float]:
        page = self._doc.load_page(page_number - 1)
        return float(page.rect.width), float(page.rect.height)

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

        def _rgb_tuple(value, default=(0.0, 0.0, 0.0)):
            try:
                r, g, b = value[:3]
                values = []
                for item in (r, g, b):
                    item = float(item)
                    values.append(item / 255.0 if item > 1.0 else item)
                return tuple(max(0.0, min(1.0, item)) for item in values)
            except Exception:
                return default

        def _rect_from_pdf_box(page, box):
            pdf_left, pdf_bottom, pdf_right, pdf_top = [float(v) for v in box]
            unrot_h = page.cropbox.height
            pt1_unrot = fitz.Point(pdf_left, unrot_h - pdf_top)
            pt2_unrot = fitz.Point(pdf_right, unrot_h - pdf_bottom)
            pt1_rot = pt1_unrot * page.rotation_matrix
            pt2_rot = pt2_unrot * page.rotation_matrix
            return fitz.Rect(pt1_rot, pt2_rot)

        doc = fitz.open(base_path)
        try:
            redaction_pages = set()
            for op in ops:
                page_no = int(op.get("page_number", 1))
                if page_no < 1 or page_no > doc.page_count:
                    continue
                op_type = op.get("type")
                redact_box = op.get("redact_box") if op_type != "redact" else op.get("box")
                if not redact_box:
                    continue
                page = doc[page_no - 1]
                rect = _rect_from_pdf_box(page, redact_box)
                padding = float(op.get("redact_padding", 0.0) or 0.0)
                if padding:
                    rect = rect + (-padding, -padding, padding, padding)
                page.add_redact_annot(rect, fill=_rgb_tuple(op.get("fill_color", (1, 1, 1)), default=(1, 1, 1)))
                redaction_pages.add(page_no)

            for page_no in sorted(redaction_pages):
                page = doc[page_no - 1]
                try:
                    page.apply_redactions(images=2, graphics=2)
                except TypeError:
                    page.apply_redactions(images=2)

            for op in ops:
                page_no = int(op.get("page_number", 1))
                if page_no < 1 or page_no > doc.page_count:
                    continue

                page = doc[page_no - 1]
                rect = _rect_from_pdf_box(page, op.get("box", (0, 0, 0, 0)))

                try:
                    op_type = op.get("type")
                    if op_type == "redact":
                        continue

                    if op_type == "text":
                        text = op.get("text", "").strip()
                        if not text:
                            continue
                        from packages.platform.fonts import get_vietnamese_font_path
                        is_bold = bool(op.get("bold"))
                        is_italic = bool(op.get("italic"))
                        font_family = op.get("font_family", "").lower()
                        # Pass family hint to our font finder
                        font_path = get_vietnamese_font_path(bold=is_bold, italic=is_italic, family=font_family)
                        color = _rgb_tuple(op.get("font_color", (0.0, 0.0, 0.0)))

                        fs = max(6, op.get("font_size", 12))
                        rotation = int(op.get("rotation", 0))

                        font_kwargs = {"fontname": "helv"}
                        if font_path:
                            import hashlib
                            font_hash = "f" + hashlib.md5(font_path.encode()).hexdigest()[:8]
                            try:
                                page.insert_font(fontname=font_hash, fontfile=font_path)
                                font_kwargs = {"fontname": font_hash}
                            except Exception as e:
                                print(f"Error inserting font {font_path}: {e}")
                                pass

                        bg_color = op.get("background_color")
                        text_str = op.get("text", "")
                        if bg_color and isinstance(bg_color, str) and bg_color.startswith("#") and len(bg_color) == 7:
                            r = int(bg_color[1:3], 16) / 255.0
                            g = int(bg_color[3:5], 16) / 255.0
                            b = int(bg_color[5:7], 16) / 255.0

                            # Estimate width of new text to cover old text completely
                            estimated_width = len(text_str) * (fs * 0.55)
                            bg_rect = fitz.Rect(rect.x0, rect.y0, max(rect.x1, rect.x0 + estimated_width), rect.y1)
                            page.draw_rect(bg_rect, color=None, fill=(r, g, b))

                        baseline = op.get("baseline")
                        if baseline and rotation == 0:
                            bx, by = [float(v) for v in baseline[:2]]
                            baseline_pt = fitz.Point(bx, page.cropbox.height - by) * page.rotation_matrix
                            page.insert_text(
                                baseline_pt,
                                text_str.splitlines()[0] if text_str.splitlines() else text_str,
                                fontsize=fs,
                                **font_kwargs,
                                color=color,
                            )
                            continue

                        # Expand width to 2000 to prevent clipping horizontally if text is long
                        text_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + 2000, rect.y1)
                        if rotation != 0:
                            cx = (rect.x0 + rect.x1) / 2
                            cy = (rect.y0 + rect.y1) / 2
                            mat = fitz.Matrix(1, 0, 0, 1, 0, 0).prerotate(rotation)
                            rc = page.insert_textbox(
                                text_rect, text_str,
                                fontsize=fs,
                                **font_kwargs,
                                color=color,
                                align=0,
                                morph=(fitz.Point(cx, cy), mat),
                            )
                            if rc < 0:
                                page.insert_text(
                                    fitz.Point(rect.x0, rect.y1), text_str,
                                    fontsize=fs,
                                    **font_kwargs,
                                    color=color,
                                    morph=(fitz.Point(cx, cy), mat),
                                )
                        else:
                            rc = page.insert_textbox(
                                text_rect, text_str,
                                fontsize=fs,
                                **font_kwargs,
                                color=color,
                                align=0,
                            )
                            if rc < 0:
                                page.insert_text(
                                    fitz.Point(rect.x0, rect.y1), text_str,
                                    fontsize=fs,
                                    **font_kwargs,
                                    color=color,
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
                        image_data_url = op.get("image_data_url", "")
                        rotation = int(op.get("rotation", 0))
                        
                        if image_path and _os.path.exists(image_path):
                            page.insert_image(rect, filename=image_path,
                                              keep_proportion=True, rotate=rotation)
                        elif image_data_url and image_data_url.startswith("data:image/"):
                            import base64
                            try:
                                b64_data = image_data_url.split(",", 1)[1]
                                image_bytes = base64.b64decode(b64_data)
                                page.insert_image(rect, stream=image_bytes,
                                                  keep_proportion=True, rotate=rotation)
                            except Exception as e:
                                print(f"Error inserting image from data_url: {e}")
                                continue
                        else:
                            continue

                    elif op_type == "rect":
                        fill = op.get("fill_color", (1.0, 1.0, 1.0))
                        stroke = op.get("stroke_color", fill)
                        page.draw_rect(rect, color=stroke, fill=fill, width=0)

                except Exception as e:
                    import traceback
                    print(f"Error rebuilding op {op_type}: {e}")
                    traceback.print_exc()
                    continue  # skip bad op, không crash toàn bộ rebuild

            try:
                doc.save(output_path)
            except Exception as e:
                raise RuntimeError(f"Không lưu được file PDF: {e}") from e
        finally:
            doc.close()
