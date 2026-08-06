"""PiperVoiceManagerDialog: nút "Đóng" không disable trong lúc dl_thread
(QThread thật) đang tải, khác với btn_download đã disable đúng cùng chỗ -
nghi vấn A3-class (libshiboken "C++ object đã bị xoá") chưa tái hiện được
crash cụ thể để khẳng định chắc chắn, nhưng đây là gap UX/an toàn thật bất
kể lý thuyết trên đúng hay không: cho phép bỏ dở dialog trong khi thread
nền vẫn đang ghi file. Fix theo đúng pattern closeEvent đã dùng ở
app/ai_translate_dialog.py cho lớp vấn đề tương tự (chặn X/Escape, không
chỉ nút bấm)."""

import inspect

from app.actions import piper_tts_manager


def test_close_button_disabled_while_downloading():
    src = inspect.getsource(piper_tts_manager.PiperVoiceManagerDialog._on_download)
    assert "self.btn_close.setEnabled(False)" in src


def test_close_button_re_enabled_when_download_finishes():
    src = inspect.getsource(piper_tts_manager.PiperVoiceManagerDialog._on_download_finished)
    assert "self.btn_close.setEnabled(True)" in src


def test_close_event_blocks_x_button_and_escape_while_thread_running():
    """Disable nút Đóng chỉ chặn được đường click - closeEvent phải tự chặn
    riêng cho đường X button/Escape, không dựa vào trạng thái nút."""
    assert hasattr(piper_tts_manager.PiperVoiceManagerDialog, "closeEvent")
    src = inspect.getsource(piper_tts_manager.PiperVoiceManagerDialog.closeEvent)
    assert "self.dl_thread.isRunning()" in src
    assert "event.ignore()" in src
