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
