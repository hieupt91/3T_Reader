"""PDF conversion utilities — PDF → Word (.docx) and PDF → Excel (.xlsx).

Windows-optimised: pdf2docx for layout-preserving Word export;
pdfplumber + openpyxl for table-aware Excel export with text fallback.

Install dependencies:
    pip install pdf2docx pdfplumber openpyxl
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
    """Convert PDF to Word (.docx) using pdf2docx.

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
        progress_cb("Đang mở file PDF…")

    # Count pages for progress reporting
    try:
        import fitz as _fitz
        with _fitz.open(pdf_path) as _d:
            total_pages = _d.page_count
    except Exception:
        total_pages = 0

    if progress_cb and total_pages:
        progress_cb(f"Đang chuyển đổi {total_pages} trang sang Word…")
    elif progress_cb:
        progress_cb("Đang chuyển đổi PDF sang Word…")

    cv = Converter(pdf_path)
    try:
        cv.convert(
            output_path,
            start=0,
            end=None,
            # multi_processing=False prevents Windows process-spawn issues
            multi_processing=False,
        )
    except Exception as e:
        raise RuntimeError(f"Không thể chuyển đổi sang Word: {e}") from e
    finally:
        cv.close()

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("File Word không được tạo ra — chuyển đổi thất bại.")

    if progress_cb:
        progress_cb("Hoàn tất xuất Word!")


def convert_pdf_to_xlsx(
    pdf_path: str,
    output_path: str,
    *,
    progress_cb: Callable[[str], None] | None = None,
) -> int:
    """Convert PDF tables to Excel (.xlsx) using pdfplumber + openpyxl.

    Strategy:
      1. Try to extract structured tables via pdfplumber.
      2. If no tables found, fall back to text extraction (one row per line).

    Returns number of sheets written (>= 1 on success).
    Raises ImportError / RuntimeError on failure.
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
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError(
            "Thiếu thư viện openpyxl.\n"
            "Cài bằng lệnh: pip install openpyxl"
        )

    if progress_cb:
        progress_cb("Đang mở file PDF…")

    # ── header style helpers ──────────────────────────────────────────────
    _HEADER_FONT   = Font(bold=True, color="FFFFFF", size=10)
    _HEADER_FILL   = PatternFill("solid", fgColor="2B4F9E")
    _HEADER_ALIGN  = Alignment(horizontal="center", vertical="center", wrap_text=True)
    _BORDER_SIDE   = Side(style="thin", color="AAAAAA")
    _CELL_BORDER   = Border(
        left=_BORDER_SIDE, right=_BORDER_SIDE,
        top=_BORDER_SIDE, bottom=_BORDER_SIDE,
    )
    _DATA_ALIGN    = Alignment(vertical="top", wrap_text=True)

    def _style_sheet(ws, has_header: bool):
        """Apply alternating row colours and column auto-widths."""
        col_widths: dict[int, int] = {}
        for r_idx, row in enumerate(ws.iter_rows(), start=1):
            for cell in row:
                # Border on all cells
                cell.border = _CELL_BORDER
                if has_header and r_idx == 1:
                    cell.font   = _HEADER_FONT
                    cell.fill   = _HEADER_FILL
                    cell.alignment = _HEADER_ALIGN
                else:
                    cell.alignment = _DATA_ALIGN
                    if r_idx % 2 == 0:
                        cell.fill = PatternFill("solid", fgColor="EEF2FA")
                # Track max content width per column
                val_len = len(str(cell.value or ""))
                col_widths[cell.column] = max(col_widths.get(cell.column, 0), val_len)

        for col_idx, max_len in col_widths.items():
            letter = get_column_letter(col_idx)
            ws.column_dimensions[letter].width = min(max_len + 4, 60)

        # Freeze the header row
        if has_header and ws.max_row > 1:
            ws.freeze_panes = "A2"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove the default empty sheet

    total_tables = 0

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages, start=1):
            if progress_cb:
                progress_cb(f"Đang xử lý trang {page_idx}/{n_pages}…")

            # Use aggressive table settings to catch borderless tables
            tables = page.extract_tables({
                "vertical_strategy":   "lines_strict",
                "horizontal_strategy": "lines_strict",
            })
            if not tables:
                # Fallback: looser detection
                tables = page.extract_tables({
                    "vertical_strategy":   "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance":      5,
                    "join_tolerance":      3,
                })

            if not tables:
                continue

            for tbl_idx, table in enumerate(tables, start=1):
                if not table:
                    continue
                total_tables += 1
                raw_name = f"Trang{page_idx}" if len(tables) == 1 else f"T{page_idx}_B{tbl_idx}"
                sheet_name = raw_name[:31]

                ws = wb.create_sheet(title=sheet_name)
                for row in table:
                    ws.append([str(cell).strip() if cell is not None else "" for cell in row])

                _style_sheet(ws, has_header=ws.max_row > 1)

    if total_tables == 0:
        # ── Text fallback: one sheet per page ────────────────────────────
        if progress_cb:
            progress_cb("Không có bảng — xuất nội dung văn bản từng trang…")

        with pdfplumber.open(pdf_path) as pdf:
            n_pages = len(pdf.pages)
            for page_idx, page in enumerate(pdf.pages, start=1):
                if progress_cb:
                    progress_cb(f"Đang xuất trang {page_idx}/{n_pages}…")

                text = (page.extract_text() or "").strip()
                if not text:
                    continue

                sheet_name = f"Trang {page_idx}"[:31]
                ws = wb.create_sheet(title=sheet_name)
                # Header row
                ws.append([f"Nội dung trang {page_idx}"])
                ws["A1"].font  = _HEADER_FONT
                ws["A1"].fill  = _HEADER_FILL
                ws["A1"].alignment = _HEADER_ALIGN

                for line in text.splitlines():
                    ws.append([line])

                # Auto width
                max_len = max((len(r[0].value or "") for r in ws.iter_rows(min_row=2)), default=20)
                ws.column_dimensions["A"].width = min(max_len + 4, 120)
                ws.freeze_panes = "A2"

        total_tables = wb.sheetnames.__len__()

    if not wb.sheetnames:
        raise RuntimeError("Không có nội dung để xuất ra Excel.")

    if progress_cb:
        progress_cb("Đang lưu file Excel…")

    wb.save(output_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("File Excel không được tạo ra — lưu thất bại.")

    if progress_cb:
        progress_cb("Hoàn tất xuất Excel!")

    return max(total_tables, 1)
