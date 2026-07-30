"""Auto-OCR khi mở file: chạy nền ngay khi mở tài liệu, để bôi đen/gạch dưới/
gạch ngang và "sửa text gốc" hoạt động được cả trên file scan (ảnh thuần).

Cách hoạt động:
  - Với mỗi trang chưa có text layer (`packages.ocr.engine.page_has_text`),
    OCR trang đó và ghi kết quả thành text vô hình, định vị đúng theo từng từ
    (`packages.ocr.engine.ocr_pdf_page_text_layer` + `merge_text_layer_into_pdf`).
  - Trang đang xem được OCR trước tiên để người dùng thấy có thể bôi đen/tìm
    kiếm sớm nhất, các trang còn lại xử lý dần ở nền.
  - Việc kiểm tra "trang đã có text chưa" trước khi OCR chính là cơ chế
    idempotent: mở lại file đã xử lý sẽ bỏ qua toàn bộ, không tốn công lần 2.
  - Ghi PDF được đưa vào hàng đợi autosave chú thích sẵn có
    (`_queue_annotation_op`) để không xung đột với các thao tác ghi PDF khác
    (highlight, ghi chú...) đang chạy song song.

Tính năng này mở cho MỌI gói license (không giống OCR thủ công toàn tài liệu
trong `app/actions/ocr.py`, vẫn khóa Enterprise) — vì đây là nền tảng để các
tính năng cơ bản (bôi đen, sửa text) hoạt động trên file scan, không phải một
tính năng OCR độc lập.
"""
from __future__ import annotations

import os

from packages.qt_compat.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from app.actions.annotate import _queue_annotation_op, _schedule_annotation_undo_flush


class _AutoOcrWorker(QObject):
    pageDone = pyqtSignal(str, int, bytes)
    finished = pyqtSignal(str, int, list)  # (pdf_path, done_count, failed_pages)

    def __init__(self, pdf_path: str, page_order: list[int]):
        super().__init__()
        self._pdf_path = pdf_path
        self._page_order = page_order
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @pyqtSlot()
    def run(self) -> None:
        from packages.ocr.engine import ocr_pdf_page_text_layer, page_has_text
        from packages.audit import log_action, ACT_OCR

        done_count = 0
        failed_pages: list[int] = []
        for page_num in self._page_order:
            if self._cancelled:
                break
            try:
                if page_has_text(self._pdf_path, page_num):
                    continue
                pdf_bytes = ocr_pdf_page_text_layer(self._pdf_path, page_num)
                if pdf_bytes:
                    done_count += 1
                    self.pageDone.emit(self._pdf_path, page_num, pdf_bytes)
            except Exception as exc:
                # Trước đây lỗi từng trang bị nuốt im lặng (except: continue) -
                # người dùng không có cách nào biết 1 phần tài liệu chưa được
                # OCR. Ghi vào audit log (xem qua "Nhật ký hoạt động") và báo
                # số trang lỗi cho _on_auto_ocr_finished hiển thị.
                failed_pages.append(page_num)
                log_action(ACT_OCR, self._pdf_path, f"auto-ocr trang {page_num} loi: {exc}")
                continue
        self.finished.emit(self._pdf_path, done_count, failed_pages)


class _AutoOcrRelay(QObject):
    """Sống trong main thread (tạo bằng `QObject(window)` từ main thread).

    Bắt buộc phải là bound-method thật của một QObject — nối signal của
    worker (chạy trên QThread khác) thẳng vào lambda thường sẽ khiến Qt
    không suy ra được thread affinity của receiver, nên lambda sẽ chạy ngay
    trên worker thread thay vì được marshal về main thread. Hậu quả: các
    thao tác QTimer/QWidget bên trong (`_queue_annotation_op`,
    `window.status`) âm thầm không có tác dụng — không exception, không
    log, chỉ đơn giản là không có gì xảy ra dù đợi bao lâu. Route qua một
    QObject thật (như class này) để Qt tự động dùng QueuedConnection đúng.
    """

    def __init__(self, window, abs_path: str):
        super().__init__(window)
        self._window = window
        self._abs_path = abs_path

    @pyqtSlot(str, int, bytes)
    def onPageDone(self, path: str, page_num: int, data: bytes) -> None:
        _on_auto_ocr_page_done(self._window, path, page_num, data)

    @pyqtSlot(str, int, list)
    def onFinished(self, path: str, count: int, failed_pages: list) -> None:
        _auto_ocr_registry(self._window).pop(self._abs_path, None)
        _on_auto_ocr_finished(self._window, path, count, failed_pages)


def _auto_ocr_registry(window) -> dict:
    registry = getattr(window, "_auto_ocr_running", None)
    if not isinstance(registry, dict):
        registry = {}
        window._auto_ocr_running = registry
    return registry


def start_auto_ocr_for_document(window, pdf_path: str | None, current_page: int = 1) -> None:
    """Bắt đầu OCR nền cho `pdf_path` nếu còn trang thiếu text layer.

    An toàn khi gọi mỗi lần mở file — trang đã có text (born-digital hoặc đã
    OCR trước đó) tự động được bỏ qua nên mở lại không tốn công.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return
    try:
        from packages.ocr.engine import is_available
        if not is_available():
            return
    except Exception:
        return

    abs_path = os.path.abspath(pdf_path)
    registry = _auto_ocr_registry(window)
    existing = registry.get(abs_path)
    if existing is not None and existing[0].isRunning():
        return

    try:
        import pypdfium2 as pdfium
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                total_pages = len(doc)
            finally:
                doc.close()
    except Exception:
        return
    if total_pages <= 0:
        return

    current_page = max(1, min(total_pages, int(current_page or 1)))
    page_order = [current_page] + [p for p in range(1, total_pages + 1) if p != current_page]

    thread = QThread(window)
    worker = _AutoOcrWorker(pdf_path, page_order)
    relay = _AutoOcrRelay(window, abs_path)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.pageDone.connect(relay.onPageDone)
    worker.finished.connect(relay.onFinished)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    registry[abs_path] = (thread, worker, relay)
    thread.start()


def _sidebar_is_loading(window, pdf_path: str) -> bool:
    sidebar = getattr(window, "sidebar", None)
    is_loading = getattr(sidebar, "is_loading", None)
    try:
        return bool(callable(is_loading) and is_loading(pdf_path))
    except Exception:
        return False


def _on_auto_ocr_page_done(
    window, pdf_path: str, page_num: int, text_layer_pdf_bytes: bytes, *, _retries_left: int = 30
) -> None:
    # ThumbnailLoader (app/sidebar.py) mở 1 pypdfium2 document handle và giữ
    # nguyên suốt vòng lặp render nhiều trang. Nếu file bị os.replace() (khi
    # hàng đợi chú thích flush) ngay lúc đó, lần truy cập trang tiếp theo của
    # handle cũ có thể access-violation cấp native — sập cả tiến trình Python,
    # không bắt được bằng try/except. Đợi sidebar rảnh rồi mới enqueue ghi đĩa.
    if _sidebar_is_loading(window, pdf_path) and _retries_left > 0:
        QTimer.singleShot(
            200,
            lambda: _on_auto_ocr_page_done(
                window, pdf_path, page_num, text_layer_pdf_bytes, _retries_left=_retries_left - 1
            ),
        )
        return

    from packages.ocr.engine import merge_text_layer_into_pdf

    def _op(pdf, page_idx=page_num - 1, data=text_layer_pdf_bytes):
        if 0 <= page_idx < len(pdf.pages):
            merge_text_layer_into_pdf(pdf, page_idx, data)

    _queue_annotation_op(window, pdf_path, _op, delay_ms=400)
    # Gom nhiều trang hoàn tất liên tiếp thành một lần lưu + soft reload duy
    # nhất (tái dùng cơ chế debounce sẵn có của undo chú thích).
    _schedule_annotation_undo_flush(window, pdf_path, delay_ms=600)


def _on_auto_ocr_finished(window, pdf_path: str, ocr_page_count: int, failed_pages: list | None = None) -> None:
    failed_pages = failed_pages or []
    if not (ocr_page_count > 0 or failed_pages) or not hasattr(window, "status"):
        return
    current_path = getattr(window, "current_path", None)
    if not (current_path and os.path.abspath(current_path) == os.path.abspath(pdf_path)):
        return

    parts = []
    if ocr_page_count > 0:
        parts.append(
            f"Đã nhận diện văn bản cho {ocr_page_count} trang scan — "
            f"có thể tìm kiếm/bôi đen/sửa text trên các trang này."
        )
    if failed_pages:
        parts.append(f"Không nhận diện được {len(failed_pages)} trang (xem Nhật ký hoạt động).")
    window.status.showMessage(" ".join(parts), 6000)


def stop_auto_ocr_for_document(window, pdf_path: str | None) -> None:
    """Hủy OCR nền đang chạy cho `pdf_path`, nếu có (ví dụ khi đóng tab/tài liệu)."""
    if not pdf_path:
        return
    registry = _auto_ocr_registry(window)
    entry = registry.get(os.path.abspath(pdf_path))
    if entry is not None:
        entry[1].cancel()
