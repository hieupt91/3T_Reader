from __future__ import annotations

import traceback

from packages.qt_compat.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


class FunctionWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str, str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
        except Exception as exc:
            self.error.emit(str(exc), traceback.format_exc())
        else:
            self.finished.emit(result)


class _DialogTaskRelay(QObject):
    """Sống ở thread đã gọi start_dialog_task (luôn là main/GUI thread, vì
    hàm này chỉ được gọi từ handler UI như nút Gửi/Tìm/Tóm tắt).

    Bắt buộc dùng bound-method thật của QObject này làm slot: nối signal
    của worker (chạy trên threading.Thread nền) thẳng vào closure thường
    khiến Qt không suy ra được thread affinity của receiver, nên on_success/
    on_error sẽ chạy ngay trên background thread thay vì được marshal về
    main thread — thao tác QWidget (vd rebuild khung chat) từ sai thread là
    undefined behavior, gây lỗi UI ẩn/không ổn định (tin nhắn không hiện,
    v.v.). Cùng lớp lỗi đã sửa ở auto_ocr.py/sidebar.py/sign.py.
    """

    def __init__(self, owner, thread_attr, worker_attr, on_success, on_error):
        super().__init__()
        self._owner = owner
        self._thread_attr = thread_attr
        self._worker_attr = worker_attr
        self._on_success = on_success
        self._on_error = on_error

    def _clear_owner_refs(self) -> None:
        setattr(self._owner, self._thread_attr, None)
        setattr(self._owner, self._worker_attr, None)

    @pyqtSlot(object)
    def handle_success(self, result):
        self._clear_owner_refs()
        self._on_success(result)

    @pyqtSlot(str, str)
    def handle_error(self, err, tb):
        self._clear_owner_refs()
        self._on_error(err, tb)


def start_dialog_task(owner, fn, *, on_success, on_error, thread_attr: str = "_task_thread", worker_attr: str = "_task_worker") -> bool:
    existing = getattr(owner, thread_attr, None)
    if existing is not None and (getattr(existing, "isRunning", lambda: False)() or getattr(existing, "is_alive", lambda: False)()):
        return False

    import threading
    worker = FunctionWorker(fn)
    relay = _DialogTaskRelay(owner, thread_attr, worker_attr, on_success, on_error)
    # Giữ relay sống tới khi worker xong (tránh bị GC giữa chừng khi nền
    # đang chạy) bằng cách gắn vào owner, giống worker_attr/thread_attr.
    setattr(owner, f"{worker_attr}_relay", relay)

    worker.finished.connect(relay.handle_success)
    worker.error.connect(relay.handle_error)

    thread = threading.Thread(target=worker.run, daemon=True)
    setattr(owner, worker_attr, worker)
    setattr(owner, thread_attr, thread)
    thread.start()

    return True


def dialog_task_running(owner, thread_attr: str = "_task_thread") -> bool:
    thread = getattr(owner, thread_attr, None)
    return bool(thread is not None and getattr(thread, "is_alive", lambda: False)())
