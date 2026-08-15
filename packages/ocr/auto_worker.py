"""Isolated helper for automatic OCR.

It deliberately runs outside the Qt GUI process: PDFium/Tesseract failures
must be reported as a failed page, never terminate the document viewer.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        return 2
    pdf_path, page_raw, output_path = args
    try:
        page = int(page_raw)
        if page < 1:
            return 2
        from packages.ocr.engine import ocr_pdf_page_text_layer

        data = ocr_pdf_page_text_layer(pdf_path, page)
        if not data:
            return 1
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_bytes(data)
        os.replace(temp, output)
        return 0
    except Exception:
        return 1
