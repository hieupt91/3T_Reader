import os
import sys
import gc
import json

from packages.qt_compat.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPageSetupDialog
from packages.qt_compat.QtWidgets import (
    QMainWindow,
    QToolBar,
    QLabel,
    QSpinBox,
    QHBoxLayout,
    QToolButton,
    QWidget,
    QVBoxLayout,
    QMenu,
    QSizePolicy,
    QMessageBox,
    QDialog,
    QColorDialog,
    QFrame,
    QPushButton,
)
from packages.qt_compat.QtGui import QAction, QKeySequence, QCloseEvent, QImage, QPainter, QColor, QPageLayout
from packages.qt_compat.QtCore import Qt, QSize, QPoint, QTimer, QThread, QRect, QObject, pyqtSignal, pyqtSlot
from packages.qt_compat.QtWebEngineWidgets import QWebEngineView
from app.pdf_viewer import PDFViewerWidget

from app.actions.file import open_file, show_recent_menu, _populate_recent_menu
from app.actions.document import search_text, search_next, search_previous, show_file_info, execute_search
from app.actions.edit import (
    create_new_pdf,
    delete_inserted_object,
    insert_image_to_pdf,
    insert_text_to_pdf,
    redact_area,
    save_edits,
    save_edits_as,
    save_edits_quiet,
    select_inserted_object,
    undo_last_edit,
    edit_existing_text,
)
from app.actions.free_draw import draw_on_pdf
from app.actions.navigate import prev_page, next_page, jump_to_page
from app.actions.zoom import zoom_in, zoom_out, apply_zoom, zoom_fit
from app.actions.brightness import brightness_up, brightness_down, apply_brightness_to_webview
from styles.theme import toggle_theme, is_dark
from app.actions.annotate import (
    highlight_text, rotate_page_cw, rotate_page_ccw,
    delete_current_page,
    underline_text, strikeout_text, add_comment, enable_note_tools,
    has_pending_annotations,
)
from app.actions.pages import merge_pdfs_action, split_pdf_action
from app.actions.sign import (
    check_token,
    create_signature_field,
    sign_document,
    sign_document_batch,
    sign_handwritten,
    sign_with_pfx,
    verify_signed_document,
)
from app.actions.ai_actions import (
    open_translate_dialog, open_summarize_dialog,
    open_chat_dialog, open_ai_settings, open_search_dialog,
)
from app.actions.export import export_pdf_to_word, export_pdf_to_excel
from app.actions.document_ops import (
    add_watermark, remove_watermark, set_pdf_password, remove_pdf_password,
    compress_pdf, export_pages_to_images,
    export_pdf_to_text, add_page_numbers, remove_page_numbers,
)
from app.sidebar import ThumbnailSidebar, BookmarkSidebar
from app.annotation_sidebar import AnnotationSidebar
from app.menu_builder import build_menubar
from app.ribbon_builder import RibbonBuilder
from app.search_panel import (
    build_search_panel,
    hide_search_panel,
    reposition_search_panel,
    search_from_panel,
    show_search_panel,
)
from app.status_bar_builder import build_status_bar
from app.tab_manager import TabManager
from app.updater import UpdateCheckWorker
from app.icon_utils import svg_icon, app_logo_icon
from app.dialogs import show_warning, show_info
from app.config import WINDOW_TITLE
from app.language_manager import (
    available_languages,
    download_language_pack,
    get_selected_language,
    get_translation,
    set_selected_language,
)
from app.platform_ui import shortcut_label, use_native_menubar, fullscreen_shortcut_hint
from packages.platform.recent import load_recent, clear_recent
from packages.pdf_engine import get_pdf_engine

# CSS overrides loaded from assets/css/pdfjs_overrides.css
from pathlib import Path as _Path
_PDFJS_OVERRIDES_CSS_PATH = _Path(__file__).resolve().parent.parent / "assets" / "css" / "pdfjs_overrides.css"
_PDFJS_OVERRIDES_CSS = _PDFJS_OVERRIDES_CSS_PATH.read_text(encoding="utf-8")
_VIEWER_DEBUG_DIR = _Path(__file__).resolve().parent.parent / "debug" / "viewer_dumps"
PDFJS_HIDE_TOOLBAR_CSS = f"""
var style = document.createElement('style');
style.innerHTML = `{_PDFJS_OVERRIDES_CSS}`;
document.head.appendChild(style);
"""
_PDFJS_VIEWER_DIAGNOSTIC_JS = r"""
(function () {
    try {
    function pick(el) {
        if (!el) return null;
        var cs = window.getComputedStyle ? window.getComputedStyle(el) : null;
        var rect = null;
        try {
            var r = el.getBoundingClientRect();
            rect = {
                left: Math.round(r.left),
                top: Math.round(r.top),
                width: Math.round(r.width),
                height: Math.round(r.height)
            };
        } catch (_) {}
        var children = [];
        try {
            children = Array.prototype.slice.call(el.children || [], 0, 5).map(function (child) {
                return {
                    tag: child.tagName || "",
                    cls: child.className || "",
                    hidden: !!child.hidden
                };
            });
        } catch (_) {}
        return {
            tag: el.tagName || "",
            cls: el.className || "",
            id: el.id || "",
            hidden: !!el.hidden,
            attrStyle: el.getAttribute ? (el.getAttribute("style") || "") : "",
            text: (el.textContent || "").slice(0, 120),
            rect: rect,
            computed: cs ? {
                display: cs.display,
                visibility: cs.visibility,
                opacity: cs.opacity,
                pointerEvents: cs.pointerEvents,
                backgroundColor: cs.backgroundColor,
                border: cs.border,
                color: cs.color
            } : null,
            children: children
        };
    }

    var styleTags = Array.prototype.slice.call(document.querySelectorAll("style"));
    var styleSummary = styleTags
        .filter(function (tag) {
            var text = tag.textContent || "";
            return text.indexOf("signatureWidgetAnnotation") >= 0
                || tag.hasAttribute("data-3t-pdfjs-overrides");
        })
        .map(function (tag) {
            var text = tag.textContent || "";
            return {
                attrs: tag.getAttributeNames ? tag.getAttributeNames().reduce(function (acc, name) {
                    acc[name] = tag.getAttribute(name);
                    return acc;
                }, {}) : {},
                sample: text.slice(0, 500)
            };
        });

    var widgets = Array.prototype.slice.call(document.querySelectorAll(".signatureWidgetAnnotation"));
    var annotationSections = Array.prototype.slice.call(document.querySelectorAll(".annotationLayer section"));
    var pageCanvases = Array.prototype.slice.call(document.querySelectorAll(".page canvas"));
    var app = window.PDFViewerApplication || null;
    var pagesOverview = [];
    try {
        var pages = document.querySelectorAll(".page[data-page-number]");
        pagesOverview = Array.prototype.slice.call(pages, 0, 8).map(function (page) {
            return {
                page: page.getAttribute("data-page-number") || "",
                annots: page.querySelectorAll(".annotationLayer section").length,
                sigs: page.querySelectorAll(".signatureWidgetAnnotation").length,
                canvases: page.querySelectorAll("canvas").length
            };
        });
    } catch (_) {}

    return JSON.stringify({
        href: String(location.href || ""),
        title: document.title || "",
        styleTagCount: styleTags.length,
        relevantStyles: styleSummary,
        widgetCount: widgets.length,
        annotationSectionCount: annotationSections.length,
        pageCanvasCount: pageCanvases.length,
        firstPage: pick(document.querySelector(".page[data-page-number='1']")),
        firstWidget: pick(widgets[0] || null),
        firstWidgetInput: pick(widgets[0] ? widgets[0].querySelector("input, textarea, select, button, canvas, div, img") : null),
        pagesOverview: pagesOverview,
        pdfjs: app ? {
            page: app.pdfViewer && app.pdfViewer.currentPageNumber || 0,
            pagesCount: app.pagesCount || 0,
            annotationMode: app.pdfViewer && app.pdfViewer.annotationMode || null
        } : null
    });
    } catch (error) {
        return JSON.stringify({
            error: String(error && error.stack || error || "unknown"),
            href: String(location.href || ""),
            readyState: document.readyState || ""
        });
    }
})()
"""


# Icon colors are centralized in styles/icon_colors.py
from styles.icon_colors import get_icon_color as _get_icon_color

AI_SUMMARIZE_SHORTCUT = "Ctrl+Alt+S"


class _TokenPresenceWorker(QObject):
    result = pyqtSignal(bool)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    @pyqtSlot()
    def run(self):
        try:
            from packages.signing import get_signing_provider

            provider = get_signing_provider()
            checker = getattr(provider, "is_token_present", None)
            token_found = bool(checker()) if callable(checker) else provider.detect_driver() is not None
            self.result.emit(token_found)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class PDFReaderApp(QMainWindow):
    external_files_requested = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._language_code = get_selected_language()
        self.setWindowIcon(app_logo_icon(256))
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 800)
        self.is_fullscreen = False
        self._tab_context_index = -1
        self._usb_token_detected = False
        self._closing = False
        self._highlight_color_pdf = [1.0, 1.0, 0.0]
        self._highlight_color_overlay = "rgba(250,204,21,.35)"

        self._brightness = 100
        self._action_icons: dict = {}   # {QAction: svg_filename} for theme refresh
        self._tabs_data = {}
        self._session_temp_paths = set()
        self._update_check_thread = None
        self._update_check_worker = None
        self._pending_manual_update_check = False
        self._token_monitor_timer = None
        self._token_check_thread = None
        self._token_check_worker = None
        self._token_monitor_suspended = False
        self._global_state = {
            "source_path": None,
            "display_path": None,
            "web_view": None,
            "search_query": "",
            "temp_path": None,
        }
        self._prune_stale_temp_files()

        self.setAcceptDrops(True)
        self.external_files_requested.connect(self._open_external_files_on_ui_thread)

        self._build_tab_host()

        self.sidebar = ThumbnailSidebar(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)

        self.toc_sidebar = BookmarkSidebar(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.toc_sidebar)
        self.toc_sidebar.hide()

        self.annotation_sidebar = AnnotationSidebar(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.annotation_sidebar)
        self.annotation_sidebar.hide()

        self._build_search_panel()
        self._build_toolbar()
        self._build_menubar()
        self._build_statusbar()
        self._connect_signals()
        self._apply_language_texts()
        self._start_token_monitor()
        self._apply_toolbar_prefs()
        QTimer.singleShot(15_000, self._auto_check_update)
        # Khôi phục AI API key đã lưu (nếu có) nhưng defer lại 500ms để không block UI khi khởi động
        try:
            from app.actions.ai_actions import load_ai_config
            QTimer.singleShot(500, load_ai_config)
        except Exception:
            pass

    def _t(self, key: str, fallback: str) -> str:
        return get_translation(self._language_code, key, fallback)

    def _check_license(self):
        from app.license_dialog import check_license_on_startup
        if not check_license_on_startup(self):
            from packages.qt_compat.QtWidgets import QApplication
            QApplication.quit()

    def _prune_stale_temp_files(self):
        try:
            from app.actions._pdf_save import collect_active_pdf_temp_paths, prune_stale_app_temp_files

            prune_stale_app_temp_files(active_paths=collect_active_pdf_temp_paths(self))
        except Exception:
            pass

    def _open_license_dialog(self):
        from app.license_dialog import open_license_dialog
        open_license_dialog(self)

    def _ocr_current_page(self):
        from app.actions.ocr import ocr_current_page
        ocr_current_page(self)

    def _ocr_full_document(self):
        from app.actions.ocr import ocr_full_document
        ocr_full_document(self)

    # ------------------------------------------------------------------ #
    #  Tab host                                                            #
    # ------------------------------------------------------------------ #

    def _build_tab_host(self):
        self.tab_widget = TabManager(self, on_context_menu=self._show_tab_context_menu)
        self.setCentralWidget(self.tab_widget)
        self._show_welcome_tab()

    def _update_tab_bar_visibility(self):
        tab_bar = self.tab_widget.tabBar()
        show_tabs = self._active_state() is not None or self.tab_widget.count() > 1
        tab_bar.setVisible(show_tabs)

    def _show_welcome_tab(self):
        from app.welcome_widget import WelcomeWidget
        from app.actions.file import open_file, show_recent_menu
        self._welcome_tab = WelcomeWidget(
            on_open=lambda: open_file(self),
            on_new=lambda: create_new_pdf(self),
            on_recent=lambda: show_recent_menu(self),
            on_recent_file=lambda path: open_file(self, path),
        )
        idx = self.tab_widget.addTab(self._welcome_tab, "Trang chủ")
        self.tab_widget.tabBar().setTabButton(idx, self.tab_widget.tabBar().ButtonPosition.RightSide, None)
        self._update_tab_bar_visibility()
        # Ẩn sidebar khi ở trang chủ
        QTimer.singleShot(0, self._hide_sidebars_for_welcome)

    def _hide_sidebars_for_welcome(self):
        if hasattr(self, "sidebar"):
            self.sidebar.hide()
        if hasattr(self, "toc_sidebar"):
            self.toc_sidebar.hide()
        if hasattr(self, "annotation_sidebar"):
            self.annotation_sidebar.hide()

    def _remove_welcome_tab(self):
        if not hasattr(self, "_welcome_tab"):
            return
        idx = self.tab_widget.indexOf(self._welcome_tab)
        if idx >= 0:
            self.tab_widget.removeTab(idx)
        self._welcome_tab = None
        self._update_tab_bar_visibility()

    # ------------------------------------------------------------------ #
    #  State helpers                                                       #
    # ------------------------------------------------------------------ #

    def _active_state(self):
        index = self.tab_widget.currentIndex()
        if index < 0:
            return None
        tab = self.tab_widget.widget(index)
        return self._tabs_data.get(tab)

    def _state_or_global(self):
        state = self._active_state()
        return state if state is not None else self._global_state

    @property
    def viewer(self):
        state = self._active_state()
        return state["viewer"] if state else None

    @property
    def current_path(self):
        return self._state_or_global().get("source_path")

    @current_path.setter
    def current_path(self, value):
        self._state_or_global()["source_path"] = value

    @property
    def search_query(self):
        return self._state_or_global().get("search_query", "")

    @search_query.setter
    def search_query(self, value):
        self._state_or_global()["search_query"] = value or ""

    @property
    def web_view(self):
        return self._state_or_global().get("web_view")

    @web_view.setter
    def web_view(self, value):
        self._state_or_global()["web_view"] = value

    def get_display_path(self):
        return self._state_or_global().get("display_path") or self.current_path

    # ------------------------------------------------------------------ #
    #  Open document                                                       #
    # ------------------------------------------------------------------ #

    def open_document(self, source_path: str, *, display_path: str | None = None, temp_path: str | None = None) -> bool:
        if not source_path:
            return False

        tab    = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        viewer = PDFViewerWidget(preset="annotation")
        layout.addWidget(viewer)

        state = {
            "viewer":       viewer,
            "source_path":  source_path,
            "display_path": display_path or source_path,
            "web_view":     None,
            "search_query": "",
            "temp_path":    temp_path,
        }
        self._tabs_data[tab] = state

        self._remove_welcome_tab()

        title = os.path.basename(state["display_path"]) if state["display_path"] else "PDF"
        index = self.tab_widget.addTab(tab, title)
        self.tab_widget.setCurrentIndex(index)
        self._update_tab_bar_visibility()

        self._connect_viewer_signals(viewer)

        load_attempt = {"count": 0}

        def _load_viewer_once():
            if self.tab_widget.indexOf(tab) < 0:
                return
            load_attempt["count"] += 1
            try:
                viewer.load_pdf(source_path, zoom="100", pagemode="thumbs")
            except Exception as e:
                close_index = self.tab_widget.indexOf(tab)
                if close_index >= 0:
                    self._close_tab(close_index)
                show_warning(self, "Không thể mở tệp", str(e))
                return
            if load_attempt["count"] == 1:
                QTimer.singleShot(1200, _retry_if_viewer_blank)

        def _retry_if_viewer_blank():
            if self.tab_widget.indexOf(tab) < 0:
                return
            if getattr(viewer, "_path", "") != source_path:
                return
            if getattr(viewer, "_page_count", 0) > 0:
                return
            _load_viewer_once()

        QTimer.singleShot(0, _load_viewer_once)

        self.status.showMessage(f"Đã mở: {title}", 3000)
        try:
            from packages.audit import log_action, ACT_OPEN
            log_action(ACT_OPEN, source_path)
        except Exception:
            pass
        return True

    def open_external_files(self, paths: list[str]) -> None:
        self.external_files_requested.emit(paths)

    def _open_external_files_on_ui_thread(self, paths: list[str]) -> None:
        from app.actions.file import open_file

        for path in paths:
            if isinstance(path, str) and os.path.isfile(path):
                open_file(self, path)
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------ #
    #  Viewer signals                                                      #
    # ------------------------------------------------------------------ #

    def _connect_viewer_signals(self, viewer):
        viewer.pdf_loaded.connect(lambda meta, v=viewer: self._on_pdf_loaded(v, meta))
        viewer.page_changed.connect(lambda cur, total, v=viewer: self._on_page_changed(v, cur, total))
        viewer.zoom_changed.connect(lambda pct, v=viewer: self._on_zoom_changed(v, pct))
        viewer.error_occurred.connect(lambda msg: self.status.showMessage(f"Cảnh báo: {msg}", 5000))
        viewer.find_not_found.connect(lambda q: show_warning(self, "Không tìm thấy", f"Không tìm thấy kết quả cho: \"{q}\""))
        viewer.signature_clicked.connect(lambda page, field, v=viewer: self._on_signature_clicked(v, page, field))
        if hasattr(viewer, "context_menu_requested"):
            viewer.context_menu_requested.connect(lambda pos, v=viewer: self._show_pdf_context_menu(v, pos))
        page_ready = getattr(viewer, "page_ready", None)
        if hasattr(page_ready, "connect"):
            page_ready.connect(lambda v=viewer: self._on_page_ready(v))
        else:
            web_view = viewer.findChild(QWebEngineView)
            if web_view is not None:
                web_view.loadFinished.connect(lambda ok, v=viewer: self._on_page_ready(v) if ok else None)

    def _find_tab_by_viewer(self, viewer):
        for tab, state in self._tabs_data.items():
            if state.get("viewer") is viewer:
                return tab
        return None

    def _get_webview_for_viewer(self, viewer):
        tab = self._find_tab_by_viewer(viewer)
        if not tab:
            return None
        state = self._tabs_data.get(tab)
        if not state:
            return None
        if not state.get("web_view"):
            state["web_view"] = viewer.findChild(QWebEngineView)
        return state.get("web_view")

    def _get_webview(self):
        viewer = self.viewer
        if not viewer:
            return None
        wv = self._get_webview_for_viewer(viewer)
        if wv:
            self.web_view = wv
        return wv

    def _inject_css_for_viewer(self, viewer):
        wv = self._get_webview_for_viewer(viewer)
        if wv:
            wv.page().runJavaScript(PDFJS_HIDE_TOOLBAR_CSS)

    def _dump_viewer_diagnostics(self, viewer):
        wv = self._get_webview_for_viewer(viewer)
        if not wv:
            return

        def _write(payload):
            try:
                _VIEWER_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                state = self._active_state() if viewer is self.viewer else {}
                pdf_path = ""
                if isinstance(state, dict):
                    pdf_path = state.get("source_path") or state.get("display_path") or ""
                if not pdf_path:
                    pdf_path = getattr(viewer, "_path", "") or ""
                parsed_payload = payload
                if isinstance(payload, str):
                    try:
                        parsed_payload = json.loads(payload) if payload else {"raw": payload}
                    except Exception as exc:
                        parsed_payload = {
                            "raw": payload,
                            "parse_error": str(exc),
                        }
                target = _VIEWER_DEBUG_DIR / "latest_viewer_state.json"
                target.write_text(
                    json.dumps(
                        {
                            "pdf_path": pdf_path,
                            "payload": parsed_payload,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

        wv.page().runJavaScript(_PDFJS_VIEWER_DIAGNOSTIC_JS, _write)

    def _inject_css(self):
        viewer = self.viewer
        if viewer:
            self._inject_css_for_viewer(viewer)

    # ------------------------------------------------------------------ #
    #  Search panel                                                        #
    # ------------------------------------------------------------------ #

    def _build_search_panel(self):
        return build_search_panel(self)

    def _reposition_search_panel(self):
        return reposition_search_panel(self)

    def show_search_panel(self):
        return show_search_panel(self)

    def hide_search_panel(self):
        return hide_search_panel(self)

    def _search_from_panel(self, *, find_previous: bool, force_new: bool):
        return search_from_panel(self, find_previous=find_previous, force_new=force_new)

    # ------------------------------------------------------------------ #
    #  Toolbar                                                             #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self):
        return RibbonBuilder(self).build()

    def _build_toolbar_impl(self):
        # ── QToolBar chứa ribbon (không hiện widget riêng lẻ) ─────────────
        self.toolbar = QToolBar("Thanh công cụ")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setContentsMargins(0, 0, 0, 0)
        self._apply_toolbar_style()
        self.addToolBar(self.toolbar)

        def _ic(svg_file):
            return _get_icon_color(svg_file, dark=is_dark())

        def make(text, svg_file, tooltip, shortcut, slot):
            a = QAction(text, self)
            a.setIcon(svg_icon(svg_file, color=_ic(svg_file)))
            a.setToolTip(tooltip)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            self._action_icons[a] = svg_file
            return a

        # ── Tạo tất cả QAction (không add vào toolbar cũ) ────────────────
        self.act_open   = make("Mở tệp",    "folder_open.svg", f"Mở tệp ({shortcut_label('Ctrl+O')})",  "Ctrl+O",       lambda: open_file(self))
        self.act_recent = make("Gần đây",   "history.svg",      "Tệp gần đây",                           None,           lambda: show_recent_menu(self))
        self.act_save   = make("Lưu",       "save.svg",         f"Lưu ({shortcut_label('Ctrl+S')})",     "Ctrl+S",       lambda: save_edits(self))
        self.act_print  = make("In",        "print.svg",        f"In ({shortcut_label('Ctrl+P')})",      "Ctrl+P",       self.print_current_pdf)
        self.act_new_pdf         = make("PDF mới",    "file_plus.svg",       f"Tạo PDF mới ({shortcut_label('Ctrl+N')})",         "Ctrl+N",       lambda: create_new_pdf(self))
        self.act_save_as         = make("Lưu mới",   "save_as.svg",         f"Lưu thành file mới ({shortcut_label('Ctrl+Shift+S')})", "Ctrl+Shift+S", lambda: save_edits_as(self))

        self.act_prev   = make("Trang trước", "chevron_left.svg",  "Trang trước (←)",                   "Left",         lambda: prev_page(self))
        self.act_next   = make("Trang sau",   "chevron_right.svg", "Trang sau (→)",                      "Right",        lambda: next_page(self))
        self.act_zoom_in = make("Phóng to",   "zoom_in.svg",       f"Phóng to ({shortcut_label('Ctrl+=')})",  "Ctrl+=", lambda: zoom_in(self))
        self.act_zoom_in.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        self.act_zoom_in.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_zoom_out = make("Thu nhỏ",   "zoom_out.svg",      f"Thu nhỏ ({shortcut_label('Ctrl+-')})",   "Ctrl+-", lambda: zoom_out(self))
        self.act_zoom_out.setShortcuts([QKeySequence("Ctrl+-"), QKeySequence("Ctrl+_")])
        self.act_zoom_out.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_fit    = make("Vừa trang",   "fit_page.svg",      f"Vừa trang ({shortcut_label('Ctrl+0')})", "Ctrl+0", lambda: zoom_fit(self))

        self.act_highlight    = make("Tô sáng",   "highlight.svg",    f"Tô sáng ({shortcut_label('Ctrl+H')})", "Ctrl+H", lambda: highlight_text(self))
        self.act_highlight_color = make("Màu tô", "highlight.svg", f"Chọn màu tô sáng ({shortcut_label('Ctrl+Shift+H')})", "Ctrl+Shift+H", self._pick_highlight_color)
        self.act_highlight_color.setIcon(svg_icon("highlight.svg", color="#facc15"))
        self.act_insert_text  = make("Chèn chữ",  "insert_text.svg",  f"Chèn văn bản vào PDF ({shortcut_label('Ctrl+T')})",   "Ctrl+T",          lambda: insert_text_to_pdf(self))
        self.act_insert_image = make("Chèn ảnh",  "insert_image.svg", f"Chèn ảnh vào PDF ({shortcut_label('Ctrl+I')})",        "Ctrl+I",          lambda: insert_image_to_pdf(self))
        self.act_draw         = make("Vẽ tự do",  "pen.svg",          f"Vẽ tự do lên PDF ({shortcut_label('Ctrl+D')})",         "Ctrl+D",          lambda: draw_on_pdf(self))
        self.act_redact       = make("Xóa trắng", "redact.svg",       "Che/tẩy vùng nội dung",   None,          lambda: redact_area(self))
        self.act_edit_existing_text = make("Sửa text", "edit_object.svg", "Sửa text có sẵn trong PDF", None, lambda: edit_existing_text(self))
        self.act_delete_object= make("Xóa đối tượng",   "trash.svg",        "Xóa text/ảnh đã chèn",    None,          lambda: delete_inserted_object(self))
        self.act_select_inserted = make("Chọn & Xoay","edit_object.svg", "Chọn text/ảnh đã chèn → hiện nút ↻ Xoay, ✎ Sửa, × Xóa, ✥ Di chuyển", None,  lambda: select_inserted_object(self))
        self.act_undo         = make("Hoàn tác",  "undo.svg",         f"Hoàn tác ({shortcut_label('Ctrl+Z')})", "Ctrl+Z", lambda: undo_last_edit(self))

        self.act_toggle_sidebar_btn = make("Thumb", "sidebar.svg",   "Danh sách trang (Ctrl+\\)", "Ctrl+\\", self._toggle_sidebar)
        self.act_toggle_sidebar_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_toggle_toc_btn     = make("Mục lục","history.svg",  "Mục lục PDF (Ctrl+Alt+T)", "Ctrl+Alt+T", self._toggle_toc)
        self.act_toggle_toc_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self._action_icons[self.act_toggle_toc_btn] = "history.svg"
        self.act_toggle_annotations_btn = make("Chú thích", "sidebar_panel.svg", "Danh sách chú thích (Ctrl+Alt+A)", "Ctrl+Alt+A", self._toggle_annotations)
        self.act_toggle_annotations_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)

        self.act_theme_toggle = make("Giao diện","sun.svg", "Đổi chủ đề sáng/tối", None, self._toggle_theme)
        self.act_theme_toggle.setIcon(svg_icon("sun.svg", color="#f0c050"))
        self.act_fullscreen   = make("Toàn màn", "fullscreen.svg", f"Toàn màn hình (F11)", "F11", self.toggle_fullscreen)
        self.act_brightness_up   = make("Sáng hơn",  "brightness_up.svg",  f"Tăng độ sáng ({shortcut_label('Ctrl+Shift+=')})", "Ctrl+Shift+=", lambda: brightness_up(self))
        self.act_brightness_down = make("Tối hơn",   "brightness_down.svg", f"Giảm độ sáng ({shortcut_label('Ctrl+Shift+-')})", "Ctrl+Shift+-", lambda: brightness_down(self))
        self.act_check_token  = make("USB token", "usb.svg", "Kiểm tra USB ký số", None, lambda: check_token(self))
        self.act_sign         = make("Ký số",     "usb.svg", "Ký số tài liệu",     None, lambda: sign_document(self))
        self.act_sign_file    = make("Ký PFX",    "file_plus.svg",    "Ký bằng file PFX/P12", None, lambda: sign_with_pfx(self))
        self.act_signature_field = make("Ô ký",   "object_plus.svg",  "Tạo ô ký số trên PDF", None, lambda: create_signature_field(self))
        self.act_verify_signature = make("Kiểm tra", "signature_check.svg", "Kiểm tra tính pháp lý chữ ký số của PDF", None, lambda: verify_signed_document(self))
        
        self.act_tts = make("Đọc sách", "volume.svg", "Đọc văn bản thành tiếng (TTS)", None, lambda: __import__("app.actions.tts_dialog", fromlist=["open_tts_dialog"]).open_tts_dialog(self))

        # ── SpinBox trang & zoom ──────────────────────────────────────────
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(9999)
        self.page_spin.setFixedWidth(62)
        self.page_spin.setToolTip("Nhập số trang rồi Enter")
        self.page_spin.editingFinished.connect(lambda: jump_to_page(self))
        self.page_spin.setStyleSheet(
            "QSpinBox{background:#1C1C36;color:#E0E8FF;border:1px solid #3A3A60;"
            "border-radius:5px;padding:2px 4px;font-size:12px;}"
            "QSpinBox::up-button,QSpinBox::down-button{width:0;}"
        )

        self.total_label = QLabel(" / -")
        self.total_label.setStyleSheet("color:#7070A8;font-size:12px;padding-right:6px;")

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(25, 400)
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setFixedWidth(76)
        self.zoom_spin.setToolTip("Zoom — double-click để về 100%")
        self.zoom_spin.editingFinished.connect(lambda: apply_zoom(self))
        self.zoom_spin.installEventFilter(self)
        self.zoom_spin.setStyleSheet(
            "QSpinBox{background:#1C1C36;color:#E0E8FF;border:1px solid #3A3A60;"
            "border-radius:5px;padding:2px 4px;font-size:12px;}"
            "QSpinBox::up-button,QSpinBox::down-button{width:0;}"
        )

        # ── Xây dựng Ribbon ──────────────────────────────────────────────
        from app.ribbon_bar import RibbonBar, RibbonPanel, RibbonGroup, make_action_btn, make_ribbon_btn

        self.ribbon = RibbonBar(self)

        ic = lambda f: svg_icon(f, color=_ic(f))   # shorthand

        # ─── Tab 0: Tệp & Xem ────────────────────────────────────────────
        p0 = RibbonPanel()

        self.g_file = RibbonGroup("Tệp")
        self.g_file.add(make_action_btn(self.act_open,    "Mở"))
        self.g_file.add(make_action_btn(self.act_new_pdf, "Mới"))
        self.g_file.add(make_action_btn(self.act_recent,  "Gần đây"))
        self.g_file.add(make_action_btn(self.act_save,    "Lưu"))
        self.g_file.add(make_action_btn(self.act_save_as, "Lưu mới"))
        self.g_file.add(make_action_btn(self.act_print,   "In"))
        p0.add_group(self.g_file)

        self.g_nav = RibbonGroup("Điều hướng")
        self.g_nav.add(make_action_btn(self.act_prev, "Trước"))
        self.g_nav.add(self.page_spin)
        self.g_nav.add(self.total_label)
        self.g_nav.add(make_action_btn(self.act_next, "Sau"))
        p0.add_group(self.g_nav)

        self.g_zoom = RibbonGroup("Zoom")
        self.g_zoom.add(make_action_btn(self.act_zoom_in,  "Phóng to"))
        self.g_zoom.add(self.zoom_spin)
        self.g_zoom.add(make_action_btn(self.act_zoom_out, "Thu nhỏ"))
        self.g_zoom.add(make_action_btn(self.act_fit,      "Vừa trang"))
        p0.add_group(self.g_zoom)

        self.g_view = RibbonGroup("Giao diện")
        self.g_view.add(make_action_btn(self.act_toggle_sidebar_btn, "Thumb"))
        self.g_view.add(make_action_btn(self.act_toggle_toc_btn,     "Mục lục"))
        self.g_view.add(make_action_btn(self.act_theme_toggle,       "Chủ đề"))
        self.g_view.add(make_action_btn(self.act_fullscreen,         "Toàn màn"))
        self.g_view.add(make_action_btn(self.act_tts,                "Đọc sách"))

        self._lang_toolbar_button = QToolButton(self)
        self._lang_toolbar_button.setAutoRaise(True)
        self._lang_toolbar_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._lang_toolbar_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._lang_toolbar_button.setIcon(svg_icon("language.svg", size=28, color=_ic("language.svg")))
        self._lang_toolbar_button.setText(self._t("menu.language", "Ngôn ngữ"))
        self._lang_toolbar_button.setToolTip(self._t("menu.language", "Ngôn ngữ"))
        lang_menu = QMenu(self._lang_toolbar_button)
        self._lang_toolbar_button.setMenu(lang_menu)
        self.act_lang_vi_tb = lang_menu.addAction(self._t("lang.vietnamese", "Tiếng Việt"))
        self.act_lang_en_tb = lang_menu.addAction(self._t("lang.english", "English"))
        self.act_lang_fr_tb = lang_menu.addAction(self._t("lang.french", "Français"))
        self.act_lang_zh_tb = lang_menu.addAction(self._t("lang.chinese", "中文"))
        self.act_lang_ko_tb = lang_menu.addAction(self._t("lang.korean", "한국어"))
        self.act_lang_th_tb = lang_menu.addAction(self._t("lang.thai", "ไทย"))
        lang_menu.addSeparator()
        self.act_lang_refresh_tb = lang_menu.addAction(self._t("lang.download", "Tải gói ngôn ngữ..."))
        self.act_lang_vi_tb.triggered.connect(lambda: self._set_language("vi"))
        self.act_lang_en_tb.triggered.connect(lambda: self._set_language("en"))
        self.act_lang_fr_tb.triggered.connect(lambda: self._set_language("fr"))
        self.act_lang_zh_tb.triggered.connect(lambda: self._set_language("zh"))
        self.act_lang_ko_tb.triggered.connect(lambda: self._set_language("ko"))
        self.act_lang_th_tb.triggered.connect(lambda: self._set_language("th"))
        self.act_lang_refresh_tb.triggered.connect(lambda: self._refresh_language_pack())
        self._ensure_action_tooltips(lang_menu)
        self.g_view.add(self._lang_toolbar_button)
        p0.add_group(self.g_view, add_sep=False)
        p0.add_stretch()

        self.ribbon.add_tab(self._t("tab.file_view", "Tệp & Xem"), p0)

        # ─── Tab 1: Chú thích ─────────────────────────────────────────────
        p1 = RibbonPanel()

        self.g_mark = RibbonGroup("Đánh dấu")
        _highlight_btn = make_action_btn(self.act_highlight, "Tô sáng")
        _highlight_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _highlight_btn.customContextMenuRequested.connect(lambda: self._show_highlight_context_menu())
        self.g_mark.add(_highlight_btn)
        self.g_mark.add(make_action_btn(self.act_highlight_color, "Màu tô"))
        self.act_underline = make("Gạch dưới", "underline.svg", f"Gạch dưới văn bản ({shortcut_label('Ctrl+U')})", "Ctrl+U", lambda: underline_text(self))
        self.act_underline.setIcon(svg_icon("underline.svg", color="#2563eb"))
        self._action_icons[self.act_underline] = "underline.svg"
        self.g_mark.add(make_action_btn(self.act_underline, "Gạch dưới"))
        self.act_strikeout = make("Gạch ngang", "strikeout.svg", f"Gạch ngang văn bản ({shortcut_label('Ctrl+Shift+X')})", "Ctrl+Shift+X", lambda: strikeout_text(self))
        self.act_strikeout.setIcon(svg_icon("strikeout.svg", color="#dc2626"))
        self._action_icons[self.act_strikeout] = "strikeout.svg"
        self.g_mark.add(make_action_btn(self.act_strikeout, "Gạch ngang"))
        self._act_comment = make("Ghi chú", "insert_text.svg", "Thêm ghi chú", None, lambda: add_comment(self))
        self.g_mark.add(make_action_btn(self._act_comment, "Ghi chú"))
        p1.add_group(self.g_mark)

        self.g_edit = RibbonGroup("Chỉnh sửa")
        self.g_edit.add(make_action_btn(self.act_insert_text,  "Chèn chữ"))
        self.g_edit.add(make_action_btn(self.act_insert_image, "Chèn ảnh"))
        self.g_edit.add(make_action_btn(self.act_draw,         "Vẽ tự do"))
        self.g_edit.add(make_action_btn(self.act_redact,       "Xóa trắng"))
        self.g_edit.add(make_action_btn(self.act_edit_existing_text, "Sửa text gốc"))
        self.g_edit.add(make_action_btn(self.act_select_inserted, "Chọn & Xoay"))
        self.g_edit.add(make_action_btn(self.act_delete_object,"Xóa đối tượng"))
        p1.add_group(self.g_edit)

        self.g_undo = RibbonGroup("Lịch sử")
        self.g_undo.add(make_action_btn(self.act_undo, "Hoàn tác"))
        p1.add_group(self.g_undo, add_sep=False)
        p1.add_stretch()

        self.ribbon.add_tab(self._t("tab.annotate", "Chú thích"), p1)

        # ─── Tab 2: Trang ─────────────────────────────────────────────────
        p2 = RibbonPanel()

        self.g_rot = RibbonGroup("Xoay / Xóa")
        self._act_rcw = make("Xoay phải", "rotate_cw.svg",  "Xoay phải 90°", None, lambda: rotate_page_cw(self))
        self._act_rccw = make("Xoay trái", "rotate_ccw.svg", "Xoay trái 90°", None, lambda: rotate_page_ccw(self))
        self._act_del = make("Xóa trang", "trash.svg", "Xóa trang hiện tại", None, lambda: delete_current_page(self))
        self.g_rot.add(make_action_btn(self._act_rcw,  "Xoay phải"))
        self.g_rot.add(make_action_btn(self._act_rccw, "Xoay trái"))
        self.g_rot.add(make_action_btn(self._act_del,  "Xóa trang"))
        p2.add_group(self.g_rot)

        self.g_org = RibbonGroup("Tổ chức")
        self._act_merge = make("Ghép PDF",   "folder_open.svg", "Ghép PDF vào cuối", None, lambda: merge_pdfs_action(self))
        self._act_extract = make("Tách PDF", "save.svg",        "Tách tài liệu",   None, lambda: split_pdf_action(self))
        self._act_pgnum = make("Số trang",   "insert_text.svg", "Thêm số trang",      None, lambda: add_page_numbers(self))
        self._act_rmpgnum = make("Xóa số trang", "trash.svg", "Xóa số trang đã thêm", None, lambda: remove_page_numbers(self))
        self.g_org.add(make_action_btn(self._act_merge,   "Ghép PDF"))
        self.g_org.add(make_action_btn(self._act_extract, "Tách PDF"))
        self.g_org.add(make_action_btn(self._act_pgnum,   "Số trang"))
        self.g_org.add(make_action_btn(self._act_rmpgnum, "Xóa số trang"))
        p2.add_group(self.g_org, add_sep=False)
        p2.add_stretch()

        self.ribbon.add_tab(self._t("tab.page", "Trang"), p2)

        # ─── Tab 3: Bảo mật & Xuất ────────────────────────────────────────
        p3 = RibbonPanel()

        self.g_sec = RibbonGroup("Bảo mật")
        self._act_wm = make("Watermark",   "pen.svg",      "Thêm watermark",     None, lambda: add_watermark(self))
        self._act_rmwm = make("Xóa watermark","trash.svg",   "Xóa watermark vừa thêm", None, lambda: remove_watermark(self))
        self._act_setpw = make("Đặt mật khẩu","save.svg",     "Đặt mật khẩu PDF",  None, lambda: set_pdf_password(self))
        self._act_rmpw = make("Xóa mật khẩu","trash.svg",    "Xóa mật khẩu PDF",  None, lambda: remove_pdf_password(self))
        self._act_comp = make("Nén PDF",     "save.svg",     "Nén / tối ưu PDF",   None, lambda: compress_pdf(self))
        self.g_sec.add(make_action_btn(self._act_wm,    "Watermark"))
        self.g_sec.add(make_action_btn(self._act_rmwm,  "Xóa watermark"))
        self.g_sec.add(make_action_btn(self._act_setpw, "Đặt mật khẩu"))
        self.g_sec.add(make_action_btn(self._act_rmpw,  "Xóa mật khẩu"))
        self.g_sec.add(make_action_btn(self._act_comp,  "Nén PDF"))
        p3.add_group(self.g_sec)

        self.g_exp = RibbonGroup("Xuất")
        self._act_word = make("Word",   "save.svg", "Xuất ra Word (.docx)", None, lambda: export_pdf_to_word(self))
        self._act_xl = make("Excel",  "save.svg", "Xuất ra Excel (.xlsx)",None, lambda: export_pdf_to_excel(self))
        self._act_img = make("Ảnh",   "save.svg",  "Xuất trang ra ảnh",    None, lambda: export_pages_to_images(self))
        self._act_txt = make("Văn bản","save.svg", "Xuất văn bản (.txt)",  None, lambda: export_pdf_to_text(self))
        self.g_exp.add(make_action_btn(self._act_word, "Word"))
        self.g_exp.add(make_action_btn(self._act_xl,   "Excel"))
        self.g_exp.add(make_action_btn(self._act_img,  "Ảnh"))
        self.g_exp.add(make_action_btn(self._act_txt,  "Văn bản"))
        p3.add_group(self.g_exp, add_sep=False)
        p3.add_stretch()

        self.ribbon.add_tab(self._t("tab.security_export", "Bảo mật & Xuất"), p3)

        # ─── Tab 4: OCR & AI ──────────────────────────────────────────────
        p4 = RibbonPanel()

        self.g_ocr = RibbonGroup("OCR")
        from app.actions.ocr import ocr_current_page, ocr_full_document
        self._act_ocr1 = make("OCR trang",    "zoom_in.svg",  "OCR trang hiện tại",  None, lambda: ocr_current_page(self))
        self._act_ocr2 = make("OCR tài liệu", "zoom_in.svg",  "OCR toàn bộ tài liệu",None, lambda: ocr_full_document(self))
        self.g_ocr.add(make_action_btn(self._act_ocr1, "OCR trang"))
        self.g_ocr.add(make_action_btn(self._act_ocr2, "OCR toàn bộ"))
        p4.add_group(self.g_ocr)

        self.g_ai = RibbonGroup("AI")
        self._act_chat = make("Chat PDF",    "pen.svg",          "Chat với PDF (Ctrl+Shift+C)", "Ctrl+Shift+C", lambda: open_chat_dialog(self))
        self._act_sum = make("Tóm tắt",     "insert_text.svg",  f"Tóm tắt tài liệu ({shortcut_label(AI_SUMMARIZE_SHORTCUT)})", AI_SUMMARIZE_SHORTCUT, lambda: open_summarize_dialog(self))
        self._act_trans = make("Dịch",        "sidebar.svg",      "Dịch trang hiện tại",         "Ctrl+Shift+T", lambda: open_translate_dialog(self))
        self._act_srch = make("Tìm nghĩa",   "zoom_in.svg",      "Tìm kiếm theo nghĩa",         "Ctrl+Shift+F", lambda: open_search_dialog(self))
        self._act_aiset = make("Cài đặt AI",  "save.svg",         "Cài đặt AI (API Key)",         None,           lambda: open_ai_settings(self))
        self.g_ai.add(make_action_btn(self._act_chat,  "Chat PDF"))
        self.g_ai.add(make_action_btn(self._act_sum,   "Tóm tắt"))
        self.g_ai.add(make_action_btn(self._act_trans, "Dịch"))
        self.g_ai.add(make_action_btn(self._act_srch,  "Tìm nghĩa"))
        self.g_ai.add(make_action_btn(self._act_aiset, "AI Key"))
        p4.add_group(self.g_ai, add_sep=False)
        
        self.g_tts = RibbonGroup("Đọc Sách")
        self.g_tts.add(make_action_btn(self.act_tts, "Đọc sách"))
        p4.add_group(self.g_tts, add_sep=False)
        
        p4.add_stretch()

        self.ribbon.add_tab(self._t("tab.ocr_ai", "OCR & AI"), p4)

        # ─── Tab 5: Ký số ─────────────────────────────────────────────────
        p5 = RibbonPanel()

        self.g_sign = RibbonGroup("Chữ ký số")
        self._act_token = make("USB token",  "usb.svg",  "Kiểm tra USB ký số",  None, lambda: check_token(self))
        self._act_sign2 = make("Ký số",      "usb.svg",  "Ký số tài liệu",      None, lambda: sign_document(self))
        self._act_sign_settings = make("Cài đặt", "settings.svg", "Cài đặt Ký số & TSA", None, lambda: self.open_signing_settings())
        self._act_sign_batch = make("Ký lô", "documents.svg", "Ký số hàng loạt nhiều file", None, lambda: sign_document_batch(self))
        self._act_sign3 = make("Ký PFX",     "file_plus.svg",    "Ký bằng file PFX/P12", None, lambda: sign_with_pfx(self))
        self._act_field = make("Ô ký",       "object_plus.svg",  "Tạo ô ký số trên PDF", None, lambda: create_signature_field(self))
        self._act_handw = make("Ký tay/dấu", "pen.svg",  "Chèn chữ ký tay, mẫu chữ ký hoặc con dấu PNG", None, lambda: sign_handwritten(self))
        self.g_sign.add(make_action_btn(self._act_token, "Kiểm tra USB"))
        self.g_sign.add(make_action_btn(self._act_sign2, "Ký số"))
        self.g_sign.add(make_action_btn(self._act_sign_settings, "Cài đặt"))
        self.g_sign.add(make_action_btn(self._act_sign3, "Ký PFX"))
        self.g_sign.add(make_action_btn(self._act_sign_batch, "Ký lô"))
        self.g_sign.add(make_action_btn(self._act_field, "Ô ký"))
        self.g_sign.add(make_action_btn(self._act_handw, "Ký tay/dấu"))
        p5.add_group(self.g_sign, add_sep=False)

        self.g_verify = RibbonGroup("Kiểm tra")
        self.g_verify.add(make_action_btn(self.act_verify_signature, "Kiểm tra"))
        p5.add_group(self.g_verify, add_sep=False)
        p5.add_stretch()

        # Sync với self.act_check_token / self.act_sign (dùng trong menu)
        self.act_check_token = self._act_token
        self.act_sign        = self._act_sign2
        self.act_sign_file   = self._act_sign3
        self.act_signature_field = self._act_field

        self.ribbon.add_tab(self._t("tab.sign", "Ký số"), p5)

        # ── Thêm ribbon vào toolbar ───────────────────────────────────────
        self.ribbon.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toolbar.setMinimumHeight(self.ribbon.EXPANDED_H)
        self.toolbar.setMaximumHeight(self.ribbon.EXPANDED_H)
        self.toolbar.addWidget(self.ribbon)
        # Áp dụng đúng theme ngay từ đầu
        self.ribbon.set_theme(is_dark())

        # Cập nhật chiều cao toolbar khi ribbon thu/mở
        def _on_ribbon_collapse(collapsed: bool):
            h = self.ribbon.TABROW_H if collapsed else self.ribbon.EXPANDED_H
            self.toolbar.setMinimumHeight(h)
            self.toolbar.setMaximumHeight(h)
        self.ribbon.collapsed_changed.connect(_on_ribbon_collapse)

    # ------------------------------------------------------------------ #
    #  Print — QPrintDialog + PDF engine, KHÔNG dùng ShellExecute         #
    # ------------------------------------------------------------------ #

    def print_current_pdf(self):
        """Open a PDF.js preview before printing."""
        state = self._active_state()
        if not state:
            show_warning(self, "Chưa mở tệp", "Vui lòng mở tệp PDF trước khi in.")
            return

        pdf_path = state.get("source_path")
        if not pdf_path or not os.path.exists(pdf_path):
            show_warning(self, "Lỗi", "Không tìm thấy tệp PDF.")
            return

        self._open_pdfjs_print_preview(pdf_path)

    def _current_viewer_page(self) -> int:
        viewer = getattr(self, "viewer", None)
        try:
            if viewer and hasattr(viewer, "get_current_page"):
                return max(1, int(viewer.get_current_page() or 1))
            if viewer and hasattr(viewer, "_current_page"):
                return max(1, int(getattr(viewer, "_current_page", 1) or 1))
        except Exception:
            pass
        return 1

    def _configured_pdf_printer(self, pdf_path: str, *, current_page: int | None = None) -> QPrinter:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        try:
            printer.setResolution(600)
        except Exception:
            pass
        try:
            pdf = get_pdf_engine().open(pdf_path)
            try:
                page_w_pt, page_h_pt = pdf.page_size(current_page or self._current_viewer_page())
                printer.setPageOrientation(self._page_orientation_for_pdf_size(page_w_pt, page_h_pt))
            finally:
                pdf.close()
        except Exception:
            pass
        return printer

    def _open_pdfjs_print_preview(self, pdf_path: str):
        current_page = self._current_viewer_page()
        dialog = QDialog(self)
        dialog.setWindowTitle("Xem trước khi in")
        dialog.resize(1120, 780)
        dialog.setMinimumSize(900, 620)

        preview_viewer = PDFViewerWidget(parent=dialog)
        preview_viewer.load_pdf(pdf_path, zoom="page-width", page=current_page)

        # ── Style theo theme sáng/tối ─────────────────────────────────────
        _dark = is_dark()
        if _dark:
            _TOOLBAR_BG  = "#16163a"
            _TOOLBAR_BDR = "#2e2e5a"
            _BTN_HOVER   = "#252552"
            _BTN_PRESSED = "#1e1e4a"
            _BTN_BORDER  = "#3a3a70"
            _BTN_CHECK   = "#1e1e60"
            _BTN_CHECK_B = "#5b7cfa"
            _BTN_CHECK_T = "#9ab8ff"
            _BTN_TXT     = "#b0b8e0"
            _SPIN_BG     = "#1C1C36"
            _SPIN_FG     = "#E0E8FF"
            _SPIN_BDR    = "#3A3A60"
            _SEP_COL     = "#2e2e5a"
        else:
            _TOOLBAR_BG  = "#f4f6fb"
            _TOOLBAR_BDR = "#d0d5e8"
            _BTN_HOVER   = "#e4e8f8"
            _BTN_PRESSED = "#d4d9f0"
            _BTN_BORDER  = "#b8bfe0"
            _BTN_CHECK   = "#dce6ff"
            _BTN_CHECK_B = "#4a6ef5"
            _BTN_CHECK_T = "#2a4ad0"
            _BTN_TXT     = "#3a3a5a"
            _SPIN_BG     = "#ffffff"
            _SPIN_FG     = "#1a1a3a"
            _SPIN_BDR    = "#b8bfe0"
            _SEP_COL     = "#d0d5e8"

        _btn_ss = (
            "QToolButton{"
            "  border:1px solid transparent; border-radius:6px;"
            "  background:" + _TOOLBAR_BG + "; padding:4px 2px 2px 2px;"
            "  font-size:10px; color:" + _BTN_TXT + ";"
            "}"
            "QToolButton:hover{background:" + _BTN_HOVER + ";border-color:" + _BTN_BORDER + ";}"
            "QToolButton:pressed{background:" + _BTN_PRESSED + ";border-color:" + _BTN_BORDER + ";}"
            "QToolButton:checked{"
            "  background:" + _BTN_CHECK + "; border:1px solid " + _BTN_CHECK_B + "; color:" + _BTN_CHECK_T + ";"
            "}"
        )
        _spin_ss = (
            "QSpinBox{background:" + _SPIN_BG + ";color:" + _SPIN_FG + ";"
            "  border:1px solid " + _SPIN_BDR + ";border-radius:5px;"
            "  padding:2px 4px;font-size:12px;}"
            "QSpinBox::up-button,QSpinBox::down-button{width:0;}"
        )

        def _make_btn(
            icon_name: str,
            label: str,
            tooltip: str,
            *,
            icon_color: str = "#8b91c8",
            icon_sz: int = 22,
            w: int = 52,
            h: int = 48,
            checkable: bool = False,
        ) -> QToolButton:
            btn = QToolButton(dialog)
            btn.setAutoRaise(True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIcon(svg_icon(icon_name, size=icon_sz, color=icon_color))
            btn.setIconSize(QSize(icon_sz, icon_sz))
            btn.setText(label)
            btn.setToolTip(tooltip)
            btn.setFixedSize(w, h)
            btn.setCheckable(checkable)
            btn.setStyleSheet(_btn_ss)
            return btn

        def _make_sep() -> QFrame:
            sep = QFrame(dialog)
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Plain)
            sep.setFixedWidth(1)
            sep.setFixedHeight(36)
            sep.setStyleSheet("QFrame{background:" + _SEP_COL + ";background-color:" + _SEP_COL + ";}")
            return sep

        # ── Nhóm 1: Chế độ xem ──────────────────────────────────────────────
        btn_overview = _make_btn(
            "preview_overview.svg", "Tổng quan",
            "Xem thu nhỏ tất cả các trang",
            icon_color="#7880b8", checkable=True, w=58,
        )
        btn_single = _make_btn(
            "preview_single_page.svg", "Một trang",
            "Cuộn từng trang riêng lẻ",
            icon_color="#7880b8", checkable=True, w=56,
        )
        btn_facing = _make_btn(
            "preview_facing_pages.svg", "Hai trang",
            "Xem hai trang song song",
            icon_color="#7880b8", checkable=True, w=56,
        )
        btn_single.setChecked(True)

        # QButtonGroup: chỉ một nút chế độ xem được chọn tại một thời điểm
        from packages.qt_compat.QtWidgets import QButtonGroup
        _view_group = QButtonGroup(dialog)
        _view_group.setExclusive(True)
        _view_group.addButton(btn_overview)
        _view_group.addButton(btn_single)
        _view_group.addButton(btn_facing)

        # ── Nhóm 2: Vừa trang & Zoom ────────────────────────────────────────
        btn_fit_width = _make_btn(
            "fit_width.svg", "Vừa rộng",
            "Vừa chiều rộng cửa sổ",
            icon_color="#4f8ff7", w=54,
        )
        btn_fit_page = _make_btn(
            "fit_page.svg", "Vừa trang",
            "Vừa toàn trang trong cửa sổ",
            icon_color="#4f8ff7", w=54,
        )
        btn_zoom_out = _make_btn(
            "zoom_out.svg", "Thu nhỏ",
            "Giảm zoom",
            icon_color="#30b088", w=40,
        )
        btn_zoom_in = _make_btn(
            "zoom_in.svg", "Phóng to",
            "Tăng zoom",
            icon_color="#30b088", w=40,
        )
        zoom_spin = QSpinBox()
        zoom_spin.setRange(25, 400)
        zoom_spin.setValue(100)
        zoom_spin.setSuffix("%")
        zoom_spin.setFixedSize(66, 26)
        zoom_spin.setToolTip("Mức zoom (25%–400%)")
        zoom_spin.setStyleSheet(_spin_ss)

        # ── Nhóm 3: Điều hướng trang ────────────────────────────────────────
        btn_prev = _make_btn(
            "chevron_left.svg", "Trước",
            "Trang trước",
            icon_color="#6676e8", w=42,
        )
        btn_next = _make_btn(
            "chevron_right.svg", "Sau",
            "Trang sau",
            icon_color="#6676e8", w=42,
        )
        page_spin = QSpinBox()
        page_spin.setRange(1, 1)
        page_spin.setValue(current_page)
        page_spin.setFixedSize(54, 26)
        page_spin.setToolTip("Số trang hiện tại")
        page_spin.setStyleSheet(_spin_ss)
        page_total = QLabel("/ ?")
        page_total.setStyleSheet("color:#6878a8; font-size:12px; padding:0 2px;")

        # ── Nhóm 4: Thiết lập trang & Hướng ────────────────────────────────
        btn_page_setup = _make_btn(
            "settings.svg", "Trang...",
            "Thiết lập khổ giấy và lề",
            icon_color="#9098c8", w=52,
        )
        btn_portrait = _make_btn(
            "page_portrait.svg", "Dọc",
            "Hướng dọc – Portrait",
            icon_color="#9098c8", w=42, checkable=True,
        )
        btn_landscape = _make_btn(
            "page_landscape.svg", "Ngang",
            "Hướng ngang – Landscape",
            icon_color="#9098c8", w=48, checkable=True,
        )
        btn_portrait.setChecked(True)

        # QButtonGroup: Dọc/Ngang exclusive
        _orient_group = QButtonGroup(dialog)
        _orient_group.setExclusive(True)
        _orient_group.addButton(btn_portrait)
        _orient_group.addButton(btn_landscape)

        # ── Nhóm 5: In & Đóng ───────────────────────────────────────────────
        btn_print = _make_btn(
            "print.svg", "In...",
            "Mở hộp thoại in (Ctrl+P)",
            icon_color="#1ab87a", w=52,
        )
        btn_close = _make_btn(
            "close_preview.svg", "Đóng",
            "Đóng xem trước",
            icon_color="#d24b4b", w=48,
        )

        # ── Xây toolbar frame ────────────────────────────────────────────────
        toolbar_frame = QFrame(dialog)
        toolbar_frame.setObjectName("printToolbar")
        toolbar_frame.setStyleSheet(
            "QFrame#printToolbar{"
            "  background:" + _TOOLBAR_BG + ";"
            "  border-bottom:1px solid " + _TOOLBAR_BDR + ";"
            "}"
        )
        toolbar_frame.setFixedHeight(58)

        # SpinBox được bọc kèm label nhỏ bên dưới cho đồng bộ với icon buttons
        def _labeled_widget(inner: QWidget, label_text: str) -> QWidget:
            w = QWidget(dialog)
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 2, 0, 0)
            v.setSpacing(1)
            v.addWidget(inner, 0, Qt.AlignmentFlag.AlignHCenter)
            lbl = QLabel(label_text, w)
            lbl.setStyleSheet("color:#5868a0; font-size:9px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            v.addWidget(lbl)
            return w

        # Trang hiện tại / tổng: spin + "/ ?" cạnh nhau, bọc label "Trang"
        _page_nav = QWidget(dialog)
        _pnl = QHBoxLayout(_page_nav)
        _pnl.setContentsMargins(0, 0, 0, 0)
        _pnl.setSpacing(2)
        _pnl.addWidget(page_spin)
        _pnl.addWidget(page_total)

        _zoom_w  = _labeled_widget(zoom_spin, "Zoom")
        _page_w  = _labeled_widget(_page_nav, "Trang")

        tbl = QHBoxLayout(toolbar_frame)
        tbl.setContentsMargins(8, 4, 8, 4)
        tbl.setSpacing(2)

        tbl.addWidget(btn_overview)
        tbl.addWidget(btn_single)
        tbl.addWidget(btn_facing)
        tbl.addSpacing(4)
        tbl.addWidget(_make_sep())
        tbl.addSpacing(4)

        tbl.addWidget(btn_fit_width)
        tbl.addWidget(btn_fit_page)
        tbl.addSpacing(4)
        tbl.addWidget(btn_zoom_out)
        tbl.addWidget(_zoom_w)
        tbl.addWidget(btn_zoom_in)
        tbl.addSpacing(4)
        tbl.addWidget(_make_sep())
        tbl.addSpacing(4)

        tbl.addWidget(btn_prev)
        tbl.addWidget(_page_w)
        tbl.addWidget(btn_next)
        tbl.addSpacing(4)
        tbl.addWidget(_make_sep())
        tbl.addSpacing(4)

        tbl.addWidget(btn_page_setup)
        tbl.addWidget(btn_portrait)
        tbl.addWidget(btn_landscape)
        tbl.addStretch(1)

        tbl.addWidget(btn_print)
        tbl.addSpacing(4)
        tbl.addWidget(btn_close)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar_frame)
        layout.addWidget(preview_viewer, 1)

        def _run_pdfjs(js: str):
            try:
                preview_viewer._web_view.page().runJavaScript(js)
            except Exception:
                pass

        def _set_page(pg: int):
            _run_pdfjs(
                f"""
                (function() {{
                    var app = window.PDFViewerApplication;
                    if (!app || !app.pdfViewer) return;
                    app.pdfViewer.currentPageNumber = {max(1, int(pg or 1))};
                }})()
                """
            )

        def _set_zoom(percent: int):
            scale = max(25, min(400, int(percent or 100))) / 100.0
            _run_pdfjs(
                f"""
                (function() {{
                    var app = window.PDFViewerApplication;
                    if (!app || !app.pdfViewer) return;
                    app.pdfViewer.currentScaleValue = "{scale}";
                }})()
                """
            )

        def _fit_width():
            _run_pdfjs(
                """
                (function() {
                    var app = window.PDFViewerApplication;
                    if (!app || !app.pdfViewer) return;
                    app.pdfViewer.currentScaleValue = "page-width";
                })()
                """
            )

        def _fit_page():
            _run_pdfjs(
                """
                (function() {
                    var app = window.PDFViewerApplication;
                    if (!app || !app.pdfViewer) return;
                    app.pdfViewer.currentScaleValue = "page-fit";
                })()
                """
            )

        def _set_preview_mode(mode: str):
            scripts = {
                "overview": """
                    app.pdfViewer.spreadMode = 0;
                    app.pdfViewer.scrollMode = 2;
                    app.pdfViewer.currentScaleValue = "page-fit";
                """,
                "single": """
                    app.pdfViewer.spreadMode = 0;
                    app.pdfViewer.scrollMode = 0;
                    app.pdfViewer.currentScaleValue = "page-width";
                """,
                "facing": """
                    app.pdfViewer.scrollMode = 0;
                    app.pdfViewer.spreadMode = 1;
                    app.pdfViewer.currentScaleValue = "page-fit";
                """,
            }
            _run_pdfjs(
                f"""
                (function() {{
                    var app = window.PDFViewerApplication;
                    if (!app || !app.pdfViewer) return;
                    {scripts.get(mode, scripts["single"])}
                }})()
                """
            )

        def _update_page(page: int, total: int):
            total = max(1, int(total or page or 1))
            page = max(1, min(total, int(page or 1)))
            try:
                page_spin.blockSignals(True)
                page_spin.setRange(1, total)
                page_spin.setValue(page)
            finally:
                page_spin.blockSignals(False)
            page_total.setText(f"/ {total}")

        def _update_zoom(percent: int):
            if percent <= 0:
                return
            try:
                zoom_spin.blockSignals(True)
                zoom_spin.setValue(max(25, min(400, int(percent))))
            finally:
                zoom_spin.blockSignals(False)

        printer_holder = {"printer": self._configured_pdf_printer(pdf_path, current_page=current_page)}

        def _page_setup():
            QPageSetupDialog(printer_holder["printer"], dialog).exec()

        def _set_orientation(orientation):
            try:
                printer_holder["printer"].setPageOrientation(orientation)
            except Exception:
                pass

        preview_viewer.page_changed.connect(_update_page)
        preview_viewer.zoom_changed.connect(_update_zoom)
        btn_overview.clicked.connect(lambda: _set_preview_mode("overview"))
        btn_single.clicked.connect(lambda: _set_preview_mode("single"))
        btn_facing.clicked.connect(lambda: _set_preview_mode("facing"))
        btn_fit_width.clicked.connect(_fit_width)
        btn_fit_page.clicked.connect(_fit_page)
        page_spin.valueChanged.connect(_set_page)
        zoom_spin.editingFinished.connect(lambda: _set_zoom(zoom_spin.value()))
        btn_prev.clicked.connect(lambda: _set_page(page_spin.value() - 1))
        btn_next.clicked.connect(lambda: _set_page(page_spin.value() + 1))
        btn_zoom_out.clicked.connect(lambda: _set_zoom(max(25, int(zoom_spin.value() / 1.1))))
        btn_zoom_in.clicked.connect(lambda: _set_zoom(min(400, int(zoom_spin.value() * 1.1))))
        btn_page_setup.clicked.connect(_page_setup)
        btn_portrait.clicked.connect(lambda: _set_orientation(QPageLayout.Orientation.Portrait))
        btn_landscape.clicked.connect(lambda: _set_orientation(QPageLayout.Orientation.Landscape))

        def _run_print():
            printer = printer_holder["printer"]
            print_dialog = QPrintDialog(printer, dialog)
            if print_dialog.exec() == QDialog.DialogCode.Accepted:
                self._do_print_pages(printer, pdf_path, show_progress=True)

        btn_print.clicked.connect(_run_print)
        btn_close.clicked.connect(dialog.accept)
        dialog.exec()

    def _open_qt_print_preview(self, pdf_path: str):
        current_page = self._current_viewer_page()
        printer = self._configured_pdf_printer(pdf_path, current_page=current_page)

        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Xem trước khi in")
        try:
            preview.resize(1100, 760)
            
            # Translate the actions
            from packages.qt_compat.QtGui import QAction
            actions = preview.findChildren(QAction)
            translations = {
                "Print": "In",
                "Print...": "In...",
                "Page setup...": "Thiết lập trang...",
                "Page Setup...": "Thiết lập trang...",
                "Zoom In": "Phóng to",
                "Zoom Out": "Thu nhỏ",
                "Show Overview of all pages": "Xem tổng quan tất cả các trang",
                "Show single page": "Xem một trang",
                "Show facing pages": "Xem hai trang",
                "First page": "Trang đầu",
                "Last page": "Trang cuối",
                "Previous page": "Trang trước",
                "Next page": "Trang sau",
                "Fit Width": "Vừa chiều rộng",
                "Fit Page": "Vừa trang",
                "Portrait": "Hướng dọc",
                "Landscape": "Hướng ngang",
                "Close": "Đóng"
            }
            # Preserve target page when switching preview modes.
            from packages.qt_compat.QtWidgets import QWidget
            from packages.qt_compat.QtCore import QTimer
            preview_widget = None
            for child in preview.findChildren(QWidget):
                if hasattr(child, "currentPage") and hasattr(child, "setCurrentPage"):
                    preview_widget = child
                    break
            
            hook_fn = None
            if preview_widget:
                try:
                    preview_widget._last_pg = max(1, int(current_page or 1))
                except Exception:
                    preview_widget._last_pg = 1

                def _remember_page(pg: int):
                    try:
                        preview_widget._last_pg = max(1, int(pg or 1))
                    except Exception:
                        pass

                if hasattr(preview_widget, "currentPageChanged"):
                    try:
                        preview_widget.currentPageChanged.connect(_remember_page)
                    except Exception:
                        pass

                def restore_page():
                    if not preview_widget.isVisible():
                        return

                    try:
                        pg = max(1, int(getattr(preview_widget, "_last_pg", current_page) or current_page or 1))
                    except Exception:
                        pg = max(1, int(current_page or 1))

                    try:
                        if hasattr(preview_widget, "currentPage") and preview_widget.currentPage() != pg:
                            preview_widget.setCurrentPage(pg)
                    except Exception:
                        pass

                hook_fn = lambda: QTimer.singleShot(0, restore_page)

            for act in actions:
                plain_text = act.text().replace("&", "")
                if plain_text in translations:
                    act.setText(translations[plain_text])
                    act.setToolTip(translations[plain_text])
                if hook_fn and plain_text in [
                    "Show Overview of all pages", "Show single page", "Show facing pages", 
                    "Fit Width", "Fit Page", "Portrait", "Landscape"
                ]:
                    act.triggered.connect(hook_fn)
        except Exception:
            pass
        preview.paintRequested.connect(lambda p: self._do_print_pages(p, pdf_path, show_progress=False, preview_dlg=preview))
        preview.exec()

    @staticmethod
    def _page_orientation_for_pdf_size(page_w_pt: float, page_h_pt: float):
        return (
            QPageLayout.Orientation.Landscape
            if float(page_w_pt or 0) > float(page_h_pt or 0)
            else QPageLayout.Orientation.Portrait
        )

    @staticmethod
    def _apply_printer_orientation(printer: QPrinter, orientation) -> bool:
        try:
            return bool(printer.setPageOrientation(orientation))
        except Exception:
            return False

    @staticmethod
    def _print_preview_render_scale(
        page_w_pt: float,
        page_h_pt: float,
        printer_resolution: int,
        *,
        large_job: bool,
        preview_mode: bool,
    ) -> float:
        """Bias preview rendering toward clarity; preview can tolerate extra pixels."""
        page_pixels = max(1.0, float(page_w_pt or 0) * float(page_h_pt or 0))
        dpi_scale = max(1.0, float(printer_resolution or 300) / 72.0)
        job_cap = 4.5 if large_job else 5.5
        pixel_cap = 14_000_000 if large_job else 28_000_000
        if preview_mode:
            job_cap = 6.5 if large_job else 8.5
            pixel_cap = 18_000_000 if large_job else 40_000_000
        scale_by_pixels = (pixel_cap / page_pixels) ** 0.5
        return min(job_cap, max(dpi_scale, scale_by_pixels, 1.0))

    def _do_print_pages(self, printer: QPrinter, pdf_path: str, show_progress: bool = True, preview_dlg=None):
        """Vẽ từng trang PDF lên printer — chạy trên main thread qua paintRequested.

        Tiến độ xử lý qua QProgressDialog (hiện sau 1s nếu vẫn đang chạy) cho
        phép user hủy. processEvents() giữa các trang để UI vẫn phản hồi
        cho file dày.

        Re-entry guard: QPrintPreviewDialog.paintRequested có thể fire nhiều
        lần (zoom/scroll) khi user còn đang thao tác. Nếu đang render dở dang
        rồi mà lại fire tiếp, chồng thêm QProgressDialog + QPainter.begin trên
        cùng printer = crash. Bỏ qua re-fire trong khi chưa xong.
        """
        from packages.qt_compat.QtWidgets import QProgressDialog, QApplication

        if getattr(self, "_print_busy", False):
            return
        self._print_busy = True

        try:
            pdf = get_pdf_engine().open(pdf_path)
        except Exception as e:
            self._print_busy = False
            show_warning(self, "Lỗi in", f"Không mở được tài liệu: {e}")
            return

        try:
            from_page = printer.fromPage()
            to_page   = printer.toPage()
            total     = pdf.page_count
            page_list = list(range(total) if from_page == 0 else range(from_page - 1, to_page))
            count     = len(page_list)
            file_size = 0
            try:
                file_size = os.path.getsize(pdf_path)
            except OSError:
                pass
            is_large_job = file_size >= 128 * 1024 * 1024 or total > 200

            progress = None
            if show_progress:
                progress = QProgressDialog("Dang chuan bi in...", "Huy", 0, count, self)
                progress.setWindowTitle("In tai lieu")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(1000)
                progress.setAutoClose(True)
                progress.setAutoReset(False)

            current_orientation = None
            if page_list:
                try:
                    page_w_pt, page_h_pt = pdf.page_size(page_list[0] + 1)
                    current_orientation = self._page_orientation_for_pdf_size(page_w_pt, page_h_pt)
                    self._apply_printer_orientation(printer, current_orientation)
                except Exception:
                    current_orientation = printer.pageLayout().orientation()

            painter = QPainter()
            if not painter.begin(printer):
                if progress is not None:
                    progress.cancel()
                show_warning(self, "Lỗi in", "Không thể khởi động máy in.")
                return
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            except Exception:
                pass

            cancelled = False
            for i, page_num in enumerate(page_list):
                if progress is not None and progress.wasCanceled():
                    cancelled = True
                    break
                if progress is not None:
                    progress.setValue(i)
                    progress.setLabelText(f"Đang in trang {page_num + 1} / {total}...")
                    QApplication.processEvents()
                try:
                    page_w_pt, page_h_pt = pdf.page_size(page_num + 1)
                except Exception:
                    page_w_pt, page_h_pt = 595.0, 842.0

                desired_orientation = self._page_orientation_for_pdf_size(page_w_pt, page_h_pt)
                if desired_orientation != current_orientation:
                    self._apply_printer_orientation(printer, desired_orientation)
                    current_orientation = desired_orientation

                if i > 0:
                    printer.newPage()

                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                w = int(page_rect.width())
                h = int(page_rect.height())
                target_scale = self._print_preview_render_scale(
                    page_w_pt,
                    page_h_pt,
                    printer.resolution(),
                    large_job=is_large_job,
                    preview_mode=preview_dlg is not None,
                )

                rendered = pdf.render_page_rgb(page_num + 1, scale=target_scale)
                img = QImage(
                    rendered.samples,
                    rendered.width,
                    rendered.height,
                    rendered.stride,
                    QImage.Format.Format_RGB888,
                )
                if img.isNull():
                    raise MemoryError(
                        f"Không đủ bộ nhớ để render trang {page_num + 1}. "
                        "Hãy thử in ít trang hơn hoặc giảm chất lượng in."
                    )

                src_w = max(1, img.width())
                src_h = max(1, img.height())
                ratio = min(w / src_w, h / src_h)
                draw_w = max(1, int(src_w * ratio))
                draw_h = max(1, int(src_h * ratio))
                x = (w - draw_w) // 2
                y = (h - draw_h) // 2
                painter.drawImage(QRect(x, y, draw_w, draw_h), img)

                del img
                del rendered
                if i % 8 == 0:
                    gc.collect()

            painter.end()
            if progress is not None:
                progress.setValue(count)

            if show_progress and cancelled:
                self.status.showMessage("Đã hủy in", 4000)
            elif show_progress:
                self.status.showMessage("✓ In hoàn tất", 4000)
        except Exception as e:
            show_warning(self, "Lỗi in", str(e))
        finally:
            try:
                pdf.close()
            except Exception:
                pass
            if progress is not None:
                progress.close()
                progress.deleteLater()
            self._print_busy = False

    # ------------------------------------------------------------------ #
    #  Menubar                                                             #
    # ------------------------------------------------------------------ #

    def _build_menubar(self):
        return build_menubar(self)

    def _build_menubar_impl(self):
        bar = self.menuBar()
        bar.setNativeMenuBar(use_native_menubar())

        def top_menu(attr: str, title: str) -> QMenu:
            menu = QMenu(title, self)
            setattr(self, attr, menu)
            bar.addMenu(menu)
            return menu

        self.menu_file = top_menu("menu_file", self._t("menu.file", "Tệp"))
        menu_file = self.menu_file
        menu_file.addAction(self.act_new_pdf)
        menu_file.addAction(self.act_open)
        self.menu_recent = menu_file.addMenu("Mở gần đây")
        self.menu_recent.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        self.menu_recent.aboutToShow.connect(self._refresh_recent_menu)
        menu_file.addSeparator()
        menu_file.addAction(self.act_save)
        menu_file.addAction(self.act_print)
        menu_file.addSeparator()

        act_export_word = menu_file.addAction("Xuất ra Word (.docx)…")
        act_export_word.setIcon(svg_icon("save_as.svg", size=16, color="#5b9cf6"))
        act_export_word.triggered.connect(lambda: export_pdf_to_word(self))

        act_export_excel = menu_file.addAction("Xuất ra Excel (.xlsx)…")
        act_export_excel.setIcon(svg_icon("extract.svg", size=16, color="#4fc080"))
        act_export_excel.triggered.connect(lambda: export_pdf_to_excel(self))

        act_export_img = menu_file.addAction("Xuất trang ra ảnh…")
        act_export_img.setIcon(svg_icon("insert_image.svg", size=16, color="#b060e0"))
        act_export_img.triggered.connect(lambda: export_pages_to_images(self))

        act_export_txt = menu_file.addAction("Xuất văn bản ra .txt…")
        act_export_txt.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        act_export_txt.triggered.connect(lambda: export_pdf_to_text(self))

        menu_file.addSeparator()

        act_file_info = menu_file.addAction("Thông tin tệp...")
        act_file_info.setShortcut(QKeySequence("Alt+Return"))
        act_file_info.triggered.connect(lambda: show_file_info(self))
        act_file_info.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))

        act_close_tab = menu_file.addAction("Đóng tab")
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(self._close_current_tab)
        act_close_tab.setIcon(svg_icon("fullscreen.svg", size=16, color="#9b9bc0"))

        menu_file.addSeparator()
        act_exit = menu_file.addAction("Thoát")
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)

        self.menu_nav = top_menu("menu_nav", self._t("menu.navigate", "Điều hướng"))
        menu_nav = self.menu_nav
        menu_nav.addAction(self.act_prev)
        menu_nav.addAction(self.act_next)
        act_goto = menu_nav.addAction("Đến trang...")
        act_goto.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))
        act_goto.triggered.connect(self._focus_page_input)

        self.menu_view = top_menu("menu_view", self._t("menu.view", "Xem"))
        menu_view = self.menu_view
        menu_view.addAction(self.act_zoom_in)
        menu_view.addAction(self.act_zoom_out)
        menu_view.addAction(self.act_fit)
        menu_view.addSeparator()
        menu_view.addAction(self.act_brightness_up)
        menu_view.addAction(self.act_brightness_down)
        menu_view.addSeparator()
        menu_view.addAction(self.act_toggle_sidebar_btn)
        menu_view.addAction(self.act_toggle_toc_btn)
        menu_view.addAction(self.act_toggle_annotations_btn)
        act_toggle_toolbar = self.toolbar.toggleViewAction()
        act_toggle_toolbar.setText("Thanh công cụ")
        act_toggle_toolbar.setShortcut(QKeySequence("Ctrl+B"))
        menu_view.addAction(act_toggle_toolbar)
        act_customize_tb = menu_view.addAction("Tuỳ chỉnh thanh công cụ...")
        act_customize_tb.triggered.connect(self._customize_toolbar)
        menu_view.addSeparator()
        menu_view.addAction(self.act_theme_toggle)
        menu_view.addAction(self.act_fullscreen)

        self.menu_tools = top_menu("menu_tools", self._t("menu.tools", "Công cụ"))
        menu_tools = self.menu_tools

        # Chèn nội dung
        menu_tools.addAction(self.act_insert_text)
        menu_tools.addAction(self.act_insert_image)
        menu_tools.addAction(self.act_draw)
        menu_tools.addSeparator()

        # Chỉnh sửa / xóa object đã chèn
        menu_tools.addAction(self.act_select_inserted)
        menu_tools.addAction(self.act_delete_object)
        menu_tools.addAction(self.act_redact)
        menu_tools.addAction(self.act_edit_existing_text)
        menu_tools.addSeparator()

        # Lưu chỉnh sửa
        menu_tools.addAction(self.act_save_as)
        menu_tools.addAction(self.act_undo)
        menu_tools.addSeparator()

        # Chú thích văn bản
        menu_tools.addAction(self.act_highlight)
        menu_tools.addAction(self.act_highlight_color)
        menu_tools.addAction(self.act_underline)
        menu_tools.addAction(self.act_strikeout)

        act_comment = menu_tools.addAction("Thêm ghi chú (Note)…")
        act_comment.setIcon(svg_icon("history.svg", size=16, color="#f0a030"))
        act_comment.triggered.connect(lambda: add_comment(self))

        menu_tools.addSeparator()

        act_page_numbers = menu_tools.addAction("Thêm số trang…")
        act_page_numbers.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))
        act_page_numbers.triggered.connect(lambda: add_page_numbers(self))

        menu_tools.addSeparator()

        act_find = menu_tools.addAction("Tìm kiếm văn bản...")
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(lambda: search_text(self))
        act_find.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))

        act_find_next = menu_tools.addAction("Tìm tiếp")
        act_find_next.setShortcut(QKeySequence("F3"))
        act_find_next.triggered.connect(lambda: search_next(self))
        act_find_next.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))

        act_find_prev = menu_tools.addAction("Tìm trước đó")
        act_find_prev.setShortcut(QKeySequence("Shift+F3"))
        act_find_prev.triggered.connect(lambda: search_previous(self))
        act_find_prev.setIcon(svg_icon("chevron_left.svg", size=16, color="#9b9bc0"))

        menu_tabs = top_menu("menu_tabs", "Tab")
        act_tab_next = menu_tabs.addAction("Tab kế tiếp")
        act_tab_next.setShortcut(QKeySequence("Ctrl+Tab"))
        act_tab_next.triggered.connect(self._activate_next_tab)
        act_tab_prev = menu_tabs.addAction("Tab trước đó")
        act_tab_prev.setShortcut(QKeySequence("Ctrl+Shift+Tab"))
        act_tab_prev.triggered.connect(self._activate_prev_tab)
        menu_tabs.addAction(act_close_tab)

        self.menu_pages = top_menu("menu_pages", self._t("menu.page", "Trang"))
        menu_pages = self.menu_pages

        act_rotate_cw = menu_pages.addAction("Xoay phải 90°")
        act_rotate_cw.setShortcut(QKeySequence("Ctrl+]"))
        act_rotate_cw.triggered.connect(lambda: rotate_page_cw(self))
        act_rotate_cw.setIcon(svg_icon("rotate_cw.svg", size=16, color="#50b8f0"))

        act_rotate_ccw = menu_pages.addAction("Xoay trái 90°")
        act_rotate_ccw.setShortcut(QKeySequence("Ctrl+["))
        act_rotate_ccw.triggered.connect(lambda: rotate_page_ccw(self))
        act_rotate_ccw.setIcon(svg_icon("rotate_ccw.svg", size=16, color="#50b8f0"))

        menu_pages.addSeparator()

        act_del_page = menu_pages.addAction("Xóa trang này")
        act_del_page.setShortcut(QKeySequence("Ctrl+Delete"))
        act_del_page.triggered.connect(lambda: delete_current_page(self))
        act_del_page.setIcon(svg_icon("delete_page.svg", size=16, color="#e05050"))

        menu_pages.addSeparator()

        act_merge = menu_pages.addAction("Ghép PDF vào cuối...")
        act_merge.triggered.connect(lambda: merge_pdfs_action(self))
        act_merge.setIcon(svg_icon("merge_pdf.svg", size=16, color="#4fc080"))

        act_extract = menu_pages.addAction("Tách PDF...")
        act_extract.triggered.connect(lambda: split_pdf_action(self))
        act_extract.setIcon(svg_icon("extract.svg", size=16, color="#f07858"))

        self.menu_security = top_menu("menu_security", self._t("menu.security", "Bảo mật"))
        menu_security = self.menu_security

        act_watermark = menu_security.addAction("Thêm watermark…")
        act_watermark.setIcon(svg_icon("pen.svg", size=16, color="#f0c050"))
        act_watermark.triggered.connect(lambda: add_watermark(self))

        act_remove_watermark = menu_security.addAction("Xóa watermark…")
        act_remove_watermark.setIcon(svg_icon("trash.svg", size=16, color="#e05050"))
        act_remove_watermark.triggered.connect(lambda: remove_watermark(self))

        menu_security.addSeparator()

        act_set_pw = menu_security.addAction("Đặt mật khẩu PDF…")
        act_set_pw.setIcon(svg_icon("sign_draw.svg", size=16, color="#b060e0"))
        act_set_pw.triggered.connect(lambda: set_pdf_password(self))

        act_rm_pw = menu_security.addAction("Xóa mật khẩu PDF…")
        act_rm_pw.setIcon(svg_icon("trash.svg", size=16, color="#e05050"))
        act_rm_pw.triggered.connect(lambda: remove_pdf_password(self))

        menu_security.addSeparator()

        act_compress = menu_security.addAction("Nén / Tối ưu PDF")
        act_compress.setIcon(svg_icon("save.svg", size=16, color="#4fc080"))
        act_compress.triggered.connect(lambda: compress_pdf(self))

        self.menu_sign = top_menu("menu_sign", self._t("menu.sign", "Chữ ký số"))
        menu_sign = self.menu_sign

        act_sign_draw = menu_sign.addAction("Ký tay / chèn dấu...")
        act_sign_draw.triggered.connect(lambda: sign_handwritten(self))
        act_sign_draw.setIcon(svg_icon("sign_draw.svg", size=16, color="#b060e0"))

        menu_sign.addSeparator()
        menu_sign.addAction(self.act_check_token)
        menu_sign.addAction(self.act_sign)
        menu_sign.addAction(self.act_verify_signature)

        self.menu_ocr = top_menu("menu_ocr", self._t("menu.ocr", "OCR"))
        menu_ocr = self.menu_ocr
        act_ocr_page = menu_ocr.addAction("🔍  OCR trang hiện tại")
        act_ocr_page.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_ocr_page.triggered.connect(lambda: self._ocr_current_page())

        act_ocr_all = menu_ocr.addAction("📄  OCR toàn bộ tài liệu")
        act_ocr_all.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act_ocr_all.triggered.connect(lambda: self._ocr_full_document())

        self.menu_ai = top_menu("menu_ai", self._t("menu.ai", "AI"))
        menu_ai = self.menu_ai

        act_ai_chat = menu_ai.addAction("💬  Chat với PDF...")
        act_ai_chat.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_ai_chat.triggered.connect(lambda: open_chat_dialog(self))

        act_ai_summarize = menu_ai.addAction("📋  Tóm tắt tài liệu...")
        act_ai_summarize.setShortcut(QKeySequence(AI_SUMMARIZE_SHORTCUT))
        act_ai_summarize.triggered.connect(lambda: open_summarize_dialog(self))

        act_ai_translate = menu_ai.addAction("🌐  Dịch trang hiện tại...")
        act_ai_translate.setShortcut(QKeySequence("Ctrl+Shift+T"))
        act_ai_translate.triggered.connect(lambda: open_translate_dialog(self))

        act_ai_search = menu_ai.addAction("🔎  Tìm kiếm theo nghĩa...")
        act_ai_search.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_ai_search.triggered.connect(lambda: open_search_dialog(self))

        menu_ai.addSeparator()
        act_ai_settings = menu_ai.addAction("⚙️  Cài đặt AI (API Key)...")
        act_ai_settings.triggered.connect(lambda: open_ai_settings(self))

        self.menu_license = top_menu("menu_license", self._t("menu.license", "License"))
        menu_license = self.menu_license

        self.menu_language = top_menu("menu_language", self._t("menu.language", "Ngôn ngữ"))
        self._populate_language_menu()
        
        act_activate = menu_license.addAction("🔑  Kích hoạt / Nhập key...")
        act_activate.setShortcut(QKeySequence("Ctrl+Shift+L"))
        act_activate.triggered.connect(lambda: self._open_license_dialog())

        self.menu_help = top_menu("menu_help", self._t("menu.help", "Trợ giúp"))
        menu_help = self.menu_help
        act_shortcuts = menu_help.addAction("Xem phím tắt")
        act_shortcuts.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        act_shortcuts.triggered.connect(self._show_shortcuts_hint)

        act_check_update = menu_help.addAction("Kiểm tra cập nhật...")
        act_check_update.triggered.connect(self._check_for_update)

        act_audit_log = menu_help.addAction("📋  Nhật ký hoạt động...")
        act_audit_log.triggered.connect(self._show_audit_log)

        menu_help.addSeparator()
        act_about = menu_help.addAction("Giới thiệu 3T Reader...")
        act_about.triggered.connect(self._show_about)
        act_about.setIcon(app_logo_icon(16))

        for action in (
            self.act_open, self.act_new_pdf, self.act_recent,
            self.act_insert_text, self.act_insert_image, self.act_select_inserted,
            self.act_draw, self.act_redact, self.act_edit_existing_text, self.act_delete_object,
            self.act_save, self.act_save_as, self.act_print, self.act_prev, self.act_next,
            self.act_zoom_in, self.act_zoom_out, self.act_fit, self.act_fullscreen,
            self.act_check_token, self.act_sign, self.act_verify_signature,
            act_find, act_find_next, act_find_prev,
            act_file_info, act_close_tab, act_tab_next, act_tab_prev,
            act_goto, self.act_toggle_sidebar_btn, act_shortcuts, act_exit,
            self.act_highlight, self.act_undo, act_rotate_cw, act_rotate_ccw, act_del_page,
            act_merge, act_extract, act_sign_draw, self.act_toggle_toc_btn, self.act_toggle_annotations_btn,
        ):
            action.setIconVisibleInMenu(True)
        self._ensure_action_tooltips(bar)

    def _ensure_action_tooltips(self, root):
        """Fill missing tooltips/status tips for menu actions."""
        actions = root.actions() if hasattr(root, "actions") else []
        for action in actions:
            menu = action.menu()
            if menu:
                self._ensure_action_tooltips(menu)
            if action.isSeparator():
                continue
            label = (action.text() or "").replace("&", "").split("\t", 1)[0].strip()
            if not label:
                continue
            if not action.toolTip():
                action.setToolTip(label)


    # ------------------------------------------------------------------ #
    #  Statusbar                                                           #
    # ------------------------------------------------------------------ #

    def _build_statusbar(self):
        return build_status_bar(self)

    # ------------------------------------------------------------------ #
    #  Signals                                                             #
    # ------------------------------------------------------------------ #

    def _connect_signals(self):
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)

    def _on_pdf_loaded(self, viewer, meta):
        tab = self._find_tab_by_viewer(viewer)
        if not tab:
            return
        state = self._tabs_data.get(tab)
        if not state:
            return

        title = os.path.basename(state.get("display_path", "")) or meta.get("filename") or "Document"
        state["search_query"] = ""

        index = self.tab_widget.indexOf(tab)
        if index >= 0:
            self.tab_widget.setTabText(index, title)

        self._inject_css_for_viewer(viewer)

        if viewer is self.viewer:
            self.search_input.clear()
            QTimer.singleShot(0, self._update_chrome_for_active_tab)
            QTimer.singleShot(0, self._load_toc_for_active)
            QTimer.singleShot(0, self._load_annotations_for_active)

    def _on_page_ready(self, viewer):
        if viewer is not self.viewer:
            return
        wv = self._get_webview_for_viewer(viewer)
        if wv:
            self._inject_css_for_viewer(viewer)
            QTimer.singleShot(800, lambda v=viewer: self._dump_viewer_diagnostics(v))
            apply_brightness_to_webview(self, wv)
            QTimer.singleShot(250, lambda: enable_note_tools(self))

    def _on_page_changed(self, viewer, cur, total):
        if viewer is not self.viewer:
            return
        if total and total > 0:
            self.page_label.setText(f"Trang {cur} / {total}")
            self.total_label.setText(f" / {total}")
            self.page_spin.setMaximum(max(1, total))
        else:
            self.page_label.setText(f"Trang {cur} / -")
            self.total_label.setText(" / -")
            self.page_spin.setMaximum(max(1, cur))
        try:
            self.page_spin.blockSignals(True)
            self.page_spin.setValue(cur)
        finally:
            self.page_spin.blockSignals(False)
        self.sidebar.highlight_page(cur)

    def _on_zoom_changed(self, viewer, pct):
        if viewer is not self.viewer or not pct:
            return
        try:
            self.zoom_spin.blockSignals(True)
            self.zoom_spin.setValue(max(25, min(400, int(pct))))
        finally:
            self.zoom_spin.blockSignals(False)

    def _on_signature_clicked(self, viewer, page_number: int, field_name: str):
        state = self._active_state() if viewer is self.viewer else None
        pdf_path = (state or {}).get("source_path") or getattr(viewer, "_path", "") or ""
        if not pdf_path or not os.path.exists(pdf_path):
            show_warning(self, "Chưa có tệp", "Không tìm thấy file PDF để kiểm tra chữ ký.")
            return
        try:
            if hasattr(self, "status"):
                self.status.showMessage("Đang kiểm tra chữ ký số...", 2000)
            from app.actions.sign import SignatureStatusDialog
            from packages.signing.shared import validate_signed_pdf_status

            report = validate_signed_pdf_status(pdf_path, field_name=field_name or None)
            if page_number or field_name:
                report = dict(report)
                report["clicked_page"] = int(page_number or 0)
                report["clicked_field"] = str(field_name or "")
            if not report.get("field_signed"):
                from app.actions.sign import UnsignedSignatureSetupDialog, _sign_existing_signature_field_with_usb
                from packages.qt_compat.QtWidgets import QProgressDialog
                from packages.qt_compat.QtCore import Qt, QCoreApplication
                
                dlg_prog = QProgressDialog("Đang quét tìm USB ký số...", None, 0, 0, self)
                dlg_prog.setWindowTitle("Vui lòng chờ")
                dlg_prog.setWindowModality(Qt.WindowModality.WindowModal)
                dlg_prog.setCancelButton(None)
                dlg_prog.show()
                QCoreApplication.processEvents()

                dlg = UnsignedSignatureSetupDialog(self, report=report)
                dlg_prog.close()
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    _sign_existing_signature_field_with_usb(self, report, dlg._selected_token)
                return

            dlg = SignatureStatusDialog(self, report, path=pdf_path)
            dlg.exec()
        except Exception as exc:
            show_warning(self, "Lỗi kiểm tra chữ ký", str(exc))

    def _load_toc_for_active(self):
        state = self._active_state()
        if not state:
            self.toc_sidebar.clear()
            return
        pdf_path = state.get("source_path")
        if not pdf_path:
            self.toc_sidebar.clear()
            return
        viewer = state["viewer"]
        self.toc_sidebar.load_outline(
            pdf_path,
            on_navigate=lambda page, v=viewer: v.goto_page(page),
        )

    def _load_annotations_for_active(self):
        state = self._active_state()
        if not state:
            self.annotation_sidebar.clear()
            return
        pdf_path = state.get("source_path")
        if not pdf_path:
            self.annotation_sidebar.clear()
            return
        viewer = state["viewer"]
        self.annotation_sidebar.load_annotations(
            pdf_path,
            on_navigate=lambda page, v=viewer: v.goto_page(page),
        )

    def _on_tab_changed(self, _index):
        self._update_chrome_for_active_tab()
        self._reposition_search_panel()
        self._load_toc_for_active()
        self._load_annotations_for_active()
        # Thông báo chat dialog khi đổi tài liệu
        try:
            from app.actions.ai_actions import notify_pdf_changed
            notify_pdf_changed(self.current_path)
        except Exception:
            pass

    def _update_chrome_for_active_tab(self):
        state = self._active_state()
        if not state:
            self.setWindowTitle(WINDOW_TITLE)
            self.total_label.setText(" / -")
            self.file_label.setText("Chưa mở tệp")
            self.page_label.setText("Trang: -")
            self.page_spin.setMaximum(9999)
            try:
                self.page_spin.blockSignals(True)
                self.page_spin.setValue(1)
            finally:
                self.page_spin.blockSignals(False)
            self.search_input.clear()
            self.hide_search_panel()
            self.sidebar.list.clear()
            self.annotation_sidebar.clear()
            return

        display_name = os.path.basename(state["display_path"]) if state["display_path"] else "PDF"
        self.setWindowTitle(f"{display_name} - {WINDOW_TITLE}")
        self.file_label.setText(f"Mở: {display_name}")
        self.file_label.setToolTip(state["display_path"] or "")

        viewer = state["viewer"]
        try:
            total = viewer.get_page_count()
            cur   = viewer.get_current_page()
        except Exception:
            total = 9999
            cur   = 1

        self.page_spin.setMaximum(max(1, total))
        try:
            self.page_spin.blockSignals(True)
            self.page_spin.setValue(max(1, cur))
        finally:
            self.page_spin.blockSignals(False)
        if total and total > 0:
            self.total_label.setText(f" / {total}")
            self.page_label.setText(f"Trang {cur} / {total}")
        else:
            self.total_label.setText(" / -")
            self.page_label.setText(f"Trang {cur} / -")
        self.search_input.setText(state.get("search_query", ""))

        def _handle_sidebar_action(action_name, page_num, v=viewer):
            v.goto_page(page_num)
            if action_name == "delete":
                from app.actions.annotate import delete_current_page
                delete_current_page(self)
            elif action_name == "insert_after":
                from app.actions.pages import insert_blank_page
                insert_blank_page(self, page_num)
            elif action_name == "extract":
                from app.actions.pages import extract_single_page
                extract_single_page(self, page_num)
            elif action_name == "rotate":
                from app.actions.annotate import rotate_page_cw
                rotate_page_cw(self)

        self.sidebar.load_thumbnails(
            state["source_path"],
            on_click=lambda page, v=viewer: v.goto_page(page),
            context_actions={
                "delete": lambda p: _handle_sidebar_action("delete", p),
                "insert_after": lambda p: _handle_sidebar_action("insert_after", p),
                "extract": lambda p: _handle_sidebar_action("extract", p),
                "rotate": lambda p: _handle_sidebar_action("rotate", p),
            }
        )
        self.sidebar.highlight_page(cur)

    # ------------------------------------------------------------------ #
    #  Tab management                                                      #
    # ------------------------------------------------------------------ #

    def _close_current_tab(self):
        index = self.tab_widget.currentIndex()
        if index >= 0:
            self._close_tab(index)

    def _has_unsaved_changes(self, state: dict | None = None) -> bool:
        if state is None:
            state = self._active_state()
        if not state:
            return False
        edit_state = state.get("_pdf_edit_state")
        if edit_state and edit_state.get("ops"):
            return True
        target_path = state.get("source_path")
        return has_pending_annotations(self, target_path)

    def _close_tab(self, index) -> bool:
        tab = self.tab_widget.widget(index)
        if not tab:
            return True

        state = self._tabs_data.get(tab)
        if not self._can_close_tab_state(state):
            return False
        queue = getattr(self, "_annotation_op_queue", None)
        target_path = state.get("source_path") if state else None
        if queue is not None or has_pending_annotations(self, target_path):
            try:
                flush_all = getattr(queue, "flush_all", None)
                ok = flush_all(target_path) if callable(flush_all) else queue.flush()
                if not ok:
                    QMessageBox.warning(
                        self,
                        "Chưa lưu xong chú thích",
                        "Một số thay đổi chú thích chưa lưu xong. Vui lòng đợi vài giây rồi đóng tab lại.",
                    )
                    return False
            except Exception as exc:
                QMessageBox.warning(self, "Chưa lưu xong chú thích", str(exc))
                return False
        edit_state = state.get("_pdf_edit_state") if state else None
        if self._has_unsaved_changes(state) and edit_state and edit_state.get("ops"):
            title = self.tab_widget.tabText(index) or "tài liệu"
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Chưa lưu thay đổi")
            box.setText(f"Tệp '{title}' có thay đổi chưa lưu.")
            box.setInformativeText("Bạn muốn lưu trước khi đóng không?")

            save_btn = box.addButton("Lưu", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Không lưu", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(save_btn)
            box.exec()

            clicked = box.clickedButton()
            if clicked == cancel_btn:
                return False
            if clicked == save_btn:
                self.tab_widget.setCurrentIndex(index)
                if not save_edits_quiet(self):
                    return False

        state = self._tabs_data.pop(tab, None)
        self._dispose_tab_resources(state)
        self.tab_widget.removeTab(index)
        tab.deleteLater()
        if self.tab_widget.count() == 0:
            self.hide_search_panel()
            self.toc_sidebar.clear()
            self.annotation_sidebar.clear()
            self._show_welcome_tab()
            self._update_chrome_for_active_tab()
        else:
            self._update_tab_bar_visibility()
        return True

    def _can_close_tab_state(self, state) -> bool:
        if not state:
            return True

        related_paths = {
            path
            for path in (
                state.get("source_path"),
                state.get("display_path"),
                state.get("temp_path"),
            )
            if path
        }
        if not related_paths:
            return True

        try:
            from app.ai_task_runner import dialog_task_running
        except Exception:
            return True

        chat = getattr(self, "_ai_chat_dialog", None)
        if chat is not None:
            chat_busy = dialog_task_running(chat) or bool(getattr(chat, "_busy", False))
            if chat_busy and getattr(chat, "_pdf_path", None) in related_paths:
                show_warning(self, "Tác vụ đang chạy", "AI chat đang xử lý tài liệu này. Hãy chờ tác vụ hoàn tất rồi đóng tab.")
                return False

        search = getattr(self, "_ai_search_dialog", None)
        if search is not None:
            search_busy = any(
                dialog_task_running(search, thread_attr=attr)
                for attr in ("_load_index_thread", "_build_index_thread", "_search_thread")
            )
            if search_busy and getattr(search, "_pdf_path", None) in related_paths:
                show_warning(self, "Tác vụ đang chạy", "AI search đang dựng index hoặc tìm kiếm trên tài liệu này. Hãy chờ tác vụ hoàn tất rồi đóng tab.")
                return False
        return True

    def _activate_next_tab(self):
        count = self.tab_widget.count()
        if count <= 1:
            return
        self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() + 1) % count)

    def _activate_prev_tab(self):
        count = self.tab_widget.count()
        if count <= 1:
            return
        self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() - 1) % count)

    def _tab_has_unsaved_edits(self, tab) -> bool:
        state = self._tabs_data.get(tab)
        edit_state = state.get("_pdf_edit_state") if state else None
        return bool(edit_state and edit_state.get("ops"))

    def _focus_page_input(self):
        self.page_spin.setFocus()
        self.page_spin.selectAll()

    def _show_shortcuts_hint(self):
        s = shortcut_label
        show_info(
            self, "Phím tắt",
            f"{s('Ctrl+O')}: Mở tệp\n"
            f"{s('Ctrl+W')}: Đóng tab\n"
            f"{s('Ctrl+Tab')}: Tab kế tiếp\n"
            f"{s('Ctrl+Shift+Tab')}: Tab trước đó\n"
            f"{s('Ctrl+F')}: Tìm kiếm văn bản\n"
            "F3 / Shift+F3: Tìm tiếp / tìm trước đó\n"
            f"{s('Ctrl+S')}: Lưu\n"
            f"{s('Ctrl+P')}: In\n"
            f"{s('Ctrl+0')}: Vừa trang\n"
            f"{s('Ctrl+-')} / {s('Ctrl+=')} : Thu nhỏ / phóng to\n"
            f"{fullscreen_shortcut_hint()}: Toàn màn hình",
        )

    def _show_about(self):
        from app.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    def _cleanup_update_check_worker(self):
        self._update_check_worker = None
        self._update_check_thread = None
        if self._pending_manual_update_check:
            self._pending_manual_update_check = False
            QTimer.singleShot(0, lambda: self._start_update_check(show_up_to_date=True, show_errors=True))

    def _start_update_check(self, *, show_up_to_date: bool, show_errors: bool):
        import threading as _threading
        from app.config import VPS_LICENSE_BASE_URL, UPDATE_CHANNEL
        from app.version import APP_VERSION

        # Kiểm tra thread Python đang chạy (thay QThread để tránh bug PySide6 6.11+Python3.14)
        if self._update_check_thread is not None and self._update_check_thread.is_alive():
            if show_errors:
                self._pending_manual_update_check = True
                self.status.showMessage("Đang kiểm tra cập nhật nền, sẽ kiểm tra lại ngay sau đó...", 5000)
            return

        self._pending_manual_update_check = False
        self.status.showMessage("Đang kiểm tra cập nhật...", 0 if show_errors else 3000)

        # Worker vẫn là QObject — nhưng KHÔNG moveToThread.
        # Worker ở main thread, Python thread chỉ gọi worker.run().
        # Signal emit từ Python thread sẽ được Qt tự queue về main thread (thread-safe).
        worker = UpdateCheckWorker(VPS_LICENSE_BASE_URL, APP_VERSION, UPDATE_CHANNEL)
        worker.available.connect(self._show_update_dialog)
        if show_up_to_date:
            worker.up_to_date.connect(self._on_update_up_to_date)
        worker.error.connect(lambda msg: self._on_update_check_error(msg, show_errors))
        worker.finished.connect(lambda: QTimer.singleShot(0, self._cleanup_update_check_worker))

        self._update_check_worker = worker

        # Dùng Python thread — KHÔNG dùng QThread để tránh QObjectWrapper destructor bug
        def _run_and_cleanup():
            try:
                worker.run()
            except Exception:
                pass

        t = _threading.Thread(target=_run_and_cleanup, daemon=True, name="update-check")
        self._update_check_thread = t
        t.start()

    def _auto_check_update(self):
        """Silent check lúc khởi động — chỉ hiện dialog nếu có bản mới."""
        self._start_update_check(show_up_to_date=False, show_errors=False)

    def _check_for_update(self):
        """Check thủ công từ menu — luôn hiện kết quả."""
        self._start_update_check(show_up_to_date=True, show_errors=True)

    def _show_update_dialog(self, info):
        from app.update_dialog import UpdateDialog
        dlg = UpdateDialog(self, info)
        dlg.exec()

    def _on_update_up_to_date(self, info):
        from app.dialogs import show_info
        from app.version import APP_VERSION

        latest = getattr(info, "latest_version", "") or APP_VERSION
        self.status.showMessage("Bạn đang dùng phiên bản mới nhất.", 4000)
        show_info(self, "Đã cập nhật", f"Phiên bản {APP_VERSION} là mới nhất.\nLatest server: {latest}")

    def _on_update_check_error(self, message: str, show_warning_dialog: bool):
        safe_message = message or "Không thể kiểm tra cập nhật."
        self.status.showMessage(f"Không kiểm tra được cập nhật: {safe_message}", 7000)
        if show_warning_dialog:
            self.raise_()
            self.activateWindow()
            QMessageBox.warning(self, "Không kiểm tra được cập nhật", safe_message)

    def _populate_language_menu(self):
        try:
            self.menu_language.clear()
        except RuntimeError:
            pass
            
        from app.language_manager import available_languages, language_pack_path
        
        self.act_lang_vi = self.menu_language.addAction(self._t("lang.vietnamese", "Tiếng Việt"))
        self.act_lang_en = self.menu_language.addAction(self._t("lang.english", "English"))
        self.act_lang_vi.triggered.connect(lambda: self._set_language("vi"))
        self.act_lang_en.triggered.connect(lambda: self._set_language("en"))
        
        self.menu_language.addSeparator()
        
        added = False
        for item in available_languages():
            code = item["code"]
            if code in ("vi", "en"): continue
            if language_pack_path(code).exists():
                act = self.menu_language.addAction(item["label"])
                act.triggered.connect(lambda checked=False, c=code: self._set_language(c))
                added = True
                
        if added:
            self.menu_language.addSeparator()
            
        self.act_lang_refresh = self.menu_language.addAction(self._t("lang.download", "Tải gói ngôn ngữ..."))
        self.act_lang_refresh.triggered.connect(lambda: self._refresh_language_pack())

    def _set_language(self, code: str):
        code = code if code in ("vi", "en", "fr", "zh", "ko", "th") else "vi"
        set_selected_language(code)
        self._language_code = code
        self._apply_language_texts()
        self.status.showMessage(f"Đã chuyển sang ngôn ngữ: {code}", 3000)

    def _refresh_language_pack(self):
        self._open_language_pack_dialog()

    def _open_language_pack_dialog(self):
        from app.language_pack_dialog import LanguagePackDialog

        dialog = LanguagePackDialog(self)
        if dialog.exec() != 1:
            return

        selected_codes = dialog.selected_codes()
        if not selected_codes:
            QMessageBox.information(
                self,
                "Tải gói ngôn ngữ",
                "Chưa chọn gói ngôn ngữ nào để tải.",
            )
            return

        self._download_selected_language_packs(selected_codes)

    def _download_selected_language_packs(self, codes: list[str]):
        label_map = {item["code"]: item["label"] for item in available_languages()}
        successes: list[str] = []
        failures: list[str] = []

        for code in codes:
            ok, detail = download_language_pack(code, self)
            label = label_map.get(code, code)
            if ok:
                successes.append(label)
            else:
                failures.append(f"{label}: {detail}")

        if successes and not failures:
            self.status.showMessage(f"Đã tải xong gói ngôn ngữ: {', '.join(successes)}", 5000)
            QMessageBox.information(
                self,
                "Tải gói ngôn ngữ",
                "Đã tải xong:\n" + "\n".join(f"• {name}" for name in successes),
            )
            return

        if successes or failures:
            message = []
            if successes:
                message.append("Đã tải:\n" + "\n".join(f"• {name}" for name in successes))
            if failures:
                message.append("Không tải được:\n" + "\n".join(f"• {name}" for name in failures))
            self.raise_()
            self.activateWindow()
            QMessageBox.warning(self, "Tải gói ngôn ngữ", "\n\n".join(message))

    def _apply_language_texts(self):
        """Cập nhật toàn bộ text UI theo ngôn ngữ hiện tại.
        
        Tên biến thực tế (self.xxx) được đọc trực tiếp từ _build_toolbar_impl:
        - self.act_open, self.act_new_pdf, self.act_save, self.act_save_as, self.act_print
        - self.act_prev, self.act_next, self.act_zoom_in, self.act_zoom_out, self.act_fit
        - self.act_highlight, self.act_highlight_color, self.act_underline, self.act_strikeout
        - self.act_insert_text, self.act_insert_image, self.act_draw, self.act_redact
        - self.act_delete_object, self.act_select_inserted, self.act_undo
        - self.act_toggle_sidebar_btn, self.act_toggle_toc_btn, self.act_toggle_annotations_btn
        - self.act_theme_toggle, self.act_fullscreen, self.act_tts
        - self.act_verify_signature (alias: self.act_sign, self.act_sign_file, self.act_signature_field)
        
        Private actions (tạo trong _build_toolbar_impl, KHÔNG có trong toolbar cũ):
        - self._act_comment (Tab Annotate)
        - self._act_rcw, self._act_rccw, self._act_del (Tab Page - Rotate/Delete)
        - self._act_merge, self._act_extract, self._act_pgnum (Tab Page - Organize)
        - self._act_wm, self._act_rmwm, self._act_setpw, self._act_rmpw, self._act_comp (Tab Security)
        - self._act_word, self._act_xl, self._act_img, self._act_txt (Tab Export)
        - self._act_ocr1, self._act_ocr2 (Tab OCR)
        - self._act_chat, self._act_sum, self._act_trans, self._act_srch, self._act_aiset (Tab AI)
        - self._act_token, self._act_sign2, self._act_sign_settings, self._act_sign3 (Tab Sign)
        - self._act_sign_batch, self._act_field, self._act_handw (Tab Sign)
        
        Groups: self.g_file, g_nav, g_zoom, g_view, g_mark, g_edit, g_undo, g_rot, g_org,
                self.g_sec, g_exp, g_ocr, g_ai, g_tts, g_sign, g_verify
        """
        def _set(attr: str, key: str, fallback: str):
            """Cập nhật text cho action/widget có tên attr trên self."""
            obj = getattr(self, attr, None)
            if obj is not None:
                obj.setText(self._t(key, fallback))

        # ── Ribbon Tab labels ──────────────────────────────────────────────
        if hasattr(self, "ribbon"):
            self.ribbon.set_tab_text(0, self._t("tab.file_view", "Tệp & Xem"))
            self.ribbon.set_tab_text(1, self._t("tab.annotate", "Chú thích"))
            self.ribbon.set_tab_text(2, self._t("tab.page", "Trang"))
            self.ribbon.set_tab_text(3, self._t("tab.security_export", "Bảo mật & Xuất"))
            self.ribbon.set_tab_text(4, self._t("tab.ocr_ai", "OCR & AI"))
            self.ribbon.set_tab_text(5, self._t("tab.sign", "Ký số"))

        # ── Ribbon Group labels ────────────────────────────────────────────
        for attr, key, fb in [
            ("g_file",    "group.file",      "Tệp"),
            ("g_nav",     "group.navigate",  "Điều hướng"),
            ("g_zoom",    "group.zoom",      "Thu phóng"),
            ("g_view",    "group.view",      "Giao diện"),
            ("g_mark",    "group.mark",      "Đánh dấu"),
            ("g_edit",    "group.edit",      "Chỉnh sửa"),
            ("g_undo",    "group.undo",      "Lịch sử"),
            ("g_rot",     "group.rotate",    "Xoay / Xóa"),
            ("g_org",     "group.organize",  "Tổ chức"),
            ("g_sec",     "group.security",  "Bảo mật"),
            ("g_exp",     "group.export",    "Xuất"),
            ("g_ocr",     "group.ocr",       "OCR"),
            ("g_ai",      "group.ai",        "AI"),
            ("g_tts",     "group.read",      "Đọc sách"),
            ("g_sign",    "group.usbsign",   "Chữ ký số"),
            ("g_verify",  "group.verify",    "Kiểm tra"),
        ]:
            grp = getattr(self, attr, None)
            if grp is not None:
                grp.set_title(self._t(key, fb))

        # ── Public Actions (self.act_xxx) ──────────────────────────────────
        _set("act_open",                 "action.open",           "Mở tệp")
        _set("act_new_pdf",              "action.new_pdf",        "PDF mới")
        _set("act_recent",               "action.recent",         "Gần đây")
        _set("act_save",                 "action.save",           "Lưu")
        _set("act_save_as",              "action.save_as",        "Lưu mới")
        _set("act_print",                "action.print",          "In")
        _set("act_prev",                 "action.prev",           "Trang trước")
        _set("act_next",                 "action.next",           "Trang sau")
        _set("act_zoom_in",              "action.zoom_in",        "Phóng to")
        _set("act_zoom_out",             "action.zoom_out",       "Thu nhỏ")
        _set("act_fit",                  "action.fit",            "Vừa trang")
        _set("act_theme_toggle",         "action.theme",          "Giao diện")
        _set("act_fullscreen",           "action.fullscreen",     "Toàn màn")
        _set("act_highlight",            "action.highlight",      "Tô sáng")
        _set("act_highlight_color",      "action.fill_color",     "Màu tô")
        _set("act_underline",            "action.underline",      "Gạch dưới")
        _set("act_strikeout",            "action.strikeout",      "Gạch ngang")
        _set("act_insert_text",          "action.insert_text",    "Chèn chữ")
        _set("act_insert_image",         "action.insert_image",   "Chèn ảnh")
        _set("act_draw",                 "action.draw",           "Vẽ tự do")
        _set("act_redact",               "action.redact",         "Xóa trắng")
        _set("act_edit_existing_text",   "action.edit_existing",  "Sửa text gốc")
        _set("act_delete_object",        "action.delete_object",  "Xóa đối tượng")
        _set("act_select_inserted",      "action.select_object",  "Chọn & Xoay")
        _set("act_undo",                 "action.undo",           "Hoàn tác")
        _set("act_toggle_sidebar_btn",   "action.thumbnail",      "Thumb")
        _set("act_toggle_toc_btn",       "action.toc",            "Mục lục")
        _set("act_toggle_annotations_btn","action.annotations",   "Chú thích")
        _set("act_tts",                  "action.tts",            "Đọc sách")
        _set("act_verify_signature",     "action.verify",         "Kiểm tra")

        # ── Private Actions (self._act_xxx) — đặt tên đúng theo code ──────
        _set("_act_comment",         "action.comment",           "Ghi chú")
        _set("_act_rcw",             "action.rotate_cw",         "Xoay phải")
        _set("_act_rccw",            "action.rotate_ccw",        "Xoay trái")
        _set("_act_del",             "action.delete_page",       "Xóa trang")
        _set("_act_merge",           "action.merge_pdf",         "Ghép PDF")
        _set("_act_extract",         "action.extract_page",      "Tách PDF")
        _set("_act_pgnum",           "action.page_number",       "Số trang")
        _set("_act_wm",              "action.watermark",         "Watermark")
        _set("_act_rmwm",            "action.remove_watermark",  "Xóa watermark")
        _set("_act_setpw",           "action.set_password",      "Đặt mật khẩu")
        _set("_act_rmpw",            "action.remove_password",   "Xóa mật khẩu")
        _set("_act_comp",            "action.compress",          "Nén PDF")
        _set("_act_word",            "action.export_word",       "Word")
        _set("_act_xl",              "action.export_excel",      "Excel")
        _set("_act_img",             "action.export_image",      "Ảnh")
        _set("_act_txt",             "action.export_text",       "Văn bản")
        _set("_act_ocr1",            "action.ocr_page",          "OCR trang")
        _set("_act_ocr2",            "action.ocr_document",      "OCR toàn bộ")
        _set("_act_chat",            "action.chat_pdf",          "Chat PDF")
        _set("_act_sum",             "action.summary",           "Tóm tắt")
        _set("_act_trans",           "action.translate",         "Dịch")
        _set("_act_srch",            "action.semantic_search",   "Tìm nghĩa")
        _set("_act_aiset",           "action.ai_settings",       "AI Key")
        _set("_act_token",           "action.check_usb",         "Kiểm tra USB")
        _set("_act_sign2",           "action.sign",              "Ký số")
        _set("_act_sign_settings",   "action.sign_settings",     "Cài đặt")
        _set("_act_sign3",           "action.sign_pfx",          "Ký PFX")
        _set("_act_sign_batch",      "action.sign_batch",        "Ký lô")
        _set("_act_field",           "action.signature_field",   "Ô ký")
        _set("_act_handw",           "action.hand_sign",         "Ký tay/dấu")

        # ── Menus ──────────────────────────────────────────────────────────
        for attr, key, fb in [
            ("menu_file",     "menu.file",     "Tệp"),
            ("menu_nav",      "menu.navigate", "Điều hướng"),
            ("menu_view",     "menu.view",     "Xem"),
            ("menu_tools",    "menu.tools",    "Công cụ"),
            ("menu_pages",    "menu.page",     "Trang"),
            ("menu_security", "menu.security", "Bảo mật"),
            ("menu_sign",     "menu.sign",     "Chữ ký số"),
            ("menu_ocr",      "menu.ocr",      "OCR"),
            ("menu_ai",       "menu.ai",       "AI"),
            ("menu_license",  "menu.license",  "License"),
            ("menu_language", "menu.language", "Ngôn ngữ"),
            ("menu_help",     "menu.help",     "Trợ giúp"),
        ]:
            m = getattr(self, attr, None)
            if m is not None:
                m.setTitle(self._t(key, fb))

        # ── Language menu items ────────────────────────────────────────────
        _set("act_lang_vi",        "lang.vietnamese", "Tiếng Việt")
        _set("act_lang_en",        "lang.english",    "English")
        _set("act_lang_fr",        "lang.french",     "Français")
        _set("act_lang_zh",        "lang.chinese",    "中文")
        _set("act_lang_ko",        "lang.korean",     "한국어")
        _set("act_lang_th",        "lang.thai",       "ไทย")
        _set("act_lang_refresh",   "lang.download",   "Tải gói ngôn ngữ...")
        _set("act_lang_vi_tb",     "lang.vietnamese", "Tiếng Việt")
        _set("act_lang_en_tb",     "lang.english",    "English")
        _set("act_lang_fr_tb",     "lang.french",     "Français")
        _set("act_lang_zh_tb",     "lang.chinese",    "中文")
        _set("act_lang_ko_tb",     "lang.korean",     "한국어")
        _set("act_lang_th_tb",     "lang.thai",       "ไทย")
        _set("act_lang_refresh_tb","lang.download",   "Tải gói ngôn ngữ...")

        if hasattr(self, "_lang_toolbar_button"):
            self._lang_toolbar_button.setText(self._t("menu.language", "Ngôn ngữ"))
            self._lang_toolbar_button.setToolTip(self._t("menu.language", "Ngôn ngữ"))

        # ── Status bar ─────────────────────────────────────────────────────
        if hasattr(self, "file_label") and self.file_label.text() in ("Chưa mở tệp", "No file opened"):
            self.file_label.setText(self._t("status.no_file", "Chưa mở tệp"))

        # ── Welcome widget ─────────────────────────────────────────────────
        if hasattr(self, "_welcome_tab") and self._welcome_tab:
            self._welcome_tab.apply_language_texts(self._t)


    def _show_audit_log(self):
        from app.audit_log_dialog import AuditLogDialog
        dlg = AuditLogDialog(self)
        dlg.exec()

    def _refresh_recent_menu(self):
        menu = getattr(self, "menu_recent", None)
        if menu is None:
            return
        try:
            menu.clear()
        except RuntimeError:
            return
        _populate_recent_menu(menu, self)

    def _clear_recent_from_menu(self):
        clear_recent()
        self.status.showMessage("Đã xóa danh sách tệp gần đây", 3000)

    

    def open_signing_settings(self):
        from packages.qt_compat.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QComboBox, QFileDialog, QGroupBox, QInputDialog, QCheckBox
        from app.config import VPS_LICENSE_BASE_URL
        import json
        import os
        import uuid
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Cài đặt Ký số & TSA")
        dlg.resize(500, 450)
        
        layout = QVBoxLayout(dlg)
        
        # TSA Settings (Global)
        layout.addWidget(QLabel("Cấu hình Dấu Thời Gian (TSA):"))
        tsa_mode_combo = QComboBox(dlg)
        tsa_mode_combo.addItem("Theo hệ thống máy (Mặc định)", "system")
        tsa_mode_combo.addItem("Theo máy chủ ứng dụng (3T Company)", "server")
        tsa_mode_combo.addItem("Người dùng tự cấu hình", "custom")
        layout.addWidget(tsa_mode_combo)
        
        url_input = QLineEdit(dlg)
        url_input.setPlaceholderText("VD: http://tsa.gov.vn")
        url_input.setEnabled(False)
        layout.addWidget(url_input)
        
        def on_tsa_mode_changed(idx):
            mode = tsa_mode_combo.itemData(idx)
            if mode == "custom":
                url_input.setEnabled(True)
                url_input.setFocus()
            else:
                url_input.setEnabled(False)
                if mode == "server":
                    url_input.setText(f"{VPS_LICENSE_BASE_URL}/api/v1/tsa")
                else:
                    url_input.setText("")
                    
        tsa_mode_combo.currentIndexChanged.connect(on_tsa_mode_changed)
        
        # Appearance Settings (Profiles)
        layout.addSpacing(10)
        grp = QGroupBox("Cấu hình Ảnh Chữ ký (Profiles)", dlg)
        grp_layout = QVBoxLayout(grp)
        layout.addWidget(grp)
        
        prof_layout = QHBoxLayout()
        prof_combo = QComboBox(dlg)
        btn_add_prof = QPushButton("+", dlg)
        btn_add_prof.setFixedWidth(30)
        btn_del_prof = QPushButton("x", dlg)
        btn_del_prof.setFixedWidth(30)
        
        prof_layout.addWidget(QLabel("Mẫu chữ ký:"))
        prof_layout.addWidget(prof_combo, 1)
        prof_layout.addWidget(btn_add_prof)
        prof_layout.addWidget(btn_del_prof)
        grp_layout.addLayout(prof_layout)
        
        img_layout = QHBoxLayout()
        img_input = QLineEdit(dlg)
        img_input.setPlaceholderText("Đường dẫn file ảnh (.png, .jpg)...")
        img_btn = QPushButton("Chọn ảnh", dlg)
        img_layout.addWidget(img_input)
        img_layout.addWidget(img_btn)
        grp_layout.addLayout(img_layout)
        
        # State variables
        profiles_data = []
        active_prof_id = ""
        
        def browse_img():
            path, _ = QFileDialog.getOpenFileName(dlg, "Chọn ảnh chữ ký", "", "Images (*.png *.jpg *.jpeg)")
            if path:
                img_input.setText(path)
                idx = prof_combo.currentIndex()
                if idx >= 0:
                    prof_id = prof_combo.itemData(idx)
                    for p in profiles_data:
                        if p["id"] == prof_id:
                            p["path"] = path
                            
        img_btn.clicked.connect(browse_img)
        
        grp_layout.addWidget(QLabel("Kiểu hiển thị ảnh:"))
        mode_combo = QComboBox(dlg)
        mode_combo.addItem("Ảnh bên trái, Text bên phải", "left")
        mode_combo.addItem("Chỉ hiển thị ảnh (Không có Text)", "only")
        mode_combo.addItem("Ảnh làm nền mờ (Watermark)", "bg")
        grp_layout.addWidget(mode_combo)
        
        # LTV Settings
        layout.addSpacing(10)
        ltv_check = QCheckBox("Bật Xác thực Dài hạn (LTV - Cần kết nối mạng để tải CRL/OCSP)")
        layout.addWidget(ltv_check)
        
        config_path = os.path.expanduser("~/.3t_reader/signing_config.json")
        
        # Load logic
        cfg = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
            
        tsa_mode = cfg.get("tsa_mode")
        saved_url = cfg.get("tsa_url", "")
        if not tsa_mode:
            if saved_url == f"{VPS_LICENSE_BASE_URL}/api/v1/tsa":
                tsa_mode = "server"
            elif saved_url:
                tsa_mode = "custom"
            else:
                tsa_mode = "system"
        idx = tsa_mode_combo.findData(tsa_mode)
        if idx >= 0:
            tsa_mode_combo.setCurrentIndex(idx)
        if tsa_mode == "custom":
            url_input.setText(saved_url)
            
        ltv_check.setChecked(bool(cfg.get("enable_ltv", False)))
        
        # Migration logic
        if "profiles" in cfg:
            profiles_data = cfg["profiles"]
            active_prof_id = cfg.get("active_profile_id", "")
        else:
            old_path = cfg.get("signature_image_path", "")
            old_mode = cfg.get("signature_image_mode", "left")
            p_id = uuid.uuid4().hex
            profiles_data = [{"id": p_id, "name": "Mặc định", "path": old_path, "mode": old_mode}]
            active_prof_id = p_id
            
        def reload_combo():
            prof_combo.blockSignals(True)
            prof_combo.clear()
            for p in profiles_data:
                prof_combo.addItem(p["name"], p["id"])
            
            idx = prof_combo.findData(active_prof_id)
            if idx >= 0:
                prof_combo.setCurrentIndex(idx)
            elif prof_combo.count() > 0:
                prof_combo.setCurrentIndex(0)
            prof_combo.blockSignals(False)
            on_prof_changed(prof_combo.currentIndex())
            
        def on_prof_changed(idx):
            if idx < 0:
                img_input.setText("")
                return
            prof_id = prof_combo.itemData(idx)
            for p in profiles_data:
                if p["id"] == prof_id:
                    img_input.setText(p.get("path", ""))
                    m = p.get("mode", "left")
                    midx = mode_combo.findData(m)
                    if midx >= 0:
                        mode_combo.setCurrentIndex(midx)
                    break

        prof_combo.currentIndexChanged.connect(on_prof_changed)
        
        def save_current_prof_state():
            idx = prof_combo.currentIndex()
            if idx >= 0:
                prof_id = prof_combo.itemData(idx)
                for p in profiles_data:
                    if p["id"] == prof_id:
                        p["path"] = img_input.text().strip()
                        p["mode"] = mode_combo.currentData()
                        
        def on_add_prof():
            name, ok = QInputDialog.getText(dlg, "Thêm Mẫu Mới", "Tên mẫu chữ ký:")
            if ok and name.strip():
                save_current_prof_state()
                p_id = uuid.uuid4().hex
                profiles_data.append({"id": p_id, "name": name.strip(), "path": "", "mode": "left"})
                nonlocal active_prof_id
                active_prof_id = p_id
                reload_combo()
                
        def on_del_prof():
            if len(profiles_data) <= 1:
                QMessageBox.warning(dlg, "Lỗi", "Phải có ít nhất 1 mẫu chữ ký.")
                return
            idx = prof_combo.currentIndex()
            if idx >= 0:
                prof_id = prof_combo.itemData(idx)
                for i, p in enumerate(profiles_data):
                    if p["id"] == prof_id:
                        profiles_data.pop(i)
                        break
                nonlocal active_prof_id
                active_prof_id = profiles_data[0]["id"]
                reload_combo()
                
        btn_add_prof.clicked.connect(on_add_prof)
        btn_del_prof.clicked.connect(on_del_prof)
        img_input.textChanged.connect(lambda: save_current_prof_state())
        mode_combo.currentIndexChanged.connect(lambda _: save_current_prof_state())
        
        reload_combo()
        
        def save():
            save_current_prof_state()
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            curr_prof_id = ""
            idx = prof_combo.currentIndex()
            if idx >= 0:
                curr_prof_id = prof_combo.itemData(idx)
                
            new_cfg = {
                "tsa_mode": tsa_mode_combo.currentData(),
                "tsa_url": url_input.text().strip(),
                "enable_ltv": ltv_check.isChecked(),
                "active_profile_id": curr_prof_id,
                "profiles": profiles_data
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_cfg, f, ensure_ascii=False, indent=2)
            dlg.accept()
            
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Lưu cấu hình", dlg)
        btn_save.clicked.connect(save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        dlg.exec()

    def _show_pdf_context_menu(self, viewer, pos):
        viewer._web_view.page().runJavaScript(
            "window.getSelection().toString().trim()",
            lambda text: self._build_and_show_pdf_context_menu(viewer, pos, text)
        )

    def _build_and_show_pdf_context_menu(self, viewer, pos, selected_text):
        from packages.qt_compat.QtWidgets import QMenu
        from app.actions.sign import sign_document
        from app.actions.edit import insert_text_to_pdf, insert_image_to_pdf
        
        menu = QMenu(self)
        
        if selected_text:
            act_copy = menu.addAction("✂️ Sao chép văn bản")
            act_copy.triggered.connect(lambda: viewer._web_view.page().runJavaScript("document.execCommand('copy')"))
            
            act_trans = menu.addAction("🌐 Dịch đoạn văn bản này")
            from app.actions.ai_actions import open_translate_dialog
            act_trans.triggered.connect(lambda: open_translate_dialog(self, selected_text))
            
            menu.addSeparator()

        act_sign = menu.addAction("✍️ Ký số tại vị trí này")
        act_sign.triggered.connect(lambda: sign_document(self))
        
        act_text = menu.addAction("📝 Chèn văn bản tại đây")
        act_text.triggered.connect(lambda: insert_text_to_pdf(self))
        
        act_img = menu.addAction("🖼️ Chèn ảnh tại đây")
        act_img.triggered.connect(lambda: insert_image_to_pdf(self))
        
        menu.addSeparator()
        
        act_add_page = menu.addAction("📄 Thêm trang trắng phía sau")
        # act_add_page.triggered.connect(lambda: insert_blank_page(self))

        menu.exec(viewer.mapToGlobal(pos))

    def _show_tab_context_menu(self, pos: QPoint):
        tab_bar = self.tab_widget.tabBar()
        index   = tab_bar.tabAt(pos)
        if index < 0:
            return

        self._tab_context_index = index
        menu = QMenu(self)

        tab = self.tab_widget.widget(index)
        state = self._tabs_data.get(tab)
        source_path = state.get("source_path") if state else None

        if source_path and os.path.exists(source_path):
            act_copy = menu.addAction("Sao chép đường dẫn file")
            from packages.qt_compat.QtWidgets import QApplication
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(os.path.abspath(source_path)))

            act_open_dir = menu.addAction("Mở thư mục chứa file")
            def _open_explorer():
                import subprocess
                import sys
                path = os.path.abspath(source_path)
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer /select,"{path}"')
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", path])
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(path)])
            act_open_dir.triggered.connect(_open_explorer)
            menu.addSeparator()

        act_close = menu.addAction("Đóng tab")
        act_close.triggered.connect(lambda: self._close_tab(index))

        act_close_others = menu.addAction("Đóng tab khác")
        act_close_others.setEnabled(self.tab_widget.count() > 1)
        act_close_others.triggered.connect(lambda: self._close_other_tabs(index))

        act_close_right = menu.addAction("Đóng tab bên phải")
        act_close_right.setEnabled(index < self.tab_widget.count() - 1)
        act_close_right.triggered.connect(lambda: self._close_tabs_right(index))

        menu.addSeparator()
        act_next = menu.addAction("Chuyển sang tab kế tiếp")
        act_next.triggered.connect(self._activate_next_tab)
        act_prev = menu.addAction("Chuyển sang tab trước đó")
        act_prev.triggered.connect(self._activate_prev_tab)

        menu.exec(tab_bar.mapToGlobal(pos))

    def _close_other_tabs(self, keep_index: int):
        for idx in range(self.tab_widget.count() - 1, -1, -1):
            if idx != keep_index:
                if not self._close_tab(idx):
                    break

    def _close_tabs_right(self, index: int):
        for idx in range(self.tab_widget.count() - 1, index, -1):
            if not self._close_tab(idx):
                break

    # ------------------------------------------------------------------ #
    #  Fullscreen / keys / close                                           #
    # ------------------------------------------------------------------ #

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.showNormal()
        else:
            self.showFullScreen()
        self.is_fullscreen = not self.is_fullscreen

    def _dispose_tab_resources(self, state):
        if not state:
            return
        
        import gc
        from packages.qt_compat.QtCore import QUrl

        web_view = state.get("web_view")
        if web_view:
            try:
                web_view.stop()
                web_view.setUrl(QUrl("about:blank"))
                page = web_view.page()
                if page:
                    page.setWebChannel(None)
                    profile = page.profile()
                    if profile:
                        profile.clearHttpCache()
                    page.deleteLater()
            except Exception:
                pass
            web_view.deleteLater()

        viewer = state.get("viewer")
        if viewer:
            viewer.deleteLater()

        temp_path = state.get("temp_path")
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        temp_paths = getattr(self, "_session_temp_paths", None)
        if isinstance(temp_paths, set) and temp_path:
            temp_paths.discard(temp_path)
            
        # Clear the dict to drop any circular references (like edit_state)
        state.clear()
        # Force garbage collection
        gc.collect()

    def eventFilter(self, obj, event):
        from packages.qt_compat.QtCore import QEvent
        if hasattr(self, 'zoom_spin') and obj is self.zoom_spin and event.type() == QEvent.Type.MouseButtonDblClick:
            self.zoom_spin.setValue(100)
            apply_zoom(self)
            return True
        return super().eventFilter(obj, event)

    def _icon_color(self) -> str:
        return "#c0c0e0" if is_dark() else "#3a3a5c"

    def _refresh_icons(self):
        fallback = self._icon_color()
        dark = is_dark()
        for action, svg_file in self._action_icons.items():
            if svg_file not in ("sun.svg", "moon.svg"):
                color = _get_icon_color(svg_file, dark=dark)
                action.setIcon(svg_icon(svg_file, color=color))
        sc = self._search_arrow_color()
        self.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color=sc))
        self.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color=sc))
        self._apply_toolbar_style()

    def _toggle_sidebar(self):
        visible = self.sidebar.isVisible()
        self.sidebar.setVisible(not visible)
        if visible:
            return
        try:
            self.sidebar.highlight_page(self.viewer.get_current_page())
        except Exception:
            pass

    def _toggle_toc(self):
        visible = self.toc_sidebar.isVisible()
        self.toc_sidebar.setVisible(not visible)

    def _toggle_annotations(self):
        visible = self.annotation_sidebar.isVisible()
        self.annotation_sidebar.setVisible(not visible)
        if not visible:
            self._load_annotations_for_active()

    def _show_highlight_context_menu(self):
        """Right-click menu on highlight button: underline, strikeout, color picker."""
        from app.actions.annotate import underline_text, strikeout_text
        menu = QMenu(self)
        # Underline & Strikeout
        menu.addAction(self.act_underline)
        menu.addAction(self.act_strikeout)
        menu.addSeparator()
        # Color presets
        presets = {
            "Vàng": "#facc15",
            "Xanh lá": "#22c55e",
            "Xanh dương": "#38bdf8",
            "Hồng": "#f472b6",
            "Cam": "#fb923c",
        }
        for label, hex_color in presets.items():
            action = menu.addAction(label)
            action.setIcon(svg_icon("highlight.svg", color=hex_color))
            action.triggered.connect(lambda _checked=False, c=hex_color: self._set_highlight_color(QColor(c)))
        menu.addSeparator()
        custom = menu.addAction("Màu khác...")
        custom.triggered.connect(self._pick_custom_highlight_color)
        button = self.toolbar.widgetForAction(self.act_highlight) if hasattr(self, "toolbar") else None
        if button:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            menu.exec(self.cursor().pos())

    def _pick_highlight_color(self):
        presets = {
            "Vàng": "#facc15",
            "Xanh lá": "#22c55e",
            "Xanh dương": "#38bdf8",
            "Hồng": "#f472b6",
            "Cam": "#fb923c",
        }
        menu = QMenu(self)
        for label, hex_color in presets.items():
            action = menu.addAction(label)
            action.setIcon(svg_icon("highlight.svg", color=hex_color))
            action.triggered.connect(lambda _checked=False, c=hex_color: self._set_highlight_color(QColor(c)))
        menu.addSeparator()
        custom = menu.addAction("Màu khác...")
        custom.triggered.connect(self._pick_custom_highlight_color)
        button = self.toolbar.widgetForAction(self.act_highlight_color) if hasattr(self, "toolbar") else None
        if button:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            menu.exec(self.cursor().pos())

    def _pick_custom_highlight_color(self):
        current = getattr(self, "_highlight_color_pdf", [1.0, 1.0, 0.0])
        color = QColor(
            int(max(0.0, min(1.0, current[0])) * 255),
            int(max(0.0, min(1.0, current[1])) * 255),
            int(max(0.0, min(1.0, current[2])) * 255),
        )
        picked = QColorDialog.getColor(color, self, "Chọn màu tô sáng")
        if not picked.isValid():
            return
        self._set_highlight_color(picked)

    def _set_highlight_color(self, picked: QColor):
        self._highlight_color_pdf = [
            round(picked.red() / 255.0, 4),
            round(picked.green() / 255.0, 4),
            round(picked.blue() / 255.0, 4),
        ]
        self._highlight_color_overlay = (
            f"rgba({picked.red()},{picked.green()},{picked.blue()},.35)"
        )
        if hasattr(self, "act_highlight_color"):
            self.act_highlight_color.setIcon(svg_icon("highlight.svg", color=picked.name()))
            self.act_highlight_color.setToolTip("Màu tô sáng hiện tại: " + picked.name())
        if hasattr(self, "status"):
            self.status.showMessage("Đã đổi màu tô sáng.", 1800)

    def _toggle_theme(self):
        toggle_theme()
        self._refresh_icons()
        self.ribbon.set_theme(is_dark())
        if is_dark():
            self.act_theme_toggle.setIcon(svg_icon("sun.svg", color="#f0c050"))
            self.act_theme_toggle.setText("☀ Sáng")
            self.act_theme_toggle.setToolTip("Chuyển sang chế độ sáng (hiện: Tối)")
        else:
            self.act_theme_toggle.setIcon(svg_icon("moon.svg", color="#6c63ff"))
            self.act_theme_toggle.setText("🌙 Tối")
            self.act_theme_toggle.setToolTip("Chuyển sang chế độ tối (hiện: Sáng)")
        btn = self.toolbar.widgetForAction(self.act_theme_toggle)
        if btn:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            
        # Update PDF.js background color dynamically
        from packages.qt_compat.QtGui import QColor
        bg_hex = "#0f0f13" if is_dark() else "#f5f5fa"
        for tab, state in self._tabs_data.items():
            if not isinstance(state, dict): continue
            viewer = state.get("viewer")
            if viewer:
                wv = viewer.findChild(QWebEngineView)
                if wv:
                    wv.page().setBackgroundColor(QColor(bg_hex))
                    wv.page().runJavaScript(f"document.body.style.setProperty('background-color', '{bg_hex}', 'important');")

    def _search_arrow_color(self) -> str:
        return "#dcdcff" if is_dark() else "#505080"

    def _apply_toolbar_style(self):
        bg = "#12122A" if is_dark() else "#E8E8F4"
        self.toolbar.setStyleSheet(
            f"QToolBar {{ border:none; padding:0; margin:0; spacing:0; background:{bg}; }}"
        )

    def _apply_toolbar_prefs(self):
        from app.toolbar_prefs import load_prefs, apply_prefs
        apply_prefs(self, load_prefs())

    def _customize_toolbar(self):
        from app.toolbar_prefs import (
            load_prefs, save_prefs, apply_prefs, ToolbarCustomizeDialog,
        )
        dlg = ToolbarCustomizeDialog(self, load_prefs())
        if dlg.exec() == dlg.DialogCode.Accepted:
            prefs = dlg.get_prefs()
            save_prefs(prefs)
            apply_prefs(self, prefs)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_search_panel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        # macOS standard fullscreen: Ctrl+Cmd+F
        if (sys.platform == "darwin"
                and event.key() == Qt.Key.Key_F
                and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
            self.toggle_fullscreen()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self.status.currentMessage().endswith("(Esc để hủy)"):
                self.status.showMessage("", 0)
                
            if self.search_panel.isVisible():
                self.hide_search_panel()
                return
            if self.is_fullscreen:
                self.showNormal()
                self.is_fullscreen = False
                return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    #  Drag & Drop                                                         #
    # ------------------------------------------------------------------ #

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            supported = (".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".doc", ".docx", ".xls", ".xlsx", ".xml")
            if any(u.toLocalFile().lower().endswith(supported) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        supported = (".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".doc", ".docx", ".xls", ".xlsx", ".xml")
        files = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(supported)]
        
        if not files:
            return

        from app.actions.file import open_file
        
        opened_any = False
        for path in files:
            if os.path.isfile(path):
                before = self.tab_widget.count()
                open_file(self, path)
                if self.tab_widget.count() > before:
                    opened_any = True
                    
        if opened_any:
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent):
        self._closing = True
        try:
            from app.license_dialog import _stop_heartbeat
            _stop_heartbeat(self)
        except Exception:
            pass

        for attr_name in ("_ai_chat_dialog", "_ai_search_dialog"):
            dlg = getattr(self, attr_name, None)
            if dlg is not None:
                try:
                    dlg.close()
                except Exception:
                    pass
                if dlg is not None and getattr(dlg, "isVisible", lambda: False)():
                    self._closing = False
                    event.ignore()
                    return

        if self._update_check_thread is not None and self._update_check_thread.is_alive():
            self._update_check_thread.join(timeout=2.0)

        signing_thread = getattr(self, "_signing_thread", None)
        is_running = False
        if signing_thread is not None:
            is_running = getattr(signing_thread, "isRunning", lambda: False)() or getattr(signing_thread, "is_alive", lambda: False)()
        if is_running:
            if hasattr(signing_thread, "quit"):
                signing_thread.quit()
                if not signing_thread.wait(3000):
                    self._closing = False
                QMessageBox.warning(
                    self,
                    "Đang ký số",
                    "Vui lòng chờ thao tác ký hiện tại hoàn tất rồi hãy đóng ứng dụng.",
                )
                event.ignore()
                return
            else:
                signing_thread.join(timeout=3.0)
                if signing_thread.is_alive():
                    self._closing = False
                    QMessageBox.warning(
                        self,
                        "Đang ký số",
                        "Vui lòng chờ thao tác ký hiện tại hoàn tất rồi hãy đóng ứng dụng.",
                    )
                    event.ignore()
                    return

        if self._token_monitor_timer is not None:
            self._token_monitor_timer.stop()

        if self._token_check_thread is not None and self._token_check_thread.isRunning():
            self._token_check_thread.quit()
            self._token_check_thread.wait(1000)

        queue = getattr(self, "_annotation_op_queue", None)
        if queue is not None or has_pending_annotations(self):
            try:
                flush_all = getattr(queue, "flush_all", None)
                ok = flush_all() if callable(flush_all) else queue.flush()
                if not ok:
                    self._closing = False
                    QMessageBox.warning(
                        self,
                        "Chưa lưu xong chú thích",
                        "Một số thay đổi chú thích chưa lưu xong. Vui lòng đợi vài giây rồi thoát lại.",
                    )
                    event.ignore()
                    return
            except Exception as exc:
                self._closing = False
                QMessageBox.warning(self, "Chưa lưu xong chú thích", str(exc))
                event.ignore()
                return

        for idx in range(self.tab_widget.count() - 1, -1, -1):
            if not self._close_tab(idx):
                self._closing = False
                event.ignore()
                return
        for temp_path in list(getattr(self, "_session_temp_paths", set())):
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
        self._session_temp_paths = set()
        self._tabs_data.clear()
        self._global_state["web_view"] = None
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    #  USB token monitor                                                   #
    # ------------------------------------------------------------------ #

    def _start_token_monitor(self):
        """Theo dõi USB token trong nền mà không khóa luồng UI."""
        if self._token_monitor_timer is not None:
            return
        timer = QTimer(self)
        timer.setInterval(15_000)
        timer.timeout.connect(self._check_token_presence)
        self._token_monitor_timer = timer
        timer.start()
        QTimer.singleShot(1500, self._check_token_presence)

    def _pause_token_monitor(self):
        """Temporarily stop USB presence checks while signing is active."""
        self._token_monitor_suspended = True
        timer = self._token_monitor_timer
        if timer is not None:
            timer.stop()

        thread = self._token_check_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1500)

    def _resume_token_monitor(self):
        """Resume USB presence checks after signing finishes."""
        self._token_monitor_suspended = False
        timer = self._token_monitor_timer
        if timer is not None and not timer.isActive():
            timer.start()

    def _check_token_presence(self):
        """Bắt đầu một lượt kiểm tra token nếu lượt trước đã hoàn tất."""
        if getattr(self, "_token_monitor_suspended", False):
            return

        signing_thread = getattr(self, "_signing_thread", None)
        if signing_thread is not None and signing_thread.isRunning():
            return

        if self._token_check_thread is not None and self._token_check_thread.isRunning():
            return

        thread = QThread()
        worker = _TokenPresenceWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(self._on_token_presence_result)
        worker.error.connect(self._on_token_presence_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_token_presence_worker)

        self._token_check_worker = worker
        self._token_check_thread = thread
        thread.start()

    def _cleanup_token_presence_worker(self):
        self._token_check_worker = None
        self._token_check_thread = None

    def _on_token_presence_result(self, token_found: bool):
        if token_found and not self._usb_token_detected:
            self._usb_token_detected = True
            self.status.showMessage("✓ Đã phát hiện USB ký số", 3000)
        elif not token_found and self._usb_token_detected:
            self._usb_token_detected = False
            self.status.showMessage("✗ USB ký số đã bị rút ra", 3000)

    def _on_token_presence_error(self, message: str):
        if message:
            self.status.showMessage("Không kiểm tra được USB ký số", 3000)
