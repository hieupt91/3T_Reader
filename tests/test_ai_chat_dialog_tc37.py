"""TC37 — Bật/tắt 'Luôn nổi' ở Chat PDF không được làm mất lịch sử chat hay
treo nút đóng.

Trước đây test này chỉ so chuỗi trong source (grep `chat_html = ...`) nên PASS
mà KHÔNG kiểm hành vi thật — đúng cạm bẫy case study #4 trong QUY_TRINH_SUA_LOI
(test hàm/chuỗi lẻ rồi vội kết luận). Nay dựng QDialog thật, đi qua đúng signal
checkbox và closeEvent, tái hiện chính xác kịch bản báo lỗi (Video 7):
    vào chat → bật luôn nổi → tắt luôn nổi → tắt chat → mở lại.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from packages.qt_compat.QtWidgets import QApplication
    from packages.qt_compat.QtCore import Qt
except Exception:  # pragma: no cover - môi trường không có Qt
    pytest.skip("Qt không khả dụng", allow_module_level=True)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeSession:
    """Thay PDFChatSession thật — không đụng file/AI, chỉ giữ lịch sử."""

    def __init__(self):
        from packages.ai.chat_pdf import ChatMessage
        self.history = [
            ChatMessage("user", "Câu hỏi trong phiên"),
            ChatMessage("assistant", "Trả lời của AI"),
        ]

    def reset(self):
        self.history.clear()


def _make_dialog(qapp):
    from app.ai_chat_dialog import AIChatDialog
    dlg = AIChatDialog(None, "C:/fake/tc37.pdf")
    dlg._session = _FakeSession()
    dlg._rebuild_chat()
    dlg.show()
    qapp.processEvents()
    return dlg


def _has_history(dlg) -> bool:
    text = dlg._chat_area.toPlainText()
    return "Câu hỏi trong phiên" in text and "Trả lời của AI" in text


def test_toggle_stays_on_top_preserves_history_and_close_works(qapp):
    dlg = _make_dialog(qapp)
    assert _has_history(dlg)

    # Bật luôn nổi qua chính signal checkbox (không gọi thẳng hàm nội bộ).
    dlg._chk_stays_on_top.setChecked(True)
    qapp.processEvents()
    assert _has_history(dlg), "Bật luôn nổi làm mất lịch sử chat"
    assert bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    # Tắt luôn nổi.
    dlg._chk_stays_on_top.setChecked(False)
    qapp.processEvents()
    assert _has_history(dlg), "Tắt luôn nổi làm mất lịch sử chat"
    assert not bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    # Tắt luôn nổi KHÔNG được làm rớt nút đóng (bug ~ trên enum flag PySide6).
    assert bool(dlg.windowFlags() & Qt.WindowType.WindowCloseButtonHint), \
        "Tắt luôn nổi làm mất nút đóng"

    # Tắt chat: close() phải đi qua closeEvent, ẩn được (không đơ), không xóa chat.
    assert dlg.close() is True
    qapp.processEvents()
    assert not dlg.isVisible()

    dlg.deleteLater()


def test_spam_toggle_stays_on_top_still_closes(qapp):
    # Triệu chứng gốc (Video 7): spam nút 'luôn nổi' rồi không tắt được cửa sổ.
    dlg = _make_dialog(qapp)
    for i in range(30):
        dlg._chk_stays_on_top.setChecked(i % 2 == 0)
        qapp.processEvents()
    assert dlg.isVisible(), "Spam toggle làm cửa sổ biến mất"
    assert _has_history(dlg), "Spam toggle làm mất lịch sử chat"
    assert bool(dlg.windowFlags() & Qt.WindowType.WindowCloseButtonHint), \
        "Spam toggle làm mất/disable nút đóng"
    assert dlg.close() is True, "Spam toggle làm kẹt nút đóng"
    qapp.processEvents()
    assert not dlg.isVisible()

    dlg.deleteLater()


def test_reopen_same_pdf_does_not_wipe_history(qapp):
    # open_chat_dialog khi dialog đã tồn tại sẽ gọi set_pdf(cùng path) rồi show().
    dlg = _make_dialog(qapp)
    dlg._chk_stays_on_top.setChecked(True)
    dlg._chk_stays_on_top.setChecked(False)
    dlg.close()
    qapp.processEvents()

    dlg.set_pdf("C:/fake/tc37.pdf")  # cùng identity -> phải return sớm, không clear
    dlg.show()
    qapp.processEvents()
    assert _has_history(dlg), "Mở lại cùng file bị xóa lịch sử"
    assert dlg.isVisible()

    dlg.deleteLater()
