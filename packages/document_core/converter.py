"""PDF conversion utilities — PDF → Word (.docx) and PDF → Excel (.xlsx).

Dependencies (install separately, not in core requirements):
    pip install pdf2docx pdfplumber openpyxl

Both conversions run in a background thread to avoid blocking the UI.
"""
from __future__ import annotations

import os
from typing import Callable


def convert_pdf_to_docx(
    pdf_path: str,
    output_path: str,
    *,
    progress_cb: Callable[[str], None] | None = None,
) -> None:
    """Convert PDF to Word document using pdf2docx (MIT license).

    Raises ImportError if pdf2docx is not installed.
    Raises RuntimeError on conversion failure.
    """
    try:
        from pdf2docx import Converter
    except ImportError:
        raise ImportError(
            "Thiếu thư viện pdf2docx.\n"
            "Cài bằng lệnh: pip install pdf2docx"
        )

    if progress_cb:
        progress_cb("Đang chuyển đổi PDF sang Word…")

    cv = Converter(pdf_path)
    try:
        cv.convert(output_path, start=0, end=None)
    except Exception as e:
        raise RuntimeError(f"Không thể chuyển đổi sang Word: {e}") from e
    finally:
        cv.close()

    if not os.path.exists(output_path):
        raise RuntimeError("File Word không được tạo ra — chuyển đổi thất bại.")


def convert_pdf_to_xlsx(
    pdf_path: str,
    output_path: str,
    *,
    progress_cb: Callable[[str], None] | None = None,
) -> int:
    """Convert PDF tables to Excel workbook using pdfplumber + openpyxl (MIT).

    Returns number of tables extracted.
    Raises ImportError if dependencies not installed.
    Raises RuntimeError if no tables found or conversion fails.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "Thiếu thư viện pdfplumber.\n"
            "Cài bằng lệnh: pip install pdfplumber openpyxl"
        )
    try:
        import openpyxl
    except ImportError:
        raise ImportError(
            "Thiếu thư viện openpyxl.\n"
            "Cài bằng lệnh: pip install openpyxl"
        )

    if progress_cb:
        progress_cb("Đang trích xuất bảng từ PDF…")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    total_tables = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            if progress_cb:
                progress_cb(f"Đang xử lý trang {page_idx}/{len(pdf.pages)}…")

            tables = page.extract_tables()
            if not tables:
                continue

            for tbl_idx, table in enumerate(tables, start=1):
                total_tables += 1
                sheet_name = f"Trang{page_idx}" if len(tables) == 1 else f"T{page_idx}_Bảng{tbl_idx}"
                sheet_name = sheet_name[:31]  # Excel sheet name limit

                ws = wb.create_sheet(title=sheet_name)
                for row in table:
                    ws.append([cell if cell is not None else "" for cell in row])

                # Auto-width columns
                for col in ws.columns:
                    max_len = max((len(str(c.value or "")) for c in col), default=0)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    if total_tables == 0:
        # Fallback: extract all text page by page as plain rows
        if progress_cb:
            progress_cb("Không tìm thấy bảng — xuất nội dung văn bản…")
        with pdfplumber.open(pdf_path) as pdf:
            ws = wb.create_sheet(title="Nội dung")
            for page_idx, page in enumerate(pdf.pages, start=1):
                ws.append([f"--- Trang {page_idx} ---"])
                text = page.extract_text() or ""
                for line in text.splitlines():
                    ws.append([line])
                ws.append([""])
        total_tables = 1  # count the text export as 1 "table"

    if progress_cb:
        progress_cb("Đang lưu file Excel…")

    wb.save(output_path)
    return total_tables
