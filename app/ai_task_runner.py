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
    if existing is not None and existing.isRunning():
        return False

    worker = FunctionWorker(fn)
    thread = QThread(owner)
    worker.moveToThread(thread)

    worker.finished.connect(on_success)
    worker.error.connect(on_error)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.error.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda: setattr(owner, thread_attr, None))
    thread.finished.connect(lambda: setattr(owner, worker_attr, None))
    thread.started.connect(worker.run)

    setattr(owner, worker_attr, worker)
    setattr(owner, thread_attr, thread)
    thread.start()
    return True


def dialog_task_running(owner, thread_attr: str = "_task_thread") -> bool:
    thread = getattr(owner, thread_attr, None)
    return bool(thread is not None and thread.isRunning())
