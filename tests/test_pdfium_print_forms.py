from __future__ import annotations

import sys
from types import SimpleNamespace


def test_pdfium_document_initializes_forms_for_print_render(monkeypatch, tmp_path):
    from packages.pdf_engine import pdfium_engine

    calls = []

    class FakePdfDocument:
        def __init__(self, path, password=None):
            calls.append(("open", path, password))

        def init_forms(self):
            calls.append(("init_forms",))

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=FakePdfDocument))

    doc = pdfium_engine.PdfiumDocument(str(tmp_path / "signed_scan.pdf"))
    try:
        assert calls == [("open", str(tmp_path / "signed_scan.pdf"), None), ("init_forms",)]
    finally:
        doc.close()


def test_pdfium_print_render_includes_signature_widget_appearance(tmp_path):
    import pikepdf
    import pypdfium2 as pdfium
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK, PdfiumDocument

    base = tmp_path / "scan_page.pdf"
    signed = tmp_path / "scan_with_stamp_widget.pdf"

    c = canvas.Canvas(str(base), pagesize=A4)
    c.drawString(80, 780, "SCAN PAGE WITH SIGNATURE WIDGET")
    c.showPage()
    c.save()

    with pikepdf.Pdf.open(str(base)) as pdf:
        page = pdf.pages[0]
        appearance = pikepdf.Stream(pdf, b"q 1 0 0 rg 0 0 120 50 re f Q")
        appearance["/Type"] = pikepdf.Name("/XObject")
        appearance["/Subtype"] = pikepdf.Name("/Form")
        appearance["/BBox"] = pikepdf.Array([0, 0, 120, 50])
        appearance["/Resources"] = pikepdf.Dictionary()

        annot = pikepdf.Dictionary(
            {
                "/Type": pikepdf.Name("/Annot"),
                "/Subtype": pikepdf.Name("/Widget"),
                "/FT": pikepdf.Name("/Sig"),
                "/Rect": pikepdf.Array([100, 600, 220, 650]),
                "/F": 4,
                "/T": pikepdf.String("Sig1"),
                "/AP": pikepdf.Dictionary({"/N": appearance}),
            }
        )
        annot_ref = pdf.make_indirect(annot)
        page.obj["/Annots"] = pikepdf.Array([annot_ref])
        pdf.Root["/AcroForm"] = pikepdf.Dictionary(
            {"/Fields": pikepdf.Array([annot_ref]), "/SigFlags": 3}
        )
        pdf.save(str(signed))

    def count_red(samples: bytes) -> int:
        return sum(
            1
            for idx in range(0, len(samples), 3)
            if samples[idx] > 180 and samples[idx + 1] < 80 and samples[idx + 2] < 80
        )

    with PDFIUM_LOCK:
        raw_doc = pdfium.PdfDocument(str(signed))
        raw_page = raw_doc[0]
        raw_bitmap = raw_page.render(scale=2)
        raw_image = raw_bitmap.to_pil().convert("RGB")
        raw_red = count_red(raw_image.tobytes())
        raw_doc.close()

    doc = PdfiumDocument(str(signed))
    try:
        rendered = doc.render_page_rgb(1, scale=2)
    finally:
        doc.close()

    assert raw_red == 0
    assert count_red(rendered.samples) > 10_000
