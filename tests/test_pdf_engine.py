"""Unit tests for packages.pdf_engine — PdfiumEngine operations."""

import os
import pytest

from packages.pdf_engine import get_pdf_engine


@pytest.fixture
def engine():
    return get_pdf_engine()


@pytest.fixture
def sample_pdf(tmp_path, engine):
    """Create a minimal PDF for testing using reportlab (same as engine internals)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    out = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(out), pagesize=letter)
    c.drawString(100, 700, "Page 1")
    c.showPage()
    c.drawString(100, 700, "Page 2")
    c.showPage()
    c.drawString(100, 700, "Page 3")
    c.showPage()
    c.save()
    return str(out)


class TestPageCount:
    def test_page_count(self, engine, sample_pdf):
        assert engine.page_count(sample_pdf) == 3


class TestWatermark:
    def test_watermark_adds_overlay(self, tmp_path, engine, sample_pdf):
        out = tmp_path / "watermarked.pdf"
        engine.watermark_pdf(sample_pdf, str(out), text="CONFIDENTIAL")
        assert out.exists()
        assert out.stat().st_size >= os.stat(sample_pdf).st_size


class TestDeletePages:
    def test_delete_middle_page(self, tmp_path, engine, sample_pdf):
        out = tmp_path / "deleted.pdf"
        engine.delete_pages(sample_pdf, str(out), [1])
        assert engine.page_count(str(out)) == 2

    def test_delete_last_page(self, tmp_path, engine, sample_pdf):
        out = tmp_path / "deleted.pdf"
        engine.delete_pages(sample_pdf, str(out), [2])
        assert engine.page_count(str(out)) == 2


class TestRotatePages:
    def test_rotate_90(self, tmp_path, engine, sample_pdf):
        out = tmp_path / "rotated.pdf"
        engine.rotate_pages(sample_pdf, str(out), {0: 90})
        assert out.exists()
        assert engine.page_count(str(out)) == 3


class TestRebuildOpsRotationConsistency:
    """B16 (QA 2026-08-13): inserted image/text must land in the same spot
    whether the page's current /Rotate was reached by one rotate or several
    - previously pikepdf's add_overlay() baked in a compensation for the
    /Rotate value present at insert time, which drifted on any later
    rotate. Compares a multi-step rotate->insert->rotate path against a
    fresh single-step page built directly at the final rotation."""

    @staticmethod
    def _blank_pdf(tmp_path, name: str, size=(200, 300)):
        import pikepdf

        path = tmp_path / name
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=size)
        pdf.save(str(path))
        pdf.close()
        return str(path)

    @staticmethod
    def _red_dot(tmp_path):
        from PIL import Image

        path = tmp_path / "dot.png"
        Image.new("RGB", (10, 10), (255, 0, 0)).save(path)
        return str(path)

    @staticmethod
    def _red_bbox(pdf_path):
        import numpy as np
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(pdf_path)
        try:
            arr = np.array(doc[0].render(scale=1).to_pil().convert("RGB"))
        finally:
            doc.close()
        mask = (arr[:, :, 0] > 200) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)
        ys, xs = np.where(mask)
        assert len(xs) > 0, "inserted image not found in render"
        return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

    @pytest.mark.parametrize(
        "start_deg,steps",
        [
            (0, []),
            (0, [90]),
            (0, [90, 90]),
            (0, [90, 90, 90]),
            (90, [90]),
            (270, [90, 90]),
        ],
    )
    def test_insert_then_rotate_matches_fresh_page_at_same_final_angle(
        self, tmp_path, engine, start_deg, steps
    ):
        image_path = self._red_dot(tmp_path)
        total = (start_deg + sum(steps)) % 360
        box = {"type": "image", "page_number": 1, "box": (50, 50, 100, 100), "image_path": image_path, "rotation": 0}

        base = self._blank_pdf(tmp_path, f"base_{start_deg}_{steps}.pdf")
        current = base
        if start_deg:
            rotated = str(tmp_path / f"r0_{start_deg}_{steps}.pdf")
            engine.rotate_pages(current, rotated, {1: start_deg})
            current = rotated
        inserted = str(tmp_path / f"ins_{start_deg}_{steps}.pdf")
        engine.rebuild_pdf_with_ops(current, inserted, [box])
        current = inserted
        for i, deg in enumerate(steps):
            stepped = str(tmp_path / f"step_{start_deg}_{i}_{steps}.pdf")
            engine.rotate_pages(current, stepped, {1: deg})
            current = stepped

        fresh_base = self._blank_pdf(tmp_path, f"fresh_{total}.pdf")
        fresh_rotated = fresh_base
        if total:
            fresh_rotated = str(tmp_path / f"fresh_r_{total}.pdf")
            engine.rotate_pages(fresh_base, fresh_rotated, {1: total})
        ground_truth = str(tmp_path / f"fresh_ins_{total}.pdf")
        engine.rebuild_pdf_with_ops(fresh_rotated, ground_truth, [box])

        assert self._red_bbox(current) == self._red_bbox(ground_truth)


class TestMergePdfs:
    def test_merge_two_pdfs(self, tmp_path, engine, sample_pdf):
        out = tmp_path / "merged.pdf"
        engine.merge_pdfs([sample_pdf, sample_pdf], str(out))
        assert engine.page_count(str(out)) == 6


class TestSplitPdf:
    def test_split_range(self, tmp_path, engine, sample_pdf):
        out_dir = tmp_path / "split_out"
        out_dir.mkdir()
        results = engine.split_pdf(sample_pdf, str(out_dir), [(0, 1)])
        assert len(results) >= 1
        for r in results:
            assert engine.page_count(r) >= 1
