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
        QLineEdit, QPushButton, QFrame, QComboBox, QScrollArea, QWidget,
    )
    from packages.qt_compat.QtCore import Qt, QTimer
    from styles.theme import is_dark
    from packages.ai.provider import is_ai_available, get_active_provider, is_ollama_available
    from app.language_manager import get_selected_language, get_translation

    lang = get_selected_language()
    _t = lambda key, fallback: get_translation(lang, key, fallback)

    if is_dark():
        _STYLE = """
        QDialog { background: #16162A; }
        QLabel#title { color: #E8EEFF; font-size: 18px; font-weight: 800; letter-spacing: 0.2px; }
        QLabel#lbl { color: #E0E8FF; font-size: 13px; font-weight: 600; }
        QLabel#hint { color: #7C8DB8; font-size: 11px; }
        QLabel#status { color: #E8EEFF; font-size: 12px; font-weight: 600; }
        QLineEdit {
            background: #1E1E38;
            color: #E0E8FF;
            border: 1px solid #3A3A60;
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 13px;
            font-family: monospace;
        }
        QLineEdit::placeholder { color: #7C8DB8; }
        QLineEdit:focus { border-color: #6366f1; }
        QPushButton {
            background: #1E1E38;
            color: #B0B8E0;
            border: 1px solid #3A3A60;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton:hover { background: #2A2A50; border-color: #6060C0; }
        QPushButton#btn_save {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);
            color: white; border: none;
        }
        QPushButton#btn_save:hover { background: #7374f8; }
        QPushButton#btn_test { min-width: 80px; }
        QFrame#divider { background: #2A2A4A; }
        """
    else:
        _STYLE = """
        QDialog { background: #F8FAFC; }
        QLabel#title { color: #0F172A; font-size: 18px; font-weight: 800; letter-spacing: 0.2px; }
        QLabel#lbl { color: #111827; font-size: 13px; font-weight: 600; }
        QLabel#hint { color: #475569; font-size: 11px; }
        QLabel#status { color: #0F172A; font-size: 12px; font-weight: 600; }
        QLineEdit {
            background: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 13px;
            font-family: monospace;
        }
        QLineEdit::placeholder { color: #94A3B8; }
        QLineEdit:focus { border-color: #2563EB; }
        QPushButton {
            background: #E2E8F0;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton:hover { background: #CBD5E1; border-color: #94A3B8; }
        QPushButton#btn_save {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #1D4ED8);
            color: white; border: none;
        }
        QPushButton#btn_save:hover { background: #3B82F6; }
        QPushButton#btn_test { min-width: 80px; }
        QFrame#divider { background: #CBD5E1; }
        """

    dlg = QDialog(window)
    dlg.setWindowTitle(_t("ai.settings.title", "Cài đặt AI"))
    dlg.setModal(True)
    dlg.setMinimumWidth(680)
    dlg.resize(760, 680)
    dlg.setStyleSheet(_STYLE)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea(dlg)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)

    content = QWidget()
    root = QVBoxLayout(content)
    root.setContentsMargins(24, 20, 24, 20)
    root.setSpacing(10)
    scroll.setWidget(content)
    outer.addWidget(scroll)

    title = QLabel(_t("ai.settings.title", "Cài đặt AI"))
    title.setObjectName("title")
    root.addWidget(title)

    # Current status
    lbl_status = QLabel()
    lbl_status.setObjectName("status")
    if is_ai_available():
        provider = get_active_provider()
        lbl_status.setText(_t("ai.settings.status.using", "Trạng thái: Đang dùng {provider}").format(provider=provider))
        lbl_status.setStyleSheet("color:#166534;font-size:12px;")
    else:
        lbl_status.setText(_t("ai.settings.status.none", "Trạng thái: Chưa cấu hình AI."))
        lbl_status.setStyleSheet("color:#b45309;font-size:12px;")
    root.addWidget(lbl_status)

    div1 = QFrame(); div1.setObjectName("divider"); div1.setFixedHeight(1)
    root.addWidget(div1)

    lbl_provider = QLabel(_t("ai.settings.provider", "AI provider ưu tiên:"))
    lbl_provider.setObjectName("lbl")
    root.addWidget(lbl_provider)

    combo_provider = QComboBox()
    combo_provider.addItem(_t("ai.settings.auto", "Tự động"), "auto")
    combo_provider.addItem("Claude (Anthropic)", "claude")
    combo_provider.addItem("OpenAI GPT", "openai")
    combo_provider.addItem("Groq", "groq")
    combo_provider.addItem("OpenRouter", "openrouter")
    combo_provider.addItem("Google Gemini", "gemini")
    combo_provider.addItem("HuggingFace", "huggingface")
    combo_provider.addItem("Ollama local", "ollama")
    preferred_provider = os.environ.get("AI_PROVIDER", "auto").strip().lower() or "auto"
    for idx in range(combo_provider.count()):
        if combo_provider.itemData(idx) == preferred_provider:
            combo_provider.setCurrentIndex(idx)
            break
    root.addWidget(combo_provider)

    hint_provider = QLabel(_t("ai.settings.provider_hint", "Nếu provider ưu tiên lỗi, app sẽ tự thử provider khác đang có key."))
    hint_provider.setObjectName("hint")
    root.addWidget(hint_provider)

    # Anthropic API key
    lbl_anthropic = QLabel(_t("ai.settings.anthropic", "Anthropic API Key (Claude — ưu tiên 1):"))
    lbl_anthropic.setObjectName("lbl")
    root.addWidget(lbl_anthropic)

    edit_anthropic = QLineEdit()
    edit_anthropic.setPlaceholderText("sk-ant-…")
    edit_anthropic.setEchoMode(QLineEdit.EchoMode.Password)
    edit_anthropic.setText(os.environ.get("ANTHROPIC_API_KEY", ""))
    root.addWidget(edit_anthropic)

    hint_anthropic = QLabel(_t("ai.settings.anthropic_hint", "Lấy key tại: console.anthropic.com"))
    hint_anthropic.setObjectName("hint")
    root.addWidget(hint_anthropic)

    # OpenAI API key
    lbl_openai = QLabel(_t("ai.settings.openai", "OpenAI API Key (GPT — ưu tiên 2):"))
    lbl_openai.setObjectName("lbl")
    root.addWidget(lbl_openai)

    edit_openai = QLineEdit()
    edit_openai.setPlaceholderText("sk-…")
    edit_openai.setEchoMode(QLineEdit.EchoMode.Password)
    edit_openai.setText(os.environ.get("OPENAI_API_KEY", ""))
    root.addWidget(edit_openai)

    hint_openai = QLabel(_t("ai.settings.openai_hint", "Lấy key tại: platform.openai.com"))
    hint_openai.setObjectName("hint")
    root.addWidget(hint_openai)

    # Gemini
    lbl_gemini = QLabel(_t("ai.settings.gemini", "Google Gemini API Key:"))
    lbl_gemini.setObjectName("lbl")
    root.addWidget(lbl_gemini)

    edit_gemini = QLineEdit()
    edit_gemini.setPlaceholderText("AIza...")
    edit_gemini.setEchoMode(QLineEdit.EchoMode.Password)
    edit_gemini.setText(os.environ.get("GEMINI_API_KEY", ""))
    root.addWidget(edit_gemini)

    hint_gemini = QLabel(_t("ai.settings.gemini_hint", "Lấy key tại: ai.google.dev"))
    hint_gemini.setObjectName("hint")
    root.addWidget(hint_gemini)

    # Groq
    lbl_groq = QLabel(_t("ai.settings.groq", "Groq API Key:"))
    lbl_groq.setObjectName("lbl")
    root.addWidget(lbl_groq)

    edit_groq_key = QLineEdit()
    edit_groq_key.setPlaceholderText("gsk_...")
    edit_groq_key.setEchoMode(QLineEdit.EchoMode.Password)
    edit_groq_key.setText(os.environ.get("GROQ_API_KEY", ""))
    root.addWidget(edit_groq_key)

    row_groq = QHBoxLayout(); row_groq.setSpacing(8)
    edit_groq_model = QLineEdit()
    edit_groq_model.setPlaceholderText("llama-3.3-70b-versatile")
    edit_groq_model.setText(os.environ.get("GROQ_MODEL", ""))
    row_groq.addWidget(edit_groq_model, 1)
    edit_groq_base = QLineEdit()
    edit_groq_base.setPlaceholderText("https://api.groq.com/openai/v1")
    edit_groq_base.setText(os.environ.get("GROQ_BASE_URL", ""))
    row_groq.addWidget(edit_groq_base, 1)
    root.addLayout(row_groq)

    hint_groq = QLabel(_t("ai.settings.groq_hint", "Groq dùng OpenAI-compatible API, có thể đổi model/base URL nếu cần."))
    hint_groq.setObjectName("hint")
    root.addWidget(hint_groq)

    # OpenRouter
    lbl_openrouter = QLabel(_t("ai.settings.openrouter", "OpenRouter API Key:"))
    lbl_openrouter.setObjectName("lbl")
    root.addWidget(lbl_openrouter)

    edit_openrouter_key = QLineEdit()
    edit_openrouter_key.setPlaceholderText("sk-or-v1-...")
    edit_openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
    edit_openrouter_key.setText(os.environ.get("OPENROUTER_API_KEY", ""))
    root.addWidget(edit_openrouter_key)

    row_openrouter = QHBoxLayout(); row_openrouter.setSpacing(8)
    edit_openrouter_model = QLineEdit()
    edit_openrouter_model.setPlaceholderText("openai/gpt-4o-mini")
    edit_openrouter_model.setText(os.environ.get("OPENROUTER_MODEL", ""))
    row_openrouter.addWidget(edit_openrouter_model, 1)
    edit_openrouter_base = QLineEdit()
    edit_openrouter_base.setPlaceholderText("https://openrouter.ai/api/v1")
    edit_openrouter_base.setText(os.environ.get("OPENROUTER_BASE_URL", ""))
    row_openrouter.addWidget(edit_openrouter_base, 1)
    root.addLayout(row_openrouter)

    row_openrouter_meta = QHBoxLayout(); row_openrouter_meta.setSpacing(8)
    edit_openrouter_ref = QLineEdit()
    edit_openrouter_ref.setPlaceholderText("HTTP-Referer")
    edit_openrouter_ref.setText(os.environ.get("OPENROUTER_HTTP_REFERER", ""))
    row_openrouter_meta.addWidget(edit_openrouter_ref, 1)
    edit_openrouter_name = QLineEdit()
    edit_openrouter_name.setPlaceholderText("X-Title")
    edit_openrouter_name.setText(os.environ.get("OPENROUTER_APP_NAME", ""))
    row_openrouter_meta.addWidget(edit_openrouter_name, 1)
    root.addLayout(row_openrouter_meta)

    hint_openrouter = QLabel(_t("ai.settings.openrouter_hint", "OpenRouter cần key + model; nên giữ referer/app name để tránh bị chặn."))
    hint_openrouter.setObjectName("hint")
    root.addWidget(hint_openrouter)

    # HuggingFace
    lbl_hf = QLabel(_t("ai.settings.hf", "HuggingFace API Token:"))
    lbl_hf.setObjectName("lbl")
    root.addWidget(lbl_hf)

    edit_hf_key = QLineEdit()
    edit_hf_key.setPlaceholderText("hf_...")
    edit_hf_key.setEchoMode(QLineEdit.EchoMode.Password)
    edit_hf_key.setText(os.environ.get("HF_API_KEY", ""))
    root.addWidget(edit_hf_key)

    row_hf = QHBoxLayout(); row_hf.setSpacing(8)
    edit_hf_model = QLineEdit()
    edit_hf_model.setPlaceholderText("Qwen/Qwen2.5-7B-Instruct")
    edit_hf_model.setText(os.environ.get("HF_MODEL", ""))
    row_hf.addWidget(edit_hf_model, 1)
    root.addLayout(row_hf)

    hint_hf = QLabel(_t("ai.settings.hf_hint", "HuggingFace Inference API có thể dùng khi cần thêm fallback miễn phí."))
    hint_hf.setObjectName("hint")
    root.addWidget(hint_hf)

    div2 = QFrame(); div2.setObjectName("divider"); div2.setFixedHeight(1)
    root.addWidget(div2)

    # Ollama (offline local LLM)
    lbl_ollama = QLabel(_t("ai.settings.ollama", "Ollama — AI offline/nội bộ (ưu tiên 3, không cần internet):"))
    lbl_ollama.setObjectName("lbl")
    root.addWidget(lbl_ollama)

    row_ollama = QHBoxLayout(); row_ollama.setSpacing(8)
    edit_ollama_url = QLineEdit()
    edit_ollama_url.setPlaceholderText("http://localhost:11434")
    edit_ollama_url.setText(os.environ.get("OLLAMA_BASE_URL", ""))
    row_ollama.addWidget(edit_ollama_url, 1)

    btn_test_ollama = QPushButton(_t("ai.settings.ollama_test", "Kiểm tra"))
    btn_test_ollama.setObjectName("btn_test")

    ollama_ok = is_ollama_available()
    _ollama_status_color = "#166534" if ollama_ok else "#64748B"
    _ollama_status_text  = _t("ai.settings.ollama_running", "Đang chạy") if ollama_ok else _t("ai.settings.ollama_down", "Không kết nối")
    lbl_ollama_status = QLabel(_ollama_status_text)
    lbl_ollama_status.setStyleSheet(f"color:{_ollama_status_color};font-size:11px;min-width:90px;")

    def _test_ollama():
        from packages.ai.provider import is_ollama_available as _check
        url = edit_ollama_url.text().strip()
        if url:
            os.environ["OLLAMA_BASE_URL"] = url
        ok = _check()
        if ok:
            lbl_ollama_status.setText(_t("ai.settings.ollama_running", "Đang chạy"))
            lbl_ollama_status.setStyleSheet("color:#166534;font-size:11px;")
        else:
            lbl_ollama_status.setText(_t("ai.settings.ollama_down", "Không kết nối"))
            lbl_ollama_status.setStyleSheet("color:#B91C1C;font-size:11px;")

    btn_test_ollama.clicked.connect(_test_ollama)
    row_ollama.addWidget(btn_test_ollama)
    row_ollama.addWidget(lbl_ollama_status)
    root.addLayout(row_ollama)

    lbl_ollama_model = QLabel(_t("ai.settings.ollama_model", "Model Ollama:"))
    lbl_ollama_model.setObjectName("lbl")
    root.addWidget(lbl_ollama_model)

    edit_ollama_model = QLineEdit()
    edit_ollama_model.setPlaceholderText("llama3")
    edit_ollama_model.setText(os.environ.get("OLLAMA_MODEL", ""))
    root.addWidget(edit_ollama_model)

    hint_ollama = QLabel(_t("ai.settings.ollama_hint", "Cài Ollama tại ollama.com  •  Gõ: ollama pull llama3  •  Tự động phát hiện khi khởi động app"))
    hint_ollama.setObjectName("hint")
    root.addWidget(hint_ollama)

    div3 = QFrame(); div3.setObjectName("divider"); div3.setFixedHeight(1)
    root.addWidget(div3)

    btn_row = QHBoxLayout(); btn_row.setSpacing(10)

    btn_reset = QPushButton(_t("ai.settings.reset", "Xóa cấu hình AI local"))
    btn_reset.setObjectName("btn_test")
    btn_reset.setToolTip(_t("ai.settings.reset_tip", "Xóa toàn bộ key/cấu hình AI đã lưu trên máy này."))

    btn_cancel = QPushButton(_t("dialog.cancel", "Hủy"))
    btn_cancel.clicked.connect(dlg.reject)

    btn_save = QPushButton(_t("ai.settings.save", "Lưu"))
    btn_save.setObjectName("btn_save")

    def _reset_local_ai_config():
        from packages.qt_compat.QtWidgets import QMessageBox
        from packages.platform import get_app_data_dir

        reply = QMessageBox.question(
            dlg,
            _t("ai.settings.reset", "Xóa cấu hình AI local"),
            _t("ai.settings.reset_tip", "Xóa toàn bộ cấu hình AI đã lưu trên máy này?\nThao tác này chỉ ảnh hưởng máy hiện tại."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            import json
            config_path = os.path.join(get_app_data_dir(), "ai_config.json")
            if os.path.exists(config_path):
                os.remove(config_path)
        except Exception:
            pass

        for key in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "GROQ_BASE_URL",
            "OPENROUTER_API_KEY",
            "OPENROUTER_MODEL",
            "OPENROUTER_BASE_URL",
            "OPENROUTER_HTTP_REFERER",
            "OPENROUTER_APP_NAME",
            "HF_API_KEY",
            "HF_MODEL",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "AI_PROVIDER",
        ):
            os.environ.pop(key, None)

        lbl_status.setText(_t("ai.settings.status.none", "Trạng thái: Chưa cấu hình AI."))
        lbl_status.setStyleSheet("color:#b45309;font-size:12px;")
        edit_anthropic.clear()
        edit_openai.clear()
        edit_gemini.clear()
        edit_groq_key.clear()
        edit_groq_model.clear()
        edit_groq_base.clear()
        edit_openrouter_key.clear()
        edit_openrouter_model.clear()
        edit_openrouter_base.clear()
        edit_openrouter_ref.clear()
        edit_openrouter_name.clear()
        edit_hf_key.clear()
        edit_hf_model.clear()
        edit_ollama_url.clear()
        edit_ollama_model.clear()
        combo_provider.setCurrentIndex(0)

    btn_reset.clicked.connect(_reset_local_ai_config)

    def _save():
        ai_provider  = combo_provider.currentData() or "auto"
        anthropic_key = edit_anthropic.text().strip()
        openai_key    = edit_openai.text().strip()
        gemini_key    = edit_gemini.text().strip()
        groq_key      = edit_groq_key.text().strip()
        groq_model    = edit_groq_model.text().strip()
        groq_base     = edit_groq_base.text().strip()
        openrouter_key = edit_openrouter_key.text().strip()
        openrouter_model = edit_openrouter_model.text().strip()
        openrouter_base = edit_openrouter_base.text().strip()
        openrouter_ref  = edit_openrouter_ref.text().strip()
        openrouter_name = edit_openrouter_name.text().strip()
        hf_key        = edit_hf_key.text().strip()
        hf_model      = edit_hf_model.text().strip()
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

        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key
        elif "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        elif "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        if groq_model:
            os.environ["GROQ_MODEL"] = groq_model
        else:
            os.environ.pop("GROQ_MODEL", None)
        if groq_base:
            os.environ["GROQ_BASE_URL"] = groq_base
        else:
            os.environ.pop("GROQ_BASE_URL", None)

        if openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = openrouter_key
        elif "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]
        if openrouter_model:
            os.environ["OPENROUTER_MODEL"] = openrouter_model
        else:
            os.environ.pop("OPENROUTER_MODEL", None)
        if openrouter_base:
            os.environ["OPENROUTER_BASE_URL"] = openrouter_base
        else:
            os.environ.pop("OPENROUTER_BASE_URL", None)
        if openrouter_ref:
            os.environ["OPENROUTER_HTTP_REFERER"] = openrouter_ref
        else:
            os.environ.pop("OPENROUTER_HTTP_REFERER", None)
        if openrouter_name:
            os.environ["OPENROUTER_APP_NAME"] = openrouter_name
        else:
            os.environ.pop("OPENROUTER_APP_NAME", None)

        if hf_key:
            os.environ["HF_API_KEY"] = hf_key
        elif "HF_API_KEY" in os.environ:
            del os.environ["HF_API_KEY"]
        if hf_model:
            os.environ["HF_MODEL"] = hf_model
        else:
            os.environ.pop("HF_MODEL", None)

        if ollama_url:
            os.environ["OLLAMA_BASE_URL"] = ollama_url
        else:
            os.environ.pop("OLLAMA_BASE_URL", None)
        if ollama_model:
            os.environ["OLLAMA_MODEL"] = ollama_model
        else:
            os.environ.pop("OLLAMA_MODEL", None)

        os.environ["AI_PROVIDER"] = ai_provider

        _persist_api_keys(
            anthropic_key,
            openai_key,
            gemini_key,
            groq_key,
            groq_model,
            groq_base,
            openrouter_key,
            openrouter_model,
            openrouter_base,
            openrouter_ref,
            openrouter_name,
            hf_key,
            hf_model,
            ollama_url,
            ollama_model,
            ai_provider,
        )

        from packages.ai.provider import is_ai_available, get_active_provider
        if is_ai_available():
            lbl_status.setText(_t("ai.settings.saved_status", "Đã lưu. Đang dùng: {provider}").format(provider=get_active_provider()))
            lbl_status.setStyleSheet("color:#166534;font-size:12px;")
        else:
            lbl_status.setText(_t("ai.settings.deleted_status", "Đã xóa cấu hình AI."))
            lbl_status.setStyleSheet("color:#b45309;font-size:12px;")

        orig = btn_save.text()
        btn_save.setText(_t("ai.settings.saved", "Đã lưu!"))
        QTimer.singleShot(1500, lambda: btn_save.setText(orig))

    btn_save.clicked.connect(_save)

    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_reset)
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


def _persist_api_keys(
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    groq_key: str = "",
    groq_model: str = "",
    groq_base: str = "",
    openrouter_key: str = "",
    openrouter_model: str = "",
    openrouter_base: str = "",
    openrouter_ref: str = "",
    openrouter_name: str = "",
    hf_key: str = "",
    hf_model: str = "",
    ollama_url: str = "",
    ollama_model: str = "",
    ai_provider: str = "auto",
):
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

        if gemini_key:
            data["GEMINI_API_KEY"] = gemini_key
        else:
            data.pop("GEMINI_API_KEY", None)

        if groq_key:
            data["GROQ_API_KEY"] = groq_key
        else:
            data.pop("GROQ_API_KEY", None)
        if groq_model:
            data["GROQ_MODEL"] = groq_model
        else:
            data.pop("GROQ_MODEL", None)
        if groq_base:
            data["GROQ_BASE_URL"] = groq_base
        else:
            data.pop("GROQ_BASE_URL", None)

        if openrouter_key:
            data["OPENROUTER_API_KEY"] = openrouter_key
        else:
            data.pop("OPENROUTER_API_KEY", None)
        if openrouter_model:
            data["OPENROUTER_MODEL"] = openrouter_model
        else:
            data.pop("OPENROUTER_MODEL", None)
        if openrouter_base:
            data["OPENROUTER_BASE_URL"] = openrouter_base
        else:
            data.pop("OPENROUTER_BASE_URL", None)
        if openrouter_ref:
            data["OPENROUTER_HTTP_REFERER"] = openrouter_ref
        else:
            data.pop("OPENROUTER_HTTP_REFERER", None)
        if openrouter_name:
            data["OPENROUTER_APP_NAME"] = openrouter_name
        else:
            data.pop("OPENROUTER_APP_NAME", None)

        if hf_key:
            data["HF_API_KEY"] = hf_key
        else:
            data.pop("HF_API_KEY", None)
        if hf_model:
            data["HF_MODEL"] = hf_model
        else:
            data.pop("HF_MODEL", None)

        if ollama_url:
            data["OLLAMA_BASE_URL"] = ollama_url
        else:
            data.pop("OLLAMA_BASE_URL", None)
        if ollama_model:
            data["OLLAMA_MODEL"] = ollama_model
        else:
            data.pop("OLLAMA_MODEL", None)

        data["AI_PROVIDER"] = ai_provider or "auto"

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
        for key in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "GROQ_BASE_URL",
            "OPENROUTER_API_KEY",
            "OPENROUTER_MODEL",
            "OPENROUTER_BASE_URL",
            "OPENROUTER_HTTP_REFERER",
            "OPENROUTER_APP_NAME",
            "HF_API_KEY",
            "HF_MODEL",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "AI_PROVIDER",
        ):
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
            search_dlg = getattr(widget, "_ai_search_dialog", None)
            if search_dlg is not None and search_dlg.isVisible() and new_path:
                search_dlg.set_pdf(new_path)
    except Exception:
        pass
