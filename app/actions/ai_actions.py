"""AI actions — mở các dialog AI từ cửa sổ chính."""
from __future__ import annotations

import os

from app.actions._guard import require_document


@require_document(show_message=True)
def open_translate_dialog(window):
    """Mở dialog dịch thuật trang PDF hiện tại."""
    pdf_path = _current_pdf_path(window)
    current_page = _current_page(window)

    from app.ai_translate_dialog import AITranslateDialog
    dlg = AITranslateDialog(window, pdf_path, current_page)
    dlg.exec()


@require_document(show_message=True)
def open_summarize_dialog(window):
    """Mở dialog tóm tắt tài liệu."""
    pdf_path = _current_pdf_path(window)

    from app.ai_summarize_dialog import AISummarizeDialog
    dlg = AISummarizeDialog(window, pdf_path)
    dlg.exec()


@require_document(show_message=True)
def open_chat_dialog(window):
    """Mở dialog chat với PDF (non-modal, có thể giữ mở khi đọc)."""
    pdf_path = _current_pdf_path(window)

    existing = getattr(window, "_ai_chat_dialog", None)
    if existing is not None and existing.isVisible():
        existing.set_pdf(pdf_path)
        existing.raise_()
        existing.activateWindow()
        return

    from app.ai_chat_dialog import AIChatDialog
    dlg = AIChatDialog(window, pdf_path)
    window._ai_chat_dialog = dlg
    dlg.show()


@require_document(show_message=True)
def open_search_dialog(window):
    """Mở dialog tìm kiếm theo nghĩa (non-modal, có thể giữ mở khi đọc)."""
    pdf_path = _current_pdf_path(window)

    existing = getattr(window, "_ai_search_dialog", None)
    if existing is not None and existing.isVisible():
        if existing._pdf_path != pdf_path:
            existing.set_pdf(pdf_path)
        existing.raise_()
        existing.activateWindow()
        return

    from app.ai_search_dialog import AISearchDialog
    dlg = AISearchDialog(window, pdf_path)
    window._ai_search_dialog = dlg
    dlg.show()


def open_ai_settings(window):
    """Dialog cấu hình API key AI và Ollama — không yêu cầu tài liệu đang mở."""
    from packages.qt_compat.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QFrame,
    )
    from packages.qt_compat.QtCore import Qt, QTimer
    from packages.ai.provider import is_ai_available, get_active_provider, is_ollama_available

    _STYLE = """
    QDialog {
        background: #F8FAFC;
    }
    QLabel#title {
        color: #0F172A;
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0.2px;
    }
    QLabel#lbl {
        color: #111827;
        font-size: 13px;
        font-weight: 600;
    }
    QLabel#hint {
        color: #475569;
        font-size: 11px;
    }
    QLabel#status {
        color: #0F172A;
        font-size: 12px;
        font-weight: 600;
    }
    QLineEdit {
        background: #FFFFFF;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 9px 12px;
        font-size: 13px;
        font-family: monospace;
    }
    QLineEdit::placeholder {
        color: #94A3B8;
    }
    QLineEdit:focus {
        border-color: #2563EB;
    }
    QPushButton {
        background: #E2E8F0;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 8px 18px;
        font-size: 12px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #CBD5E1;
        border-color: #94A3B8;
    }
    QPushButton#btn_save {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #1D4ED8);
        color: white; border: none;
    }
    QPushButton#btn_save:hover { background: #3B82F6; }
    QPushButton#btn_test { min-width: 80px; }
    QFrame#divider { background: #CBD5E1; }
    """

    dlg = QDialog(window)
    dlg.setWindowTitle("Cài đặt AI")
    dlg.setModal(True)
    dlg.setMinimumWidth(680)
    dlg.resize(720, 520)
    dlg.setStyleSheet(_STYLE)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(24, 20, 24, 20)
    root.setSpacing(10)

    title = QLabel("Cài đặt AI")
    title.setObjectName("title")
    root.addWidget(title)

    # Current status
    lbl_status = QLabel()
    lbl_status.setObjectName("status")
    if is_ai_available():
        provider = get_active_provider()
        lbl_status.setText(f"Trạng thái: Đang dùng {provider}")
        lbl_status.setStyleSheet("color:#166534;font-size:12px;")
    else:
        lbl_status.setText("Trạng thái: Chưa cấu hình AI.")
        lbl_status.setStyleSheet("color:#b45309;font-size:12px;")
    root.addWidget(lbl_status)

    div1 = QFrame(); div1.setObjectName("divider"); div1.setFixedHeight(1)
    root.addWidget(div1)

    # Anthropic API key
    lbl_anthropic = QLabel("Anthropic API Key (Claude — ưu tiên 1):")
    lbl_anthropic.setObjectName("lbl")
    root.addWidget(lbl_anthropic)

    edit_anthropic = QLineEdit()
    edit_anthropic.setPlaceholderText("sk-ant-…")
    edit_anthropic.setEchoMode(QLineEdit.EchoMode.Password)
    edit_anthropic.setText(os.environ.get("ANTHROPIC_API_KEY", ""))
    root.addWidget(edit_anthropic)

    hint_anthropic = QLabel("Lấy key tại: console.anthropic.com")
    hint_anthropic.setObjectName("hint")
    root.addWidget(hint_anthropic)

    # OpenAI API key
    lbl_openai = QLabel("OpenAI API Key (GPT-4o — ưu tiên 2):")
    lbl_openai.setObjectName("lbl")
    root.addWidget(lbl_openai)

    edit_openai = QLineEdit()
    edit_openai.setPlaceholderText("sk-…")
    edit_openai.setEchoMode(QLineEdit.EchoMode.Password)
    edit_openai.setText(os.environ.get("OPENAI_API_KEY", ""))
    root.addWidget(edit_openai)

    hint_openai = QLabel("Lấy key tại: platform.openai.com")
    hint_openai.setObjectName("hint")
    root.addWidget(hint_openai)

    div2 = QFrame(); div2.setObjectName("divider"); div2.setFixedHeight(1)
    root.addWidget(div2)

    # Ollama (offline local LLM)
    lbl_ollama = QLabel("Ollama — AI offline/nội bộ (ưu tiên 3, không cần internet):")
    lbl_ollama.setObjectName("lbl")
    root.addWidget(lbl_ollama)

    row_ollama = QHBoxLayout(); row_ollama.setSpacing(8)
    edit_ollama_url = QLineEdit()
    edit_ollama_url.setPlaceholderText("http://localhost:11434")
    edit_ollama_url.setText(os.environ.get("OLLAMA_BASE_URL", ""))
    row_ollama.addWidget(edit_ollama_url, 1)

    btn_test_ollama = QPushButton("Kiểm tra")
    btn_test_ollama.setObjectName("btn_test")

    ollama_ok = is_ollama_available()
    _ollama_status_color = "#166534" if ollama_ok else "#64748B"
    _ollama_status_text  = "Đang chạy" if ollama_ok else "Không kết nối"
    lbl_ollama_status = QLabel(_ollama_status_text)
    lbl_ollama_status.setStyleSheet(f"color:{_ollama_status_color};font-size:11px;min-width:90px;")

    def _test_ollama():
        from packages.ai.provider import is_ollama_available as _check
        url = edit_ollama_url.text().strip()
        if url:
            os.environ["OLLAMA_BASE_URL"] = url
        ok = _check()
        if ok:
            lbl_ollama_status.setText("Đang chạy")
            lbl_ollama_status.setStyleSheet("color:#166534;font-size:11px;")
        else:
            lbl_ollama_status.setText("Không kết nối")
            lbl_ollama_status.setStyleSheet("color:#B91C1C;font-size:11px;")

    btn_test_ollama.clicked.connect(_test_ollama)
    row_ollama.addWidget(btn_test_ollama)
    row_ollama.addWidget(lbl_ollama_status)
    root.addLayout(row_ollama)

    lbl_ollama_model = QLabel("Model Ollama:")
    lbl_ollama_model.setObjectName("lbl")
    root.addWidget(lbl_ollama_model)

    edit_ollama_model = QLineEdit()
    edit_ollama_model.setPlaceholderText("llama3")
    edit_ollama_model.setText(os.environ.get("OLLAMA_MODEL", ""))
    root.addWidget(edit_ollama_model)

    hint_ollama = QLabel("Cài Ollama tại ollama.com  •  Gõ: ollama pull llama3  •  Tự động phát hiện khi khởi động app")
    hint_ollama.setObjectName("hint")
    root.addWidget(hint_ollama)

    div3 = QFrame(); div3.setObjectName("divider"); div3.setFixedHeight(1)
    root.addWidget(div3)

    btn_row = QHBoxLayout(); btn_row.setSpacing(10)

    btn_cancel = QPushButton("Hủy")
    btn_cancel.clicked.connect(dlg.reject)

    btn_save = QPushButton("Lưu")
    btn_save.setObjectName("btn_save")

    def _save():
        anthropic_key = edit_anthropic.text().strip()
        openai_key    = edit_openai.text().strip()
        ollama_url    = edit_ollama_url.text().strip()
        ollama_model  = edit_ollama_model.text().strip()

        if anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        elif "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        if ollama_url:
            os.environ["OLLAMA_BASE_URL"] = ollama_url
        if ollama_model:
            os.environ["OLLAMA_MODEL"] = ollama_model

        _persist_api_keys(anthropic_key, openai_key, ollama_url, ollama_model)

        from packages.ai.provider import is_ai_available, get_active_provider
        if is_ai_available():
            lbl_status.setText(f"Đã lưu. Đang dùng: {get_active_provider()}")
            lbl_status.setStyleSheet("color:#166534;font-size:12px;")
        else:
            lbl_status.setText("Đã xóa cấu hình AI.")
            lbl_status.setStyleSheet("color:#b45309;font-size:12px;")

        orig = btn_save.text()
        btn_save.setText("Đã lưu!")
        QTimer.singleShot(1500, lambda: btn_save.setText(orig))

    btn_save.clicked.connect(_save)

    btn_row.addWidget(btn_cancel)
    btn_row.addStretch()
    btn_row.addWidget(btn_save)
    root.addLayout(btn_row)

    dlg.exec()


def _current_pdf_path(window) -> str:
    state = window._state_or_global() if hasattr(window, "_state_or_global") else {}
    path = state.get("source_path") or state.get("display_path")
    return path or getattr(window, "current_path", "") or ""


def _current_page(window) -> int:
    viewer = getattr(window, "viewer", None)
    if viewer:
        return getattr(viewer, "_current_page", 1) or 1
    return 1


def _persist_api_keys(anthropic_key: str, openai_key: str,
                      ollama_url: str = "", ollama_model: str = ""):
    """Lưu API key và Ollama config vào file config trong thư mục dữ liệu ứng dụng."""
    import json
    try:
        from packages.platform import get_app_data_dir
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")

        data: dict = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        if anthropic_key:
            data["ANTHROPIC_API_KEY"] = anthropic_key
        else:
            data.pop("ANTHROPIC_API_KEY", None)

        if openai_key:
            data["OPENAI_API_KEY"] = openai_key
        else:
            data.pop("OPENAI_API_KEY", None)

        if ollama_url:
            data["OLLAMA_BASE_URL"] = ollama_url
        if ollama_model:
            data["OLLAMA_MODEL"] = ollama_model

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def load_ai_config():
    """Tải API key và Ollama config từ file config (gọi lúc khởi động app)."""
    import json
    try:
        from packages.platform import get_app_data_dir
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")
        if not os.path.exists(config_path):
            return
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
            val = data.get(key, "")
            if val and not os.environ.get(key):
                os.environ[key] = val
    except Exception:
        pass


def notify_pdf_changed(new_path: str | None):
    """Gọi khi người dùng đổi tab PDF — cập nhật session chat nếu đang mở."""
    # Tìm chat dialog từ tất cả các cửa sổ Qt
    try:
        from packages.qt_compat.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            dlg = getattr(widget, "_ai_chat_dialog", None)
            if dlg is not None and dlg.isVisible() and new_path:
                dlg.set_pdf(new_path)
    except Exception:
        pass
