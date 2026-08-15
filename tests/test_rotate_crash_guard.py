"""B13-adjacent (QA 2026-08-13): rotating a page crashed the whole app
(Fatal Python error: Aborted) when the final file-replace failed (a
PermissionError - e.g. antivirus/indexer briefly locking a freshly-written
multi-hundred-MB temp file) surfaced from inside the QThread-finished Qt
slot `_RotatePageRelay.onFinished`. An exception escaping a pyqtSlot
callback aborts the whole PySide6 process instead of just failing that one
rotate. Reproduced live on the 711MB test file; fixed by wrapping the
disk-I/O call in try/except and reporting via show_warning like the
worker-side error branch already did.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from packages.qt_compat.QtWidgets import QApplication, QWidget
except Exception:  # pragma: no cover - môi trường không có Qt
    pytest.skip("Qt không khả dụng", allow_module_level=True)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeStatus:
    def __init__(self):
        self.messages = []

    def showMessage(self, text, *_args, **_kwargs):
        self.messages.append(text)


def test_rotate_relay_reports_error_instead_of_crashing_on_replace_failure(qapp, monkeypatch, tmp_path):
    from app.actions import annotate

    window = QWidget()
    window.status = _FakeStatus()
    window._rotating_pages = {annotate._normalise_rotate_path("doc.pdf")}
    window._rotate_page_jobs = {}

    monkeypatch.setattr(annotate, "_is_temp_converted_document", lambda *_a, **_k: False)

    warnings = []
    monkeypatch.setattr(
        annotate,
        "show_warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    def _boom(*_args, **_kwargs):
        raise PermissionError("[WinError 5] Access is denied: staged file locked")

    monkeypatch.setattr(annotate, "replace_document_with_staged", _boom)

    tmp_file = tmp_path / "staged.pdf"
    tmp_file.write_bytes(b"%PDF-1.4\n%%EOF")

    relay = annotate._RotatePageRelay(
        window, path="doc.pdf", page_no=1, degrees=90, write_slot=""
    )

    # Must not raise - this is exactly what crashed the app before the fix.
    relay.onFinished(str(tmp_file), None)

    assert len(warnings) == 1
    assert warnings[0][0] == "Lỗi xoay trang"
    assert "khóa tạm thời" in warnings[0][1]
    assert not tmp_file.exists()  # cleaned up on failure, not left behind
    assert window.status.messages == []  # success message must NOT fire on failure
