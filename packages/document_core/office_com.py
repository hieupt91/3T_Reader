"""B52: dùng Microsoft Office/WPS Office đã cài sẵn (nếu có) để convert file
Office gốc (.doc/.docx/.xls/.xlsx/.ppt/.pptx) sang PDF, thay vì bắt buộc
người dùng tải LibreOffice (~150MB). Chỉ gọi COM Automation - API công khai
do Microsoft/Kingsoft công bố cho lập trình viên bên thứ 3, không đụng mã
nguồn của Office/WPS (xem docs/ROADMAP_B52_B2_B13_2026-08-14.md mục B52 để
biết đầy đủ bối cảnh + rủi ro kỹ thuật đã lường trước).

CHỈ chạy trên Windows (COM Automation không tồn tại trên macOS/Linux) - mọi
hàm ở đây phải luôn được gọi có fallback, không bao giờ là đường bắt buộc.
"""

from __future__ import annotations

import os
import sys

_MS_PROG_IDS = {
    "word": "Word.Application",
    "excel": "Excel.Application",
    "ppt": "PowerPoint.Application",
}
# ProgID của WPS Office - tương thích COM với API Office nhưng đăng ký ProgID
# riêng (không dùng chung "Excel.Application" với Microsoft, tránh xung đột
# khi máy cài cả 2). CHƯA XÁC NHẬN THẬT trên máy có cài WPS (xem mục "Việc
# cần làm" trong ROADMAP_B52...) - để rỗng string thay vì đoán sai ProgID
# khiến Dispatch() ném lỗi khó hiểu; điền đúng tên khi có máy test thật.
_WPS_PROG_IDS = {
    "word": "Kwps.Application",
    "excel": "Ket.Application",
    "ppt": "Kwpp.Application",
}

_SAVE_AS_PDF_FORMAT = {"word": 17, "excel": 0, "ppt": 32}  # wdFormatPDF, xlTypePDF, ppSaveAsPDF


def _com_progid_exists(prog_id: str) -> bool:
    """True nếu ProgID đã đăng ký COM trên máy (không cần khởi động app)."""
    if sys.platform != "win32" or not prog_id:
        return False
    try:
        import winreg

        winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, f"{prog_id}\\CLSID")
        return True
    except (FileNotFoundError, OSError):
        return False
    except Exception:
        return False


def detect_office_suite() -> str | None:
    """Trả 'msoffice' | 'wps' | None theo thứ tự ưu tiên (MS Office trước -
    phổ biến hơn, ProgID đã xác nhận chắc chắn đúng)."""
    if _com_progid_exists(_MS_PROG_IDS["word"]) and _com_progid_exists(_MS_PROG_IDS["excel"]):
        return "msoffice"
    if _com_progid_exists(_WPS_PROG_IDS["excel"]) or _com_progid_exists(_WPS_PROG_IDS["word"]):
        return "wps"
    return None


def _kind_for_extension(ext: str) -> str | None:
    ext = ext.lower().lstrip(".")
    if ext in {"doc", "docx", "rtf", "odt"}:
        return "word"
    if ext in {"xls", "xlsx", "ods", "csv"}:
        return "excel"
    if ext in {"ppt", "pptx", "odp"}:
        return "ppt"
    return None


def convert_via_office_com(input_path: str, output_pdf: str, *, suite: str | None = None) -> bool:
    """Convert `input_path` (Office gốc) sang `output_pdf` bằng COM
    Automation của MS Office hoặc WPS đã cài. Trả True nếu thành công (file
    PDF hợp lệ đã được ghi ra `output_pdf`), False nếu bất kỳ bước nào lỗi -
    caller PHẢI có fallback (LibreOffice), không được coi False là lỗi
    nghiêm trọng.

    `suite`: 'msoffice' | 'wps' | None (tự dò qua detect_office_suite())."""
    if sys.platform != "win32":
        return False

    kind = _kind_for_extension(os.path.splitext(input_path)[1])
    if kind is None:
        return False

    suite = suite or detect_office_suite()
    if suite is None:
        return False

    prog_ids = _MS_PROG_IDS if suite == "msoffice" else _WPS_PROG_IDS
    prog_id = prog_ids.get(kind)
    if not prog_id or not _com_progid_exists(prog_id):
        return False

    # Retry có backoff tăng dần (tối đa 5 lần, tới 3s/lần chờ): xác nhận
    # thật (14/08/2026) - chạy nhiều convert khác loại (Word rồi Excel) liên
    # tiếp trên CÙNG thread, đặc biệt khi máy đang bận (chạy sau hàng trăm
    # test khác), có thể khiến 1 lần ném lỗi "Property
    # 'Excel.Application.Visible' can not be set" dù code đúng và dùng
    # DispatchEx (không phải bám instance cũ) - nghi do apartment COM của
    # thread hoặc tiến trình Office trước đó chưa kịp dọn xong giữa
    # CoUninitialize()/Quit() lần trước và CoInitialize() lần sau, dễ xảy ra
    # hơn khi hệ thống đang tải nặng. Đây là đặc tính vốn có của COM
    # Automation trên Windows dưới tải cao (không có cách nào loại bỏ hoàn
    # toàn 100%), backoff tăng dần cho tự phục hồi phần lớn trường hợp thay
    # vì fail ngay - vẫn có fallback LibreOffice ở caller nếu retry hết mà
    # vẫn lỗi."""
    last_exc: Exception | None = None
    for attempt in range(5):
        if attempt > 0:
            import time

            time.sleep(min(3.0, 0.5 * (2 ** attempt)))
        try:
            if _convert_via_office_com_once(prog_id, kind, input_path, output_pdf):
                return True
        except Exception as exc:
            last_exc = exc
    return False


def _convert_via_office_com_once(prog_id: str, kind: str, input_path: str, output_pdf: str) -> bool:
    import pythoncom
    import win32com.client

    # BẮT BUỘC trên thread nền (không phải main thread Qt) - thiếu dòng này
    # là đúng lớp lỗi COM apartment mismatch đã gặp ở TTS (xem
    # app/actions/tts_dialog.py, comment đầu file _run_offline_tts).
    pythoncom.CoInitialize()
    app = None
    doc = None
    try:
        # DispatchEx (không phải Dispatch thường) - Dispatch() có thể bám
        # vào 1 instance CÓ SẴN đã đăng ký trong Running Object Table (vd
        # user đang mở sẵn Excel thật, hoặc 1 tiến trình automation trước đó
        # để lại chưa thoát hết) - nếu instance đó đang ở trạng thái lỗi/bị
        # khoá, mọi lệnh gọi sau (kể cả set .Visible) ném lỗi khó hiểu dù
        # code hoàn toàn đúng (xác nhận thật 14/08/2026: "Property
        # 'Excel.Application.Visible' can not be set" từ 1 instance kẹt).
        # DispatchEx luôn tạo tiến trình MỚI độc lập, né phần lớn lớp lỗi
        # này (phần còn lại xử lý bằng retry ở convert_via_office_com()).
        app = win32com.client.DispatchEx(prog_id)
        app.Visible = False
        if kind != "ppt":
            # Chặn popup "Save changes?"/"Repair document?" có thể treo COM
            # call vô thời hạn nếu file có cảnh báo (macro, định dạng lạ...).
            app.DisplayAlerts = False

        abs_in = os.path.abspath(input_path)
        abs_out = os.path.abspath(output_pdf)
        fmt = _SAVE_AS_PDF_FORMAT[kind]

        if kind == "word":
            doc = app.Documents.Open(abs_in, ReadOnly=True)
            doc.SaveAs(abs_out, FileFormat=fmt)
        elif kind == "excel":
            doc = app.Workbooks.Open(abs_in, ReadOnly=True)
            doc.ExportAsFixedFormat(fmt, abs_out)
        else:
            doc = app.Presentations.Open(abs_in, WithWindow=False, ReadOnly=True)
            doc.SaveAs(abs_out, fmt)

        return os.path.exists(abs_out) and os.path.getsize(abs_out) > 4
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
