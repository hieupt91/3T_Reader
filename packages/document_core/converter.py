"""PDF conversion utilities - PDF -> Word (.docx) and PDF -> Excel (.xlsx)."""
from __future__ import annotations

import os
from typing import Callable


def convert_pdf_to_docx(
    pdf_path: str,
    output_path: str,
    *,
    progress_cb: Callable[[str], None] | None = None,
) -> None:
    """Convert PDF to Word (.docx) using pdf2docx."""
    try:
        from pdf2docx import Converter
    except ImportError:
        raise ImportError(
            "Thieu thu vien pdf2docx.\n"
            "Cai bang lenh: pip install pdf2docx"
        )

    if progress_cb:
        progress_cb("Dang mo file PDF...")

    try:
        import pypdfium2 as _pdfium
        _d = _pdfium.PdfDocument(pdf_path)
        total_pages = len(_d)
        _d.close()
    except Exception:
        total_pages = 0

    if progress_cb and total_pages:
        progress_cb(f"Dang chuyen doi {total_pages} trang sang Word...")
    elif progress_cb:
        progress_cb("Dang chuyen doi PDF sang Word...")

    cv = Converter(pdf_path)
    try:
        cv.convert(
            output_path,
            start=0,
            end=None,
            multi_processing=False,
        )
    except Exception as e:
        raise RuntimeError(f"Khong the chuyen doi sang Word: {e}") from e
    finally:
        cv.close()

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("File Word khong duoc tao ra - chuyen doi that bai.")

    if progress_cb:
        progress_cb("Hoan tat xuat Word!")


def _build_rows_from_words(words: list[dict]) -> list[list[str]]:
    if not words:
        return []

    rows: list[dict] = []
    for word in sorted(words, key=lambda w: (float(w.get("top", 0.0)), float(w.get("x0", 0.0)))):
        top = float(word.get("top", 0.0))
        bottom = float(word.get("bottom", top + 10.0))
        size = float(word.get("size") or max(1.0, bottom - top))
        mid = (top + bottom) / 2.0

        placed = False
        for row in rows:
            tol = max(3.0, row["avg_size"] * 0.6)
            if abs(mid - row["mid"]) <= tol:
                row["words"].append(word)
                count = len(row["words"])
                row["mid"] = ((row["mid"] * (count - 1)) + mid) / count
                row["avg_size"] = ((row["avg_size"] * (count - 1)) + size) / count
                placed = True
                break

        if not placed:
            rows.append({"mid": mid, "avg_size": size, "words": [word]})

    result: list[list[str]] = []
    for row in rows:
        sorted_words = sorted(row["words"], key=lambda w: float(w.get("x0", 0.0)))
        if not sorted_words:
            continue

        gap_threshold = max(12.0, row["avg_size"] * 1.8)
        cells: list[str] = []
        current: list[dict] = []
        prev = None
        for word in sorted_words:
            if prev is None:
                current.append(word)
            else:
                gap = float(word.get("x0", 0.0)) - float(prev.get("x1", word.get("x0", 0.0)))
                if gap > gap_threshold and current:
                    cells.append(
                        " ".join(str(part.get("text", "")).strip() for part in current if part.get("text")).strip()
                    )
                    current = [word]
                else:
                    current.append(word)
            prev = word

        if current:
            cells.append(
                " ".join(str(part.get("text", "")).strip() for part in current if part.get("text")).strip()
            )

        cleaned = [cell for cell in cells if cell]
        if cleaned:
            result.append(cleaned)

    return result


def convert_pdf_to_xlsx(
    pdf_path: str,
    output_path: str,
    *,
    progress_cb: Callable[[str], None] | None = None,
) -> int:
    """Export PDF pages to worksheets with best-effort layout reconstruction."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "Thieu thu vien pdfplumber.\n"
            "Cai bang lenh: pip install pdfplumber openpyxl"
        )
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError(
            "Thieu thu vien openpyxl.\n"
            "Cai bang lenh: pip install openpyxl"
        )

    if progress_cb:
        progress_cb("Dang mo file PDF...")

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border_side = Side(style="thin", color="AAAAAA")
    cell_border = Border(
        left=border_side, right=border_side,
        top=border_side, bottom=border_side,
    )
    data_align = Alignment(vertical="top", wrap_text=True)

    def style_row(ws, row_idx: int, fill_color: str = "2B4F9E") -> None:
        fill = PatternFill("solid", fgColor=fill_color)
        for cell in ws[row_idx]:
            cell.font = header_font
            cell.fill = fill
            cell.alignment = header_align

    def finalize_sheet(ws) -> None:
        col_widths: dict[int, int] = {}
        for r_idx, row in enumerate(ws.iter_rows(), start=1):
            for cell in row:
                cell.border = cell_border
                if r_idx != 1:
                    cell.alignment = data_align
                    if r_idx % 2 == 0:
                        cell.fill = PatternFill("solid", fgColor="EEF2FA")
                val_len = len(str(cell.value or ""))
                col_widths[cell.column] = max(col_widths.get(cell.column, 0), val_len)

        for col_idx, max_len in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 80)
        if ws.max_row > 1:
            ws.freeze_panes = "A2"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    total_tables = 0

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages, start=1):
            if progress_cb:
                progress_cb(f"Dang xuat trang {page_idx}/{n_pages}...")

            ws = wb.create_sheet(title=f"Trang {page_idx}"[:31])
            ws.append([f"Trang {page_idx}"])

            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                extra_attrs=["size"],
            ) or []

            rows = _build_rows_from_words(words)
            tables = []
            if not rows:
                tables = page.extract_tables({
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                }) or []
                if not tables:
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "snap_tolerance": 5,
                        "join_tolerance": 3,
                    }) or []

            if rows:
                ws.append(["Noi dung va bo cuc trang"])
                for row in rows:
                    ws.append(row)
            elif tables:
                for tbl_idx, table in enumerate(tables, start=1):
                    if not table:
                        continue
                    total_tables += 1
                    ws.append([f"Bang {tbl_idx}"])
                    for row in table:
                        ws.append([str(cell).strip() if cell is not None else "" for cell in row])
                    ws.append([""])
            else:
                text = (page.extract_text() or "").strip()
                if text:
                    ws.append(["Noi dung van ban trang nay"])
                    for line in text.splitlines():
                        ws.append([line])
                else:
                    ws.append(["Khong trich xuat duoc noi dung trang nay."])

            finalize_sheet(ws)
            style_row(ws, 1)
            for row_idx in range(1, ws.max_row + 1):
                first_value = ws.cell(row=row_idx, column=1).value
                if isinstance(first_value, str) and first_value.startswith("Bang "):
                    style_row(ws, row_idx, fill_color="4C6EA9")

    if not wb.sheetnames:
        raise RuntimeError("Khong co noi dung de xuat ra Excel.")

    if progress_cb:
        progress_cb("Dang luu file Excel...")

    wb.save(output_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("File Excel khong duoc tao ra - luu that bai.")

    if progress_cb:
        progress_cb("Hoan tat xuat Excel!")

    return max(total_tables, len(wb.sheetnames))
