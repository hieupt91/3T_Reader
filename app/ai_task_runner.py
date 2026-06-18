from __future__ import annotations

import traceback

from packages.qt_compat.QtCore import QObject, QThread, pyqtSignal


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


def start_dialog_task(owner, fn, *, on_success, on_error, thread_attr: str = "_task_thread", worker_attr: str = "_task_worker") -> bool:
    existing = getattr(owner, thread_attr, None)
    if existing is not None and (getattr(existing, "isRunning", lambda: False)() or getattr(existing, "is_alive", lambda: False)()):
        return False

    import threading
    worker = FunctionWorker(fn)

    def _wrap_success(result):
        setattr(owner, thread_attr, None)
        setattr(owner, worker_attr, None)
        on_success(result)

    def _wrap_error(err, tb):
        setattr(owner, thread_attr, None)
        setattr(owner, worker_attr, None)
        on_error(err, tb)

    worker.finished.connect(_wrap_success)
    worker.error.connect(_wrap_error)

    thread = threading.Thread(target=worker.run, daemon=True)
    setattr(owner, worker_attr, worker)
    setattr(owner, thread_attr, thread)
    thread.start()

    return True


def dialog_task_running(owner, thread_attr: str = "_task_thread") -> bool:
    thread = getattr(owner, thread_attr, None)
    return bool(thread is not None and getattr(thread, "is_alive", lambda: False)())
