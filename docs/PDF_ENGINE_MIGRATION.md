# PDF Engine Migration

Goal: avoid shipping a closed-source commercial app that depends on AGPL MuPDF/PyMuPDF without a commercial license.

## Current Engines

`PyMuPdfEngine`

- File: `packages/pdf_engine/pymupdf_engine.py`
- Status: prototype default.
- Supports open, page count, render, decrypt save, blank PDF, text/image edit rebuild.
- Commercial blocker unless a commercial Artifex/PyMuPDF license is purchased.

`PdfiumEngine`

- File: `packages/pdf_engine/pdfium_engine.py`
- Status: Phase 0.5 experimental engine.
- Supports open, page count, render, blank PDF.
- Does not yet support edit operations.
- Select with:

```bash
THREET_READER_PDF_ENGINE=pdfium python main.py
```

## Required Before Commercial Release

- Implement text/image edit rebuild without PyMuPDF, likely using a dedicated `pikepdf/qpdf` plus overlay generation pipeline.
- Implement password decrypt/save through a compliant non-AGPL library.
- Generate SBOM and third-party notices for PDFium/pypdfium2/qpdf/pikepdf.
- Decide whether the Pro edit/sign workflow can ship with replacement engine or requires a commercial SDK/license.
