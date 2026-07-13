"""TC51 — Chat PDF phải là chatbox thực thụ: hiện ngay câu hỏi của người dùng,
giữ toàn bộ lịch sử qua nhiều lượt gửi (không xóa/dựng lại làm mất tin nhắn).

Khung chat được render từ self._messages (setHtml) nên không còn lỗi cursor
xóa nhầm bong bóng như bản cũ.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from packages.qt_compat.QtWidgets import QApplication
except Exception:  # pragma: no cover
    pytest.skip("Qt không khả dụng", allow_module_level=True)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _M:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class _FakeSession:
    """ask() trả lời đồng bộ, ghi lại history như PDFChatSession thật."""

    def __init__(self):
        self.history = []

    def ask(self, q):
        from packages.ai.chat_pdf import ChatResult
        self.history.append(_M("user", q))
        answer = f"Trả lời cho {q}"
        self.history.append(_M("assistant", answer))
        return ChatResult(answer=answer)

    def reset(self):
        self.history.clear()


def _make(qapp, monkeypatch):
    import packages.ai.provider as prov
    monkeypatch.setattr(prov, "is_ai_available", lambda: True)
    import app.ai_chat_dialog as mod
    # ép chạy đồng bộ để quan sát UI ngay sau _on_send
    monkeypatch.setattr(mod, "start_dialog_task",
                        lambda dlg, fn, on_success=None, on_error=None:
                        (on_success(fn()) if on_success else None) or True)
    dlg = mod.AIChatDialog(None, "tc51.pdf")
    dlg._session = _FakeSession()
    dlg._rebuild_chat()
    return dlg


def test_first_message_shows_user_question(qapp, monkeypatch):
    dlg = _make(qapp, monkeypatch)
    dlg._input.setText("Câu hỏi đầu tiên")
    dlg._on_send()
    qapp.processEvents()
    text = dlg._chat_area.toPlainText()
    assert "Câu hỏi đầu tiên" in text, "Tin nhắn đầu tiên của người dùng không hiển thị"
    assert "Trả lời cho Câu hỏi đầu tiên" in text
    dlg.deleteLater()


def test_resend_keeps_previous_history(qapp, monkeypatch):
    dlg = _make(qapp, monkeypatch)
    dlg._input.setText("Câu 1"); dlg._on_send(); qapp.processEvents()
    dlg._input.setText("Câu 2"); dlg._on_send(); qapp.processEvents()
    text = dlg._chat_area.toPlainText()
    # gửi câu 2 KHÔNG được xóa câu 1 + trả lời 1
    assert "Câu 1" in text and "Trả lời cho Câu 1" in text, "Gửi lại làm mất lịch sử cũ"
    assert "Câu 2" in text and "Trả lời cho Câu 2" in text
    # 2 lượt = 4 bong bóng, đúng thứ tự user/ai xen kẽ
    assert [r for r, _ in dlg._messages] == ["user", "ai", "user", "ai"]
    dlg.deleteLater()
