"""
Fixture tests for the non-AGPL PDF edit pipeline.

Coverage:
- PdfiumEngine.create_blank_pdf()  → pypdfium2
- PdfiumEngine.open() / page_count → pypdfium2
- _build_overlay_pdf() text op     → reportlab only (no pikepdf needed)
- _build_overlay_pdf() image op    → reportlab + Pillow
- PdfiumEngine.rebuild_pdf_with_ops() → pikepdf + reportlab (skipped if pikepdf missing)

None of these tests use PyMuPDF / fitz (AGPL). The legacy engine is NOT imported here.
"""
import io
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Dependency guards
# ---------------------------------------------------------------------------

def _skip_if_missing(*packages):
    missing = []
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        pytest.skip(f"Missing dependencies: {missing}")


# ---------------------------------------------------------------------------
# PdfiumEngine — create_blank_pdf
# ---------------------------------------------------------------------------

class TestPdfiumEngineCreateBlank:
    def test_create_blank_pdf_creates_file(self, tmp_path):
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        out = str(tmp_path / "blank.pdf")
        engine = PdfiumEngine()
        engine.create_blank_pdf(out, width_pt=595, height_pt=842)

        assert os.path.exists(out)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_create_blank_pdf_has_one_page(self, tmp_path):
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        out = str(tmp_path / "blank.pdf")
        engine = PdfiumEngine()
        engine.create_blank_pdf(out, width_pt=595, height_pt=842)

        doc = engine.open(out)
        try:
            assert doc.page_count == 1
        finally:
            doc.close()

    def test_create_blank_pdf_custom_size(self, tmp_path):
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        out = str(tmp_path / "letter.pdf")
        engine = PdfiumEngine()
        engine.create_blank_pdf(out, width_pt=612, height_pt=792)

        assert os.path.exists(out)


# ---------------------------------------------------------------------------
# PdfiumEngine — open / page_count
# ---------------------------------------------------------------------------

class TestPdfiumEngineOpen:
    def _make_pdf(self, tmp_path, pages=2) -> str:
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        engine = PdfiumEngine()
        path = str(tmp_path / "multi.pdf")
        # Create multi-page via pypdfium2 directly
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument.new()
        for _ in range(pages):
            doc.new_page(595, 842)
        doc.save(path)
        doc.close()
        return path

    def test_open_returns_document(self, tmp_path):
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        path = self._make_pdf(tmp_path)
        engine = PdfiumEngine()
        doc = engine.open(path)
        assert doc is not None
        doc.close()

    def test_page_count_correct(self, tmp_path):
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        path = self._make_pdf(tmp_path, pages=3)
        engine = PdfiumEngine()
        assert engine.page_count(path) == 3

    def test_needs_password_false_for_unencrypted(self, tmp_path):
        _skip_if_missing("pypdfium2")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        path = self._make_pdf(tmp_path)
        engine = PdfiumEngine()
        doc = engine.open(path)
        assert doc.needs_password is False
        doc.close()


# ---------------------------------------------------------------------------
# _build_overlay_pdf — reportlab (no pikepdf needed)
# ---------------------------------------------------------------------------

class TestBuildOverlayPdf:
    def test_text_op_produces_pdf_bytes(self):
        _skip_if_missing("reportlab")
        from packages.pdf_engine.pdfium_engine import _build_overlay_pdf

        ops = [{"type": "text", "text": "Hello 3T", "box": (50, 700, 250, 750), "font_size": 12}]
        result = _build_overlay_pdf(595, 842, ops)
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_empty_ops_returns_empty_bytes(self):
        _skip_if_missing("reportlab")
        from packages.pdf_engine.pdfium_engine import _build_overlay_pdf

        result = _build_overlay_pdf(595, 842, [])
        assert result == b""

    def test_image_op_with_valid_file(self, tmp_path):
        _skip_if_missing("reportlab", "PIL")
        from packages.pdf_engine.pdfium_engine import _build_overlay_pdf
        from PIL import Image

        img_path = str(tmp_path / "test_img.png")
        img = Image.new("RGB", (100, 50), color=(255, 0, 0))
        img.save(img_path)

        ops = [{"type": "image", "image_path": img_path, "box": (100, 600, 300, 700)}]
        result = _build_overlay_pdf(595, 842, ops)
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_image_op_missing_file_returns_empty(self, tmp_path):
        _skip_if_missing("reportlab")
        from packages.pdf_engine.pdfium_engine import _build_overlay_pdf

        ops = [{"type": "image", "image_path": "/nonexistent/path.png", "box": (100, 600, 300, 700)}]
        result = _build_overlay_pdf(595, 842, ops)
        assert result == b""

    def test_text_multiline_wraps_correctly(self):
        _skip_if_missing("reportlab")
        from packages.pdf_engine.pdfium_engine import _build_overlay_pdf

        long_text = "Đây là một đoạn văn bản dài để kiểm tra khả năng xuống dòng tự động trong hộp PDF"
        ops = [{"type": "text", "text": long_text, "box": (50, 600, 250, 720), "font_size": 10}]
        result = _build_overlay_pdf(595, 842, ops)
        assert result[:4] == b"%PDF"


class TestAnnotateMultilineSearch:
    def test_search_text_on_page_handles_selection_spanning_lines(self, tmp_path):
        _skip_if_missing("reportlab", "pdfplumber", "pypdfium2")
        from reportlab.pdfgen import canvas
        from app.actions.annotate import _search_text_on_page

        out = str(tmp_path / "multiline.pdf")
        c = canvas.Canvas(out, pagesize=(595, 842))
        c.drawString(50, 760, "Doan van ban nay co")
        c.drawString(50, 740, "nhieu dong de kiem tra")
        c.save()

        rects = _search_text_on_page(
            out,
            1,
            "Doan van ban nay co\nnhieu dong de kiem tra",
        )

        assert len(rects) >= 2
        assert all(len(rect) == 4 for rect in rects)


# ---------------------------------------------------------------------------
# PdfiumEngine.rebuild_pdf_with_ops — requires pikepdf
# ---------------------------------------------------------------------------

class TestRebuildPdfWithOps:
    def _make_blank_pdf(self, tmp_path) -> str:
        _skip_if_missing("pypdfium2")
        import pypdfium2 as pdfium
        path = str(tmp_path / "base.pdf")
        doc = pdfium.PdfDocument.new()
        doc.new_page(595, 842)
        doc.save(path)
        doc.close()
        return path

    def test_text_overlay_produces_valid_pdf(self, tmp_path):
        _skip_if_missing("pypdfium2", "pikepdf", "reportlab")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        base = self._make_blank_pdf(tmp_path)
        out = str(tmp_path / "output.pdf")
        ops = [{"type": "text", "text": "3T Reader Test", "box": (50, 700, 300, 750),
                "page_number": 1, "font_size": 12}]
        PdfiumEngine().rebuild_pdf_with_ops(base, out, ops)

        assert os.path.exists(out)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_no_ops_copies_file_unchanged(self, tmp_path):
        _skip_if_missing("pypdfium2", "pikepdf", "reportlab")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        base = self._make_blank_pdf(tmp_path)
        out = str(tmp_path / "copy.pdf")
        PdfiumEngine().rebuild_pdf_with_ops(base, out, [])

        assert os.path.exists(out)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_rotated_text_overlay_produces_valid_pdf(self, tmp_path):
        _skip_if_missing("pypdfium2", "pikepdf", "reportlab")
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        base = self._make_blank_pdf(tmp_path)
        out = str(tmp_path / "rotated.pdf")
        ops = [{"type": "text", "text": "Rotate me", "box": (50, 700, 300, 750),
                "page_number": 1, "font_size": 12, "rotation": 90}]
        PdfiumEngine().rebuild_pdf_with_ops(base, out, ops)

        assert os.path.exists(out)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_redact_box_visually_covers_existing_text(self, tmp_path):
        _skip_if_missing("pypdfium2", "pikepdf", "reportlab", "PIL")
        import pypdfium2 as pdfium
        from reportlab.pdfgen import canvas
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        base = str(tmp_path / "base_text.pdf")
        c = canvas.Canvas(base, pagesize=(300, 200))
        c.setFont("Helvetica", 14)
        c.drawString(50, 150, "XXXXXXXXXX")
        c.save()

        out = str(tmp_path / "redacted_text.pdf")
        ops = [{
            "type": "text",
            "text": "OK",
            "box": (50, 145, 180, 165),
            "redact_box": (48, 145, 150, 168),
            "redact_padding": 2,
            "page_number": 1,
            "font_size": 14,
        }]
        PdfiumEngine().rebuild_pdf_with_ops(base, out, ops)

        pdf = pdfium.PdfDocument(out)
        try:
            image = pdf[0].render(scale=2).to_pil().convert("RGB")
        finally:
            pdf.close()

        # Sample where the original right-side X glyphs were. The replacement
        # text is on the left, so this region should be clean white.
        crop = image.crop((110 * 2, (200 - 160) * 2, 145 * 2, (200 - 150) * 2))
        data = crop.tobytes()
        total = len(data) // 3
        white = sum(
            1
            for offset in range(0, len(data), 3)
            if data[offset] > 245 and data[offset + 1] > 245 and data[offset + 2] > 245
        )
        assert white / total > 0.98

    def test_text_still_draws_when_box_is_shorter_than_font(self, tmp_path):
        _skip_if_missing("pypdfium2", "pikepdf", "reportlab", "PIL")
        import pypdfium2 as pdfium
        from reportlab.pdfgen import canvas
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        base = str(tmp_path / "short_box_base.pdf")
        c = canvas.Canvas(base, pagesize=(300, 200))
        c.setFont("Helvetica", 14)
        c.drawString(50, 150, "OLD TEXT")
        c.save()

        out = str(tmp_path / "short_box_out.pdf")
        ops = [{
            "type": "text",
            "text": "NEW",
            "box": (50, 150, 150, 158),
            "redact_box": (50, 150, 120, 158),
            "redact_padding": 2,
            "page_number": 1,
            "font_size": 14,
        }]
        PdfiumEngine().rebuild_pdf_with_ops(base, out, ops)

        pdf = pdfium.PdfDocument(out)
        try:
            image = pdf[0].render(scale=2).to_pil().convert("RGB")
        finally:
            pdf.close()

        crop = image.crop((50 * 2, (200 - 160) * 2, 100 * 2, (200 - 145) * 2))
        data = crop.tobytes()
        total = len(data) // 3
        dark = sum(
            1
            for offset in range(0, len(data), 3)
            if data[offset] < 80 and data[offset + 1] < 80 and data[offset + 2] < 80
        )
        assert dark / total > 0.01

    def test_existing_text_edit_uses_original_baseline(self, tmp_path):
        _skip_if_missing("pypdfium2", "pikepdf", "reportlab", "PIL")
        import pypdfium2 as pdfium
        from reportlab.pdfgen import canvas
        from packages.pdf_engine.pdfium_engine import PdfiumEngine

        base = str(tmp_path / "baseline_base.pdf")
        c = canvas.Canvas(base, pagesize=(300, 200))
        c.setFont("Times-Roman", 14)
        c.drawString(50, 150, "OLD TEXT")
        c.save()

        out = str(tmp_path / "baseline_out.pdf")
        ops = [{
            "type": "text",
            "text": "NEW TEXT",
            "box": (50, 145, 180, 165),
            "redact_box": (48, 145, 135, 168),
            "redact_padding": 2,
            "baseline": (50, 150),
            "page_number": 1,
            "font_size": 14,
            "font_family": "Times-Roman",
        }]
        PdfiumEngine().rebuild_pdf_with_ops(base, out, ops)

        pdf = pdfium.PdfDocument(out)
        try:
            image = pdf[0].render(scale=2).to_pil().convert("RGB")
        finally:
            pdf.close()

        expected_line_crop = image.crop((50 * 2, (200 - 166) * 2, 145 * 2, (200 - 145) * 2))
        wrong_lower_crop = image.crop((50 * 2, (200 - 140) * 2, 145 * 2, (200 - 126) * 2))

        def dark_count(img):
            data = img.tobytes()
            return sum(
                1
                for offset in range(0, len(data), 3)
                if data[offset] < 80 and data[offset + 1] < 80 and data[offset + 2] < 80
            )

        assert dark_count(expected_line_crop) > 20
        assert dark_count(expected_line_crop) > dark_count(wrong_lower_crop) * 5


# ---------------------------------------------------------------------------
# Verify PyMuPDF / fitz NOT imported by non-AGPL path
# ---------------------------------------------------------------------------

class TestNoPyMuPdfInDefaultPath:
    def test_pdfium_engine_does_not_import_fitz(self):
        """Importing PdfiumEngine must NOT cause fitz/PyMuPDF to be loaded."""
        # Ensure fitz is not already loaded
        fitz_loaded_before = "fitz" in sys.modules or "pymupdf" in sys.modules
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        fitz_loaded_after = "fitz" in sys.modules or "pymupdf" in sys.modules
        if not fitz_loaded_before:
            assert not fitz_loaded_after, "PdfiumEngine must not import fitz/PyMuPDF"

    def test_default_engine_is_pdfium(self):
        from packages.pdf_engine import PdfiumEngine, get_pdf_engine
        engine = get_pdf_engine()
        assert isinstance(engine, PdfiumEngine)

    def test_pymupdf_engine_module_no_longer_exists(self):
        """B2 Giai đoạn 3 (2026-08-14): PyMuPDF (AGPL-3.0) đã gỡ hoàn toàn -
        không còn packages/pdf_engine/pymupdf_engine.py, không còn engine
        thay thế nào dùng fitz. Test này khoá lại kết luận đó - nếu ai vô
        tình thêm lại module này, test sẽ fail để nhắc rà soát lại quyết
        định pháp lý trước khi merge."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("packages.pdf_engine.pymupdf_engine")

    def test_package_wildcard_import_does_not_import_pymupdf(self):
        # Other test modules may legitimately import fitz (handwritten signing);
        # only assert on modules this wildcard import itself pulls in.
        fitz_loaded_before = "fitz" in sys.modules or "pymupdf" in sys.modules
        namespace = {}
        exec("from packages.pdf_engine import *", namespace)
        assert "PyMuPdfEngine" not in namespace
        if not fitz_loaded_before:
            assert "fitz" not in sys.modules
            assert "pymupdf" not in sys.modules
