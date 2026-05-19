# PDF Engine Migration

Goal: avoid shipping a closed-source commercial app that depends on AGPL MuPDF/PyMuPDF without a commercial license.

## Current Engines

`PyMuPdfEngine`

- File: `packages/pdf_engine/pymupdf_engine.py`
- Status: optional legacy fallback.
- Supports open, page count, render, decrypt save, blank PDF, text/image edit rebuild.
- Commercial blocker unless a commercial Artifex/PyMuPDF license is purchased. Do not use in commercial builds.

`PdfiumEngine`

- File: `packages/pdf_engine/pdfium_engine.py`
- Status: Phase 0.8 default engine.
- Supports open, page count, render, blank PDF, and text/image edit rebuild through pikepdf/reportlab overlays.
- Default selection. To force legacy prototype engine:

```bash
THREET_READER_PDF_ENGINE=pymupdf python main.py
```

## Required Before Commercial Release

- Add fixture tests for text/image edit rebuild without PyMuPDF.
- Implement password decrypt/save through a compliant non-AGPL library.
- Generate SBOM and third-party notices for PDFium/pypdfium2/qpdf/pikepdf/reportlab.
- Decide whether the Pro edit/sign workflow can ship with replacement engine or requires a commercial SDK/license.
