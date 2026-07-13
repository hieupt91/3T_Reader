"""AI actions — mở các dialog AI từ cửa sổ chính."""
from __future__ import annotations

import os

from app.actions._guard import require_document


@require_document(show_message=True)
def open_translate_dialog(window, initial_text: str = None):
    """Mở dialog dịch thuật trang PDF hiện tại."""
    from app.license_dialog import require_plan
    if not require_plan(window, "Dịch văn bản AI", ["enterprise"]):
        return

    pdf_path = _current_pdf_path(window)
    current_page = _current_page(window)

    from app.ai_translate_dialog import AITranslateDialog
    dlg = AITranslateDialog(window, pdf_path, current_page, selected_text=initial_text or "")
    dlg.exec()


@require_document(show_message=True)
def open_summarize_dialog(window):
    """Mở dialog tóm tắt tài liệu."""
    from app.license_dialog import require_plan
    if not require_plan(window, "Tóm tắt tài liệu bằng AI", ["enterprise"]):
        return

    pdf_path = _current_pdf_path(window)

    from app.ai_summarize_dialog import AISummarizeDialog
    dlg = AISummarizeDialog(window, pdf_path)
    dlg.exec()


@require_document(show_message=True)
def open_chat_dialog(window):
    """Mở dialog chat với PDF (non-modal, có thể giữ mở khi đọc)."""
    from app.license_dialog import require_plan
    if not require_plan(window, "Trợ lý AI ChatPDF", ["enterprise"]):
        return

    pdf_path = _current_pdf_path(window)
    history_identity_path = _current_history_identity_path(window)

    existing = getattr(window, "_ai_chat_dialog", None)
    if existing is not None:
        existing.set_pdf(pdf_path, history_identity_path=history_identity_path)
        existing.show()
        existing.raise_()
        existing.activateWindow()
        return

    from app.ai_chat_dialog import AIChatDialog
    dlg = AIChatDialog(window, pdf_path, history_identity_path=history_identity_path)
    window._ai_chat_dialog = dlg
    dlg.show()


@require_document(show_message=True)
def open_search_dialog(window):
    """Mở dialog tìm kiếm theo nghĩa (non-modal, có thể giữ mở khi đọc)."""
    from app.license_dialog import require_plan
    if not require_plan(window, "Tìm kiếm ngữ nghĩa (Semantic Search)", ["enterprise"]):
        return

    pdf_path = _current_pdf_path(window)

    existing = getattr(window, "_ai_search_dialog", None)
    if existing is not None:
        if existing._pdf_path != pdf_path:
            existing.set_pdf(pdf_path)
        existing.show()
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
        QLineEdit, QPushButton, QFrame, QScrollArea, QWidget,
        QSizePolicy, QStackedWidget, QListWidget, QListWidgetItem,
    )
    from packages.qt_compat.QtCore import Qt, QTimer, QSize
    from styles.theme import is_dark
    from packages.ai.provider import is_ai_available, get_active_provider, is_ollama_available
    from app.language_manager import get_selected_language, get_translation

    lang = get_selected_language()
    _t = lambda key, fallback: get_translation(lang, key, fallback)

    dark = is_dark()
    if dark:
        bg          = "#0F0F1A"
        sidebar     = "#16162A"
        card_bg     = "#1E1E36"
        card_sel    = "#252545"
        card_bor    = "#3A3A60"
        card_sel_bor = "#6366f1"
        text_pri    = "#E8EEFF"
        text_sec    = "#9BA8C8"
        text_hint   = "#6270A0"
        inp_bg      = "#12122A"
        inp_bor     = "#3A3A60"
        inp_focus   = "#6366f1"
        div_col     = "#2A2A48"
        btn_bg      = "#252545"
        btn_bor     = "#3A3A60"
        save_grad   = "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6)"
        save_hov    = "#7374f8"
        badge_ok    = "#166534"
        badge_warn  = "#92400e"
        badge_ok_txt   = "#86efac"
        badge_warn_txt = "#fcd34d"
    else:
        bg          = "#F0F4FF"
        sidebar     = "#FFFFFF"
        card_bg     = "#FFFFFF"
        card_sel    = "#EEF2FF"
        card_bor    = "#E2E8F0"
        card_sel_bor = "#6366f1"
        text_pri    = "#0F172A"
        text_sec    = "#475569"
        text_hint   = "#94A3B8"
        inp_bg      = "#FFFFFF"
        inp_bor     = "#CBD5E1"
        inp_focus   = "#6366f1"
        div_col     = "#E2E8F0"
        btn_bg      = "#F1F5F9"
        btn_bor     = "#CBD5E1"
        save_grad   = "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #4F46E5)"
        save_hov    = "#4F46E5"
        badge_ok    = "#DCFCE7"
        badge_warn  = "#FEF9C3"
        badge_ok_txt   = "#166534"
        badge_warn_txt = "#92400e"

    STYLE = f"""
    QDialog {{ background: {bg}; }}
    QWidget#sidebar {{ background: {sidebar}; border-right: 1px solid {div_col}; }}
    QWidget#rightpanel {{ background: {bg}; }}
    QLabel#h1 {{ color: {text_pri}; font-size: 20px; font-weight: 800; }}
    QLabel#h2 {{ color: {text_pri}; font-size: 15px; font-weight: 700; margin-top: 4px; }}
    QLabel#lbl {{ color: {text_sec}; font-size: 12px; font-weight: 600; margin-top: 6px; }}
    QLabel#hint {{ color: {text_hint}; font-size: 11px; }}
    QLineEdit {{
        background: {inp_bg};
        color: {text_pri};
        border: 1.5px solid {inp_bor};
        border-radius: 8px;
        padding: 9px 14px;
        font-size: 13px;
        font-family: "Consolas","Menlo","monospace";
    }}
    QLineEdit:focus {{ border-color: {inp_focus}; }}
    QLineEdit::placeholder {{ color: {text_hint}; }}
    QPushButton {{
        background: {btn_bg};
        color: {text_pri};
        border: 1px solid {btn_bor};
        border-radius: 8px;
        padding: 9px 20px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{ border-color: {inp_focus}; color: {inp_focus}; }}
    QPushButton#btn_save {{
        background: {save_grad};
        color: white; border: none;
        padding: 10px 32px;
        font-size: 13px;
        font-weight: 700;
        border-radius: 10px;
    }}
    QPushButton#btn_save:hover {{ background: {save_hov}; }}
    QPushButton#btn_danger {{ color: #ef4444; border-color: #ef4444; }}
    QPushButton#btn_danger:hover {{ background: #ef4444; color: white; }}
    QPushButton#btn_test {{ min-width: 80px; }}
    QFrame#divider {{ background: {div_col}; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget::item {{ background: transparent; border: none; padding: 0px; margin: 3px 8px; }}
    QListWidget::item:selected {{ background: transparent; }}
    """

    dlg = QDialog(window)
    dlg.setWindowTitle(_t("ai.settings.title", "Cài đặt AI"))
    dlg.setModal(True)
    dlg.resize(860, 620)
    dlg.setMinimumSize(780, 540)
    dlg.setStyleSheet(STYLE)

    main_layout = QHBoxLayout(dlg)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # ─── SIDEBAR ───────────────────────────────────────────────
    sidebar_w = QWidget()
    sidebar_w.setObjectName("sidebar")
    sidebar_w.setFixedWidth(220)
    sidebar_lay = QVBoxLayout(sidebar_w)
    sidebar_lay.setContentsMargins(0, 20, 0, 20)
    sidebar_lay.setSpacing(0)

    lbl_side_title = QLabel("  🤖  AI Provider")
    lbl_side_title.setStyleSheet(
        f"font-size:12px;font-weight:700;color:{text_hint};"
        "padding:0 16px 12px 16px;letter-spacing:1px;")
    sidebar_lay.addWidget(lbl_side_title)

    div_top = QFrame(); div_top.setObjectName("divider"); div_top.setFixedHeight(1)
    sidebar_lay.addWidget(div_top)
    sidebar_lay.addSpacing(8)

    providers = [
        ("claude",      "\U0001f7e3", "Anthropic Claude",  "API Key"),
        ("openai",      "\U0001f7e2", "OpenAI GPT",         "API Key"),
        ("gemini",      "\U0001f535", "Google Gemini",      "API Key"),
        ("groq",        "\u26a1",     "Groq",               "API Key + Model"),
        ("openrouter",  "\U0001f310", "OpenRouter",         "API Key + Model"),
        ("huggingface", "\U0001f917", "HuggingFace",        "Token + Model"),
        ("ollama",      "\U0001f999", "Ollama Local",       "URL + Model"),
    ]

    active_prov = get_active_provider() if is_ai_available() else ""
    env_prov    = os.environ.get("AI_PROVIDER", "auto").strip().lower() or "auto"

    list_w = QListWidget()
    list_w.setSpacing(2)
    sidebar_lay.addWidget(list_w)

    card_refs = {}

    def _make_card(pid, icon, name, sub):
        w = QWidget()
        w.setObjectName("pcard")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        row = QHBoxLayout()
        l_icon = QLabel(icon)
        l_icon.setStyleSheet("font-size:18px;")
        l_name = QLabel(f"<b>{name}</b>")
        l_name.setStyleSheet(f"font-size:13px;color:{text_pri};")
        row.addWidget(l_icon)
        row.addWidget(l_name)
        row.addStretch()
        if pid == active_prov:
            badge = QLabel("\u2713 Active")
            badge.setStyleSheet(
                f"font-size:10px;font-weight:700;color:{badge_ok_txt};"
                f"background:{badge_ok};border-radius:6px;padding:2px 6px;")
            row.addWidget(badge)
        lay.addLayout(row)
        l_sub = QLabel(sub)
        l_sub.setStyleSheet(f"font-size:11px;color:{text_hint};margin-left:26px;")
        lay.addWidget(l_sub)
        w.setStyleSheet(
            f"QWidget#pcard{{background:{card_bg};border:1.5px solid {card_bor};border-radius:10px;}}")
        return w

    prov_ids = [p[0] for p in providers]

    for pid, icon, name, sub in providers:
        item = QListWidgetItem()
        card = _make_card(pid, icon, name, sub)
        item.setSizeHint(QSize(204, 58))
        list_w.addItem(item)
        list_w.setItemWidget(item, card)
        card_refs[pid] = (item, card)

    sidebar_lay.addStretch()
    main_layout.addWidget(sidebar_w)

    # ─── RIGHT PANEL ────────────────────────────────────────────
    right_w = QWidget()
    right_w.setObjectName("rightpanel")
    right_lay = QVBoxLayout(right_w)
    right_lay.setContentsMargins(32, 28, 32, 24)
    right_lay.setSpacing(0)

    # Header
    hdr = QHBoxLayout()
    lbl_title = QLabel("Cài đặt AI")
    lbl_title.setObjectName("h1")
    hdr.addWidget(lbl_title)
    hdr.addStretch()

    if is_ai_available():
        _st = f"\u2713 Đang dùng: {get_active_provider()}"
        _ss = (f"color:{badge_ok_txt};background:{badge_ok};"
               "border-radius:8px;padding:5px 14px;font-size:12px;font-weight:700;")
    else:
        _st = "\u26a0 Chưa cấu hình AI"
        _ss = (f"color:{badge_warn_txt};background:{badge_warn};"
               "border-radius:8px;padding:5px 14px;font-size:12px;font-weight:700;")

    lbl_status = QLabel(_st)
    lbl_status.setStyleSheet(_ss)
    hdr.addWidget(lbl_status)
    right_lay.addLayout(hdr)
    right_lay.addSpacing(4)

    lbl_sub = QLabel("Chọn nhà cung cấp AI ở bên trái và nhập thông tin API của bạn.")
    lbl_sub.setStyleSheet(f"color:{text_hint};font-size:12px;")
    right_lay.addWidget(lbl_sub)
    right_lay.addSpacing(18)

    div0 = QFrame(); div0.setObjectName("divider"); div0.setFixedHeight(1)
    right_lay.addWidget(div0)
    right_lay.addSpacing(14)

    lbl_page_name = QLabel("Anthropic Claude")
    lbl_page_name.setObjectName("h2")
    right_lay.addWidget(lbl_page_name)
    right_lay.addSpacing(10)

    # Stacked pages
    stack = QStackedWidget()
    right_lay.addWidget(stack, 1)

    def _page(fields):
        """fields = [(label, placeholder, env_key, echo_bool, hint)]"""
        pg = QWidget()
        ly = QVBoxLayout(pg)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(6)
        eds = {}
        for lbl_txt, ph, ekey, echo, hint in fields:
            lbl = QLabel(lbl_txt); lbl.setObjectName("lbl"); ly.addWidget(lbl)
            ed = QLineEdit()
            ed.setPlaceholderText(ph)
            if echo:
                ed.setEchoMode(QLineEdit.EchoMode.Password)
            ed.setText(os.environ.get(ekey, ""))
            ly.addWidget(ed)
            eds[ekey] = ed
            if hint:
                h = QLabel(hint); h.setObjectName("hint"); h.setWordWrap(True); ly.addWidget(h)
            ly.addSpacing(4)
        ly.addStretch()
        return pg, eds

    pg_claude, ed_claude = _page([
        ("API Key", "sk-ant-…", "ANTHROPIC_API_KEY", True,
         "Lấy key tại console.anthropic.com → API Keys")])
    pg_openai, ed_openai = _page([
        ("API Key", "sk-…", "OPENAI_API_KEY", True,
         "Lấy key tại platform.openai.com → API keys")])
    pg_gemini, ed_gemini = _page([
        ("API Key", "AIza…", "GEMINI_API_KEY", True,
         "Lấy key tại aistudio.google.com → Get API key")])
    pg_groq, ed_groq = _page([
        ("API Key", "gsk_…", "GROQ_API_KEY", True, "Lấy key tại console.groq.com"),
        ("Model", "llama3-70b-8192", "GROQ_MODEL", False, "Mặc định: llama3-70b-8192"),
        ("Base URL (tuỳ chọn)", "https://api.groq.com/openai/v1", "GROQ_BASE_URL", False, ""),
    ])
    pg_or, ed_or = _page([
        ("API Key", "sk-or-…", "OPENROUTER_API_KEY", True, "Lấy key tại openrouter.ai → Keys"),
        ("Model", "openai/gpt-4o", "OPENROUTER_MODEL", False,
         "Ví dụ: openai/gpt-4o, anthropic/claude-3-haiku"),
        ("Base URL (tuỳ chọn)", "https://openrouter.ai/api/v1", "OPENROUTER_BASE_URL", False, ""),
        ("HTTP Referer (tuỳ chọn)", "https://yoursite.com", "OPENROUTER_HTTP_REFERER", False, ""),
        ("App Name (tuỳ chọn)", "3T Reader", "OPENROUTER_APP_NAME", False, ""),
    ])
    pg_hf, ed_hf = _page([
        ("HuggingFace Token", "hf_…", "HF_API_KEY", True,
         "Lấy token tại huggingface.co → Settings → Access Tokens"),
        ("Model ID", "meta-llama/Meta-Llama-3-8B-Instruct", "HF_MODEL", False, ""),
    ])

    # Ollama page (special)
    pg_ol = QWidget()
    ly_ol = QVBoxLayout(pg_ol)
    ly_ol.setContentsMargins(0, 0, 0, 0); ly_ol.setSpacing(6)
    lb_url = QLabel("URL Ollama server"); lb_url.setObjectName("lbl"); ly_ol.addWidget(lb_url)
    row_url = QHBoxLayout()
    ed_ol_url = QLineEdit()
    ed_ol_url.setPlaceholderText("http://localhost:11434")
    ed_ol_url.setText(os.environ.get("OLLAMA_BASE_URL", ""))
    row_url.addWidget(ed_ol_url, 1)
    btn_test_ol = QPushButton("Kiểm tra"); btn_test_ol.setObjectName("btn_test")
    btn_test_ol.setFixedWidth(90)
    ol_ok = is_ollama_available()
    lbl_ol_st = QLabel("\U0001f7e2 Kết nối" if ol_ok else "\U0001f534 Không kết nối")
    lbl_ol_st.setStyleSheet(f"font-size:12px;color:{'#22c55e' if ol_ok else '#ef4444'};")
    def _test_ol():
        u = ed_ol_url.text().strip()
        if u: os.environ["OLLAMA_BASE_URL"] = u
        from packages.ai.provider import is_ollama_available as _chk
        ok = _chk()
        lbl_ol_st.setText("\U0001f7e2 Kết nối" if ok else "\U0001f534 Không kết nối")
        lbl_ol_st.setStyleSheet(f"font-size:12px;color:{'#22c55e' if ok else '#ef4444'};")
    btn_test_ol.clicked.connect(_test_ol)
    row_url.addWidget(btn_test_ol); row_url.addWidget(lbl_ol_st)
    ly_ol.addLayout(row_url)
    lb_mdl = QLabel("Model Ollama"); lb_mdl.setObjectName("lbl"); ly_ol.addWidget(lb_mdl)
    ed_ol_mdl = QLineEdit()
    ed_ol_mdl.setPlaceholderText("llama3")
    ed_ol_mdl.setText(os.environ.get("OLLAMA_MODEL", ""))
    ly_ol.addWidget(ed_ol_mdl)
    h_ol = QLabel("Cài Ollama tại ollama.com \u2192 Chạy: ollama pull llama3 \u2192 App tự nhận khi khởi động")
    h_ol.setObjectName("hint"); h_ol.setWordWrap(True); ly_ol.addWidget(h_ol)
    ly_ol.addStretch()
    ed_ollama = {"OLLAMA_BASE_URL": ed_ol_url, "OLLAMA_MODEL": ed_ol_mdl}

    all_pages = [pg_claude, pg_openai, pg_gemini, pg_groq, pg_or, pg_hf, pg_ol]
    all_edits = [ed_claude, ed_openai, ed_gemini, ed_groq, ed_or, ed_hf, ed_ollama]
    for pg in all_pages:
        stack.addWidget(pg)

    # ─── Card selection logic ────────────────────────────────────
    def _switch(idx):
        if idx < 0: return
        stack.setCurrentIndex(idx)
        pid, icon, name, _ = providers[idx]
        lbl_page_name.setText(f"{icon}  {name}")
        for i, (pid2, _, _, _) in enumerate(providers):
            _, card = card_refs[pid2]
            sel = (i == idx)
            card.setStyleSheet(
                f"QWidget#pcard{{background:{card_sel if sel else card_bg};"
                f"border:1.5px solid {card_sel_bor if sel else card_bor};"
                "border-radius:10px;}}")

    list_w.currentRowChanged.connect(_switch)
    init_idx = prov_ids.index(env_prov) if env_prov in prov_ids else 0
    list_w.setCurrentRow(init_idx)

    # ─── Bottom bar ──────────────────────────────────────────────
    right_lay.addSpacing(16)
    div_bot = QFrame(); div_bot.setObjectName("divider"); div_bot.setFixedHeight(1)
    right_lay.addWidget(div_bot)
    right_lay.addSpacing(12)

    btn_row = QHBoxLayout(); btn_row.setSpacing(10)
    btn_reset  = QPushButton("\U0001f5d1  Xoá cấu hình AI")
    btn_reset.setObjectName("btn_danger")
    btn_cancel = QPushButton("Huỷ")
    btn_save   = QPushButton("\U0001f4be  Lưu cài đặt")
    btn_save.setObjectName("btn_save")

    def _reset_all():
        from packages.qt_compat.QtWidgets import QMessageBox
        from packages.platform import get_app_data_dir
        reply = QMessageBox.question(dlg, "Xoá cấu hình AI",
            "Xoá toàn bộ API key và cấu hình AI đã lưu trên máy này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        try:
            cfg = os.path.join(get_app_data_dir(), "ai_config.json")
            if os.path.exists(cfg): os.remove(cfg)
        except Exception: pass
        for key in ("ANTHROPIC_API_KEY","OPENAI_API_KEY","GEMINI_API_KEY","GROQ_API_KEY",
                    "GROQ_MODEL","GROQ_BASE_URL","OPENROUTER_API_KEY","OPENROUTER_MODEL",
                    "OPENROUTER_BASE_URL","OPENROUTER_HTTP_REFERER","OPENROUTER_APP_NAME",
                    "HF_API_KEY","HF_MODEL","OLLAMA_BASE_URL","OLLAMA_MODEL","AI_PROVIDER"):
            os.environ.pop(key, None)
        for em in all_edits:
            for ed in em.values(): ed.clear()
        lbl_status.setText("\u26a0 Chưa cấu hình AI")
        lbl_status.setStyleSheet(
            f"color:{badge_warn_txt};background:{badge_warn};"
            "border-radius:8px;padding:5px 14px;font-size:12px;font-weight:700;")

    def _save():
        all_env = {}
        for em in all_edits:
            for ekey, ed in em.items():
                all_env[ekey] = ed.text().strip()
        all_env["AI_PROVIDER"] = prov_ids[list_w.currentRow()]
        for k, v in all_env.items():
            if v: os.environ[k] = v
            else: os.environ.pop(k, None)
        _persist_api_keys(
            all_env.get("ANTHROPIC_API_KEY",""), all_env.get("OPENAI_API_KEY",""),
            all_env.get("GEMINI_API_KEY",""),    all_env.get("GROQ_API_KEY",""),
            all_env.get("GROQ_MODEL",""),         all_env.get("GROQ_BASE_URL",""),
            all_env.get("OPENROUTER_API_KEY",""), all_env.get("OPENROUTER_MODEL",""),
            all_env.get("OPENROUTER_BASE_URL",""),all_env.get("OPENROUTER_HTTP_REFERER",""),
            all_env.get("OPENROUTER_APP_NAME",""),all_env.get("HF_API_KEY",""),
            all_env.get("HF_MODEL",""),           all_env.get("OLLAMA_BASE_URL",""),
            all_env.get("OLLAMA_MODEL",""),       all_env.get("AI_PROVIDER","auto"),
        )
        from packages.ai.provider import is_ai_available as _chk, get_active_provider as _prov
        if _chk():
            lbl_status.setText(f"\u2713 Đang dùng: {_prov()}")
            lbl_status.setStyleSheet(
                f"color:{badge_ok_txt};background:{badge_ok};"
                "border-radius:8px;padding:5px 14px;font-size:12px;font-weight:700;")
        else:
            lbl_status.setText("\u26a0 Chưa cấu hình AI")
            lbl_status.setStyleSheet(
                f"color:{badge_warn_txt};background:{badge_warn};"
                "border-radius:8px;padding:5px 14px;font-size:12px;font-weight:700;")
        orig = btn_save.text()
        btn_save.setText("\u2705  Đã lưu!")
        QTimer.singleShot(1500, lambda: btn_save.setText(orig))

    btn_reset.clicked.connect(_reset_all)
    btn_cancel.clicked.connect(dlg.reject)
    btn_save.clicked.connect(_save)
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_reset)
    btn_row.addStretch()
    btn_row.addWidget(btn_save)
    right_lay.addLayout(btn_row)

    main_layout.addWidget(right_w, 1)
    dlg.exec()


def _current_pdf_path(window) -> str:
    state = window._state_or_global() if hasattr(window, "_state_or_global") else {}
    path = state.get("source_path") or state.get("display_path")
    return path or getattr(window, "current_path", "") or ""


def _current_history_identity_path(window) -> str:
    # Ưu tiên khóa GHI-MỘT-LẦN `chat_identity_path` (đặt lúc mở file, không luồng
    # reload/chú thích/sửa nào đụng tới). Trước đây dùng `display_path` — nhưng
    # nhiều luồng (pages._reload, reload_document...) ghi đè display_path sang
    # đường dẫn temp -> identity chat đổi -> lịch sử chat "biến mất" khi mở lại.
    state = window._state_or_global() if hasattr(window, "_state_or_global") else {}
    return (
        state.get("chat_identity_path")
        or state.get("display_path")
        or state.get("source_path")
        or getattr(window, "current_path", "")
        or ""
    )


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
    """Lưu API key và Ollama config vào file config (mã hóa API keys)."""
    try:
        from packages.platform import get_app_data_dir, load_secure_config, save_secure_config
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")

        data = load_secure_config(config_path) if os.path.exists(config_path) else {}

        # --- API keys (will be encrypted by save_secure_config) ---
        for key, val in [
            ("ANTHROPIC_API_KEY", anthropic_key),
            ("OPENAI_API_KEY", openai_key),
            ("GEMINI_API_KEY", gemini_key),
            ("GROQ_API_KEY", groq_key),
            ("OPENROUTER_API_KEY", openrouter_key),
            ("HF_API_KEY", hf_key),
        ]:
            if val:
                data[key] = val
            else:
                data.pop(key, None)

        # --- Non-sensitive config (stored as plain text) ---
        for key, val in [
            ("GROQ_MODEL", groq_model),
            ("GROQ_BASE_URL", groq_base),
            ("OPENROUTER_MODEL", openrouter_model),
            ("OPENROUTER_BASE_URL", openrouter_base),
            ("OPENROUTER_HTTP_REFERER", openrouter_ref),
            ("OPENROUTER_APP_NAME", openrouter_name),
            ("HF_MODEL", hf_model),
        ]:
            if val:
                data[key] = val
            else:
                data.pop(key, None)

        if ollama_url:
            data["OLLAMA_BASE_URL"] = ollama_url
        else:
            data.pop("OLLAMA_BASE_URL", None)
        if ollama_model:
            data["OLLAMA_MODEL"] = ollama_model
        else:
            data.pop("OLLAMA_MODEL", None)

        data["AI_PROVIDER"] = ai_provider or "auto"

        save_secure_config(config_path, data)
    except Exception:
        pass


def load_ai_config():
    """Tải API key và Ollama config từ file config (gọi lúc khởi động app)."""
    try:
        from packages.platform import get_app_data_dir, load_secure_config
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")
        if not os.path.exists(config_path):
            return
        data = load_secure_config(config_path)
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
