import os
import sys
import gc
import json

from packages.qt_compat.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
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
    draw_on_pdf,
    insert_image_to_pdf,
    insert_text_to_pdf,
    redact_area,
    save_edits,
    save_edits_as,
    save_edits_quiet,
    select_inserted_object,
    undo_last_edit,
)
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
    export_pdf_to_text, add_page_numbers,
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
        # KhÃ´i phá»¥c AI API key Ä‘Ã£ lÆ°u (náº¿u cÃ³)
        try:
            from app.actions.ai_actions import load_ai_config
            load_ai_config()
        except Exception:
            pass

    def _t(self, key: str, fallback: str) -> str:
        return get_translation(self._language_code, key, fallback)

    def _check_license(self):
        from app.license_dialog import check_license_on_startup
        if not check_license_on_startup(self):
            from packages.qt_compat.QtWidgets import QApplication
            QApplication.quit()

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
            on_recent_file=lambda path: self.open_document(path),
        )
        idx = self.tab_widget.addTab(self._welcome_tab, "Trang chá»§")
        self.tab_widget.tabBar().setTabButton(idx, self.tab_widget.tabBar().ButtonPosition.RightSide, None)
        self._update_tab_bar_visibility()
        # áº¨n sidebar khi á»Ÿ trang chá»§
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

        try:
            viewer.load_pdf(source_path, zoom="100", pagemode="thumbs")
        except Exception as e:
            self._close_tab(index)
            show_warning(self, "KhÃ´ng thá»ƒ má»Ÿ tá»‡p", str(e))
            return False

        self.status.showMessage(f"ÄÃ£ má»Ÿ: {title}", 3000)
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
            if isinstance(path, str) and path.lower().endswith(".pdf") and os.path.isfile(path):
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
        viewer.error_occurred.connect(lambda msg: self.status.showMessage(f"Cáº£nh bÃ¡o: {msg}", 5000))
        viewer.find_not_found.connect(lambda q: show_warning(self, "KhÃ´ng tÃ¬m tháº¥y", f"KhÃ´ng tÃ¬m tháº¥y káº¿t quáº£ cho: \"{q}\""))
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
        # â”€â”€ QToolBar chá»©a ribbon (khÃ´ng hiá»‡n widget riÃªng láº») â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.toolbar = QToolBar("Thanh cÃ´ng cá»¥")
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

        # â”€â”€ Táº¡o táº¥t cáº£ QAction (khÃ´ng add vÃ o toolbar cÅ©) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.act_open   = make("Má»Ÿ tá»‡p",    "folder_open.svg", f"Má»Ÿ tá»‡p ({shortcut_label('Ctrl+O')})",  "Ctrl+O",       lambda: open_file(self))
        self.act_recent = make("Gáº§n Ä‘Ã¢y",   "history.svg",      "Tá»‡p gáº§n Ä‘Ã¢y",                           None,           lambda: show_recent_menu(self))
        self.act_save   = make("LÆ°u",       "save.svg",         f"LÆ°u ({shortcut_label('Ctrl+S')})",     "Ctrl+S",       lambda: save_edits(self))
        self.act_print  = make("In",        "print.svg",        f"In ({shortcut_label('Ctrl+P')})",      "Ctrl+P",       self.print_current_pdf)
        self.act_new_pdf         = make("PDF má»›i",    "file_plus.svg",       f"Táº¡o PDF má»›i ({shortcut_label('Ctrl+N')})",         "Ctrl+N",       lambda: create_new_pdf(self))
        self.act_save_as         = make("LÆ°u má»›i",   "save_as.svg",         f"LÆ°u thÃ nh file má»›i ({shortcut_label('Ctrl+Shift+S')})", "Ctrl+Shift+S", lambda: save_edits_as(self))

        self.act_prev   = make("Trang trÆ°á»›c", "chevron_left.svg",  "Trang trÆ°á»›c (â†)",                   "Left",         lambda: prev_page(self))
        self.act_next   = make("Trang sau",   "chevron_right.svg", "Trang sau (â†’)",                      "Right",        lambda: next_page(self))
        self.act_zoom_in = make("PhÃ³ng to",   "zoom_in.svg",       f"PhÃ³ng to ({shortcut_label('Ctrl+=')})",  "Ctrl+=", lambda: zoom_in(self))
        self.act_zoom_in.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        self.act_zoom_in.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_zoom_out = make("Thu nhá»",   "zoom_out.svg",      f"Thu nhá» ({shortcut_label('Ctrl+-')})",   "Ctrl+-", lambda: zoom_out(self))
        self.act_zoom_out.setShortcuts([QKeySequence("Ctrl+-"), QKeySequence("Ctrl+_")])
        self.act_zoom_out.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_fit    = make("Vá»«a trang",   "fit_page.svg",      f"Vá»«a trang ({shortcut_label('Ctrl+0')})", "Ctrl+0", lambda: zoom_fit(self))

        self.act_highlight    = make("TÃ´ sÃ¡ng",   "highlight.svg",    f"TÃ´ sÃ¡ng ({shortcut_label('Ctrl+H')})", "Ctrl+H", lambda: highlight_text(self))
        self.act_highlight_color = make("MÃ u tÃ´", "highlight.svg", f"Chá»n mÃ u tÃ´ sÃ¡ng ({shortcut_label('Ctrl+Shift+H')})", "Ctrl+Shift+H", self._pick_highlight_color)
        self.act_highlight_color.setIcon(svg_icon("highlight.svg", color="#facc15"))
        self.act_insert_text  = make("ChÃ¨n chá»¯",  "insert_text.svg",  f"ChÃ¨n vÄƒn báº£n vÃ o PDF ({shortcut_label('Ctrl+T')})",   "Ctrl+T",          lambda: insert_text_to_pdf(self))
        self.act_insert_image = make("ChÃ¨n áº£nh",  "insert_image.svg", f"ChÃ¨n áº£nh vÃ o PDF ({shortcut_label('Ctrl+I')})",        "Ctrl+I",          lambda: insert_image_to_pdf(self))
        self.act_draw         = make("Váº½ tá»± do",  "pen.svg",          f"Váº½ tá»± do lÃªn PDF ({shortcut_label('Ctrl+D')})",         "Ctrl+D",          lambda: draw_on_pdf(self))
        self.act_redact       = make("XÃ³a tráº¯ng", "redact.svg",       "Che/táº©y vÃ¹ng ná»™i dung",   None,          lambda: redact_area(self))
        self.act_delete_object= make("XÃ³a Ä‘á»‘i tÆ°á»£ng",   "trash.svg",        "XÃ³a text/áº£nh Ä‘Ã£ chÃ¨n",    None,          lambda: delete_inserted_object(self))
        self.act_select_inserted = make("Chá»n & Xoay","edit_object.svg", "Chá»n text/áº£nh Ä‘Ã£ chÃ¨n â†’ hiá»‡n nÃºt â†» Xoay, âœŽ Sá»­a, Ã— XÃ³a, âœ¥ Di chuyá»ƒn", None,  lambda: select_inserted_object(self))
        self.act_undo         = make("HoÃ n tÃ¡c",  "undo.svg",         f"HoÃ n tÃ¡c ({shortcut_label('Ctrl+Z')})", "Ctrl+Z", lambda: undo_last_edit(self))

        self.act_toggle_sidebar_btn = make("Thumb", "sidebar.svg",   "Danh sÃ¡ch trang (Ctrl+\\)", "Ctrl+\\", self._toggle_sidebar)
        self.act_toggle_sidebar_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_toggle_toc_btn     = make("Má»¥c lá»¥c","history.svg",  "Má»¥c lá»¥c PDF (Ctrl+Alt+T)", "Ctrl+Alt+T", self._toggle_toc)
        self.act_toggle_toc_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self._action_icons[self.act_toggle_toc_btn] = "history.svg"
        self.act_toggle_annotations_btn = make("ChÃº thÃ­ch", "sidebar_panel.svg", "Danh sÃ¡ch chÃº thÃ­ch (Ctrl+Alt+A)", "Ctrl+Alt+A", self._toggle_annotations)
        self.act_toggle_annotations_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)

        self.act_theme_toggle = make("Giao diá»‡n","sun.svg", "Äá»•i chá»§ Ä‘á» sÃ¡ng/tá»‘i", None, self._toggle_theme)
        self.act_theme_toggle.setIcon(svg_icon("sun.svg", color="#f0c050"))
        self.act_fullscreen   = make("ToÃ n mÃ n", "fullscreen.svg", f"ToÃ n mÃ n hÃ¬nh (F11)", "F11", self.toggle_fullscreen)
        self.act_brightness_up   = make("SÃ¡ng hÆ¡n",  "brightness_up.svg",  f"TÄƒng Ä‘á»™ sÃ¡ng ({shortcut_label('Ctrl+Shift+=')})", "Ctrl+Shift+=", lambda: brightness_up(self))
        self.act_brightness_down = make("Tá»‘i hÆ¡n",   "brightness_down.svg", f"Giáº£m Ä‘á»™ sÃ¡ng ({shortcut_label('Ctrl+Shift+-')})", "Ctrl+Shift+-", lambda: brightness_down(self))
        self.act_check_token  = make("USB token", "usb.svg", "Kiá»ƒm tra USB kÃ½ sá»‘", None, lambda: check_token(self))
        self.act_sign         = make("KÃ½ sá»‘",     "usb.svg", "KÃ½ sá»‘ tÃ i liá»‡u",     None, lambda: sign_document(self))
        self.act_sign_file    = make("KÃ½ PFX",    "file_plus.svg",    "KÃ½ báº±ng file PFX/P12", None, lambda: sign_with_pfx(self))
        self.act_signature_field = make("Ã” kÃ½",   "object_plus.svg",  "Táº¡o Ã´ kÃ½ sá»‘ trÃªn PDF", None, lambda: create_signature_field(self))
        self.act_verify_signature = make("Kiá»ƒm tra", "signature_check.svg", "Kiá»ƒm tra tÃ­nh phÃ¡p lÃ½ chá»¯ kÃ½ sá»‘ cá»§a PDF", None, lambda: verify_signed_document(self))
        
        self.act_tts = make("Äá»c sÃ¡ch", "volume.svg", "Äá»c vÄƒn báº£n thÃ nh tiáº¿ng (TTS)", None, lambda: __import__("app.actions.tts_dialog", fromlist=["open_tts_dialog"]).open_tts_dialog(self))

        # â”€â”€ SpinBox trang & zoom â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(9999)
        self.page_spin.setFixedWidth(62)
        self.page_spin.setToolTip("Nháº­p sá»‘ trang rá»“i Enter")
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
        self.zoom_spin.setToolTip("Zoom â€” double-click Ä‘á»ƒ vá» 100%")
        self.zoom_spin.editingFinished.connect(lambda: apply_zoom(self))
        self.zoom_spin.installEventFilter(self)
        self.zoom_spin.setStyleSheet(
            "QSpinBox{background:#1C1C36;color:#E0E8FF;border:1px solid #3A3A60;"
            "border-radius:5px;padding:2px 4px;font-size:12px;}"
            "QSpinBox::up-button,QSpinBox::down-button{width:0;}"
        )

        # â”€â”€ XÃ¢y dá»±ng Ribbon â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from app.ribbon_bar import RibbonBar, RibbonPanel, RibbonGroup, make_action_btn, make_ribbon_btn

        self.ribbon = RibbonBar(self)

        ic = lambda f: svg_icon(f, color=_ic(f))   # shorthand

        # â”€â”€â”€ Tab 0: Tá»‡p & Xem â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p0 = RibbonPanel()

        g_file = RibbonGroup("Tá»‡p")
        g_file.add(make_action_btn(self.act_open,    "Má»Ÿ"))
        g_file.add(make_action_btn(self.act_new_pdf, "Má»›i"))
        g_file.add(make_action_btn(self.act_recent,  "Gáº§n Ä‘Ã¢y"))
        g_file.add(make_action_btn(self.act_save,    "LÆ°u"))
        g_file.add(make_action_btn(self.act_save_as, "LÆ°u má»›i"))
        g_file.add(make_action_btn(self.act_print,   "In"))
        p0.add_group(g_file)

        g_nav = RibbonGroup("Äiá»u hÆ°á»›ng")
        g_nav.add(make_action_btn(self.act_prev, "TrÆ°á»›c"))
        g_nav.add(self.page_spin)
        g_nav.add(self.total_label)
        g_nav.add(make_action_btn(self.act_next, "Sau"))
        p0.add_group(g_nav)

        g_zoom = RibbonGroup("Zoom")
        g_zoom.add(make_action_btn(self.act_zoom_in,  "PhÃ³ng to"))
        g_zoom.add(self.zoom_spin)
        g_zoom.add(make_action_btn(self.act_zoom_out, "Thu nhá»"))
        g_zoom.add(make_action_btn(self.act_fit,      "Vá»«a trang"))
        p0.add_group(g_zoom)

        g_view = RibbonGroup("Giao diá»‡n")
        g_view.add(make_action_btn(self.act_toggle_sidebar_btn, "Thumb"))
        g_view.add(make_action_btn(self.act_toggle_toc_btn,     "Má»¥c lá»¥c"))
        g_view.add(make_action_btn(self.act_theme_toggle,       "Chá»§ Ä‘á»"))
        g_view.add(make_action_btn(self.act_fullscreen,         "ToÃ n mÃ n"))
        g_view.add(make_action_btn(self.act_tts,                "Äá»c sÃ¡ch"))

        self._lang_toolbar_button = QToolButton(self)
        self._lang_toolbar_button.setAutoRaise(True)
        self._lang_toolbar_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._lang_toolbar_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._lang_toolbar_button.setIcon(svg_icon("language.svg", size=28, color=_ic("language.svg")))
        self._lang_toolbar_button.setText(self._t("menu.language", "NgÃ´n ngá»¯"))
        self._lang_toolbar_button.setToolTip(self._t("menu.language", "NgÃ´n ngá»¯"))
        lang_menu = QMenu(self._lang_toolbar_button)
        self._lang_toolbar_button.setMenu(lang_menu)
        self.act_lang_vi_tb = lang_menu.addAction(self._t("lang.vietnamese", "Tiáº¿ng Viá»‡t"))
        self.act_lang_en_tb = lang_menu.addAction(self._t("lang.english", "English"))
        self.act_lang_fr_tb = lang_menu.addAction(self._t("lang.french", "FranÃ§ais"))
        self.act_lang_zh_tb = lang_menu.addAction(self._t("lang.chinese", "ä¸­æ–‡"))
        self.act_lang_ko_tb = lang_menu.addAction(self._t("lang.korean", "í•œêµ­ì–´"))
        self.act_lang_th_tb = lang_menu.addAction(self._t("lang.thai", "à¹„à¸—à¸¢"))
        lang_menu.addSeparator()
        self.act_lang_refresh_tb = lang_menu.addAction(self._t("lang.download", "Táº£i gÃ³i ngÃ´n ngá»¯..."))
        self.act_lang_vi_tb.triggered.connect(lambda: self._set_language("vi"))
        self.act_lang_en_tb.triggered.connect(lambda: self._set_language("en"))
        self.act_lang_fr_tb.triggered.connect(lambda: self._set_language("fr"))
        self.act_lang_zh_tb.triggered.connect(lambda: self._set_language("zh"))
        self.act_lang_ko_tb.triggered.connect(lambda: self._set_language("ko"))
        self.act_lang_th_tb.triggered.connect(lambda: self._set_language("th"))
        self.act_lang_refresh_tb.triggered.connect(lambda: self._refresh_language_pack())
        self._ensure_action_tooltips(lang_menu)
        g_view.add(self._lang_toolbar_button)
        p0.add_group(g_view, add_sep=False)
        p0.add_stretch()

        self.ribbon.add_tab(self._t("tab.file_view", "Tá»‡p & Xem"), p0)

        # â”€â”€â”€ Tab 1: ChÃº thÃ­ch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p1 = RibbonPanel()

        g_mark = RibbonGroup("ÄÃ¡nh dáº¥u")
        _highlight_btn = make_action_btn(self.act_highlight, "TÃ´ sÃ¡ng")
        _highlight_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _highlight_btn.customContextMenuRequested.connect(lambda: self._show_highlight_context_menu())
        g_mark.add(_highlight_btn)
        g_mark.add(make_action_btn(self.act_highlight_color, "MÃ u tÃ´"))
        self.act_underline = make("Gáº¡ch dÆ°á»›i", "underline.svg", f"Gáº¡ch dÆ°á»›i vÄƒn báº£n ({shortcut_label('Ctrl+U')})", "Ctrl+U", lambda: underline_text(self))
        self.act_underline.setIcon(svg_icon("underline.svg", color="#2563eb"))
        self._action_icons[self.act_underline] = "underline.svg"
        g_mark.add(make_action_btn(self.act_underline, "Gáº¡ch dÆ°á»›i"))
        self.act_strikeout = make("Gáº¡ch ngang", "strikeout.svg", f"Gáº¡ch ngang vÄƒn báº£n ({shortcut_label('Ctrl+Shift+X')})", "Ctrl+Shift+X", lambda: strikeout_text(self))
        self.act_strikeout.setIcon(svg_icon("strikeout.svg", color="#dc2626"))
        self._action_icons[self.act_strikeout] = "strikeout.svg"
        g_mark.add(make_action_btn(self.act_strikeout, "Gáº¡ch ngang"))
        _act_comment = make("Ghi chÃº", "insert_text.svg", "ThÃªm ghi chÃº", None, lambda: add_comment(self))
        g_mark.add(make_action_btn(_act_comment, "Ghi chÃº"))
        p1.add_group(g_mark)

        g_edit = RibbonGroup("Chá»‰nh sá»­a")
        g_edit.add(make_action_btn(self.act_insert_text,  "ChÃ¨n chá»¯"))
        g_edit.add(make_action_btn(self.act_insert_image, "ChÃ¨n áº£nh"))
        g_edit.add(make_action_btn(self.act_draw,         "Váº½ tá»± do"))
        g_edit.add(make_action_btn(self.act_redact,       "XÃ³a tráº¯ng"))
        g_edit.add(make_action_btn(self.act_select_inserted, "Chá»n & Xoay"))
        g_edit.add(make_action_btn(self.act_delete_object,"XÃ³a Ä‘á»‘i tÆ°á»£ng"))
        p1.add_group(g_edit)

        g_undo = RibbonGroup("Lá»‹ch sá»­")
        g_undo.add(make_action_btn(self.act_undo, "HoÃ n tÃ¡c"))
        p1.add_group(g_undo, add_sep=False)
        p1.add_stretch()

        self.ribbon.add_tab(self._t("tab.annotate", "ChÃº thÃ­ch"), p1)

        # â”€â”€â”€ Tab 2: Trang â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p2 = RibbonPanel()

        g_rot = RibbonGroup("Xoay / XÃ³a")
        _act_rcw = make("Xoay pháº£i", "rotate_cw.svg",  "Xoay pháº£i 90Â°", None, lambda: rotate_page_cw(self))
        _act_rccw= make("Xoay trÃ¡i", "rotate_ccw.svg", "Xoay trÃ¡i 90Â°", None, lambda: rotate_page_ccw(self))
        _act_del = make("XÃ³a trang", "trash.svg", "XÃ³a trang hiá»‡n táº¡i", None, lambda: delete_current_page(self))
        g_rot.add(make_action_btn(_act_rcw,  "Xoay pháº£i"))
        g_rot.add(make_action_btn(_act_rccw, "Xoay trÃ¡i"))
        g_rot.add(make_action_btn(_act_del,  "XÃ³a trang"))
        p2.add_group(g_rot)

        g_org = RibbonGroup("Tá»• chá»©c")
        _act_merge   = make("GhÃ©p PDF",   "folder_open.svg", "GhÃ©p PDF vÃ o cuá»‘i", None, lambda: merge_pdfs_action(self))
        _act_extract = make("TrÃ­ch xuáº¥t", "save.svg",        "TrÃ­ch xuáº¥t trang",   None, lambda: split_pdf_action(self))
        _act_pgnum   = make("Sá»‘ trang",   "insert_text.svg", "ThÃªm sá»‘ trang",      None, lambda: add_page_numbers(self))
        g_org.add(make_action_btn(_act_merge,   "GhÃ©p PDF"))
        g_org.add(make_action_btn(_act_extract, "TrÃ­ch xuáº¥t"))
        g_org.add(make_action_btn(_act_pgnum,   "Sá»‘ trang"))
        p2.add_group(g_org, add_sep=False)
        p2.add_stretch()

        self.ribbon.add_tab(self._t("tab.page", "Trang"), p2)

        # â”€â”€â”€ Tab 3: Báº£o máº­t & Xuáº¥t â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p3 = RibbonPanel()

        g_sec = RibbonGroup("Báº£o máº­t")
        _act_wm   = make("Watermark",   "pen.svg",      "ThÃªm watermark",     None, lambda: add_watermark(self))
        _act_rmwm = make("XÃ³a watermark","trash.svg",   "XÃ³a watermark vá»«a thÃªm", None, lambda: remove_watermark(self))
        _act_setpw= make("Äáº·t máº­t kháº©u","save.svg",     "Äáº·t máº­t kháº©u PDF",  None, lambda: set_pdf_password(self))
        _act_rmpw = make("XÃ³a máº­t kháº©u","trash.svg",    "XÃ³a máº­t kháº©u PDF",  None, lambda: remove_pdf_password(self))
        _act_comp = make("NÃ©n PDF",     "save.svg",     "NÃ©n / tá»‘i Æ°u PDF",   None, lambda: compress_pdf(self))
        g_sec.add(make_action_btn(_act_wm,    "Watermark"))
        g_sec.add(make_action_btn(_act_rmwm,  "XÃ³a watermark"))
        g_sec.add(make_action_btn(_act_setpw, "Äáº·t máº­t kháº©u"))
        g_sec.add(make_action_btn(_act_rmpw,  "XÃ³a máº­t kháº©u"))
        g_sec.add(make_action_btn(_act_comp,  "NÃ©n PDF"))
        p3.add_group(g_sec)

        g_exp = RibbonGroup("Xuáº¥t")
        _act_word = make("Word",   "save.svg", "Xuáº¥t ra Word (.docx)", None, lambda: export_pdf_to_word(self))
        _act_xl   = make("Excel",  "save.svg", "Xuáº¥t ra Excel (.xlsx)",None, lambda: export_pdf_to_excel(self))
        _act_img  = make("áº¢nh",   "save.svg",  "Xuáº¥t trang ra áº£nh",    None, lambda: export_pages_to_images(self))
        _act_txt  = make("VÄƒn báº£n","save.svg", "Xuáº¥t vÄƒn báº£n (.txt)",  None, lambda: export_pdf_to_text(self))
        g_exp.add(make_action_btn(_act_word, "Word"))
        g_exp.add(make_action_btn(_act_xl,   "Excel"))
        g_exp.add(make_action_btn(_act_img,  "áº¢nh"))
        g_exp.add(make_action_btn(_act_txt,  "VÄƒn báº£n"))
        p3.add_group(g_exp, add_sep=False)
        p3.add_stretch()

        self.ribbon.add_tab(self._t("tab.security_export", "Báº£o máº­t & Xuáº¥t"), p3)

        # â”€â”€â”€ Tab 4: OCR & AI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p4 = RibbonPanel()

        g_ocr = RibbonGroup("OCR")
        from app.actions.ocr import ocr_current_page, ocr_full_document
        _act_ocr1 = make("OCR trang",    "zoom_in.svg",  "OCR trang hiá»‡n táº¡i",  None, lambda: ocr_current_page(self))
        _act_ocr2 = make("OCR tÃ i liá»‡u", "zoom_in.svg",  "OCR toÃ n bá»™ tÃ i liá»‡u",None, lambda: ocr_full_document(self))
        g_ocr.add(make_action_btn(_act_ocr1, "OCR trang"))
        g_ocr.add(make_action_btn(_act_ocr2, "OCR toÃ n bá»™"))
        p4.add_group(g_ocr)

        g_ai = RibbonGroup("AI")
        _act_chat  = make("Chat PDF",    "pen.svg",          "Chat vá»›i PDF (Ctrl+Shift+C)", "Ctrl+Shift+C", lambda: open_chat_dialog(self))
        _act_sum   = make("TÃ³m táº¯t",     "insert_text.svg",  f"TÃ³m táº¯t tÃ i liá»‡u ({shortcut_label(AI_SUMMARIZE_SHORTCUT)})", AI_SUMMARIZE_SHORTCUT, lambda: open_summarize_dialog(self))
        _act_trans = make("Dá»‹ch",        "sidebar.svg",      "Dá»‹ch trang hiá»‡n táº¡i",         "Ctrl+Shift+T", lambda: open_translate_dialog(self))
        _act_srch  = make("TÃ¬m nghÄ©a",   "zoom_in.svg",      "TÃ¬m kiáº¿m theo nghÄ©a",         "Ctrl+Shift+F", lambda: open_search_dialog(self))
        _act_aiset = make("CÃ i Ä‘áº·t AI",  "save.svg",         "CÃ i Ä‘áº·t AI (API Key)",         None,           lambda: open_ai_settings(self))
        g_ai.add(make_action_btn(_act_chat,  "Chat PDF"))
        g_ai.add(make_action_btn(_act_sum,   "TÃ³m táº¯t"))
        g_ai.add(make_action_btn(_act_trans, "Dá»‹ch"))
        g_ai.add(make_action_btn(_act_srch,  "TÃ¬m nghÄ©a"))
        g_ai.add(make_action_btn(_act_aiset, "AI Key"))
        p4.add_group(g_ai, add_sep=False)
        
        g_tts = RibbonGroup("Äá»c SÃ¡ch")
        g_tts.add(make_action_btn(self.act_tts, "Äá»c sÃ¡ch"))
        p4.add_group(g_tts, add_sep=False)
        
        p4.add_stretch()

        self.ribbon.add_tab(self._t("tab.ocr_ai", "OCR & AI"), p4)

        # â”€â”€â”€ Tab 5: KÃ½ sá»‘ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p5 = RibbonPanel()

        g_sign = RibbonGroup("Chá»¯ kÃ½ sá»‘")
        _act_token = make("USB token",  "usb.svg",  "Kiá»ƒm tra USB kÃ½ sá»‘",  None, lambda: check_token(self))
        _act_sign2 = make("KÃ½ sá»‘",      "usb.svg",  "KÃ½ sá»‘ tÃ i liá»‡u",      None, lambda: sign_document(self))
        _act_sign_settings = make("CÃ i Ä‘áº·t", "settings.svg", "CÃ i Ä‘áº·t KÃ½ sá»‘ & TSA", None, lambda: self.open_signing_settings())
        _act_sign_batch = make("KÃ½ lÃ´", "documents.svg", "KÃ½ sá»‘ hÃ ng loáº¡t nhiá»u file", None, lambda: sign_document_batch(self))
        _act_sign3 = make("KÃ½ PFX",     "file_plus.svg",    "KÃ½ báº±ng file PFX/P12", None, lambda: sign_with_pfx(self))
        _act_field = make("Ã” kÃ½",       "object_plus.svg",  "Táº¡o Ã´ kÃ½ sá»‘ trÃªn PDF", None, lambda: create_signature_field(self))
        _act_handw = make("KÃ½ tay/dáº¥u", "pen.svg",  "ChÃ¨n chá»¯ kÃ½ tay, máº«u chá»¯ kÃ½ hoáº·c con dáº¥u PNG", None, lambda: sign_handwritten(self))
        g_sign.add(make_action_btn(_act_token, "Kiá»ƒm tra USB"))
        g_sign.add(make_action_btn(_act_sign2, "KÃ½ sá»‘"))
        g_sign.add(make_action_btn(_act_sign_settings, "CÃ i Ä‘áº·t"))
        g_sign.add(make_action_btn(_act_sign3, "KÃ½ PFX"))
        g_sign.add(make_action_btn(_act_sign_batch, "KÃ½ lÃ´"))
        g_sign.add(make_action_btn(_act_field, "Ã” kÃ½"))
        g_sign.add(make_action_btn(_act_handw, "KÃ½ tay/dáº¥u"))
        p5.add_group(g_sign, add_sep=False)

        g_verify = RibbonGroup("Kiá»ƒm tra")
        g_verify.add(make_action_btn(self.act_verify_signature, "Kiá»ƒm tra"))
        p5.add_group(g_verify, add_sep=False)
        p5.add_stretch()

        # Sync vá»›i self.act_check_token / self.act_sign (dÃ¹ng trong menu)
        self.act_check_token = _act_token
        self.act_sign        = _act_sign2
        self.act_sign_file   = _act_sign3
        self.act_signature_field = _act_field

        self.ribbon.add_tab(self._t("tab.sign", "KÃ½ sá»‘"), p5)

        # â”€â”€ ThÃªm ribbon vÃ o toolbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.ribbon.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toolbar.setMinimumHeight(self.ribbon.EXPANDED_H)
        self.toolbar.setMaximumHeight(self.ribbon.EXPANDED_H)
        self.toolbar.addWidget(self.ribbon)
        # Ãp dá»¥ng Ä‘Ãºng theme ngay tá»« Ä‘áº§u
        self.ribbon.set_theme(is_dark())

        # Cáº­p nháº­t chiá»u cao toolbar khi ribbon thu/má»Ÿ
        def _on_ribbon_collapse(collapsed: bool):
            h = self.ribbon.TABROW_H if collapsed else self.ribbon.EXPANDED_H
            self.toolbar.setMinimumHeight(h)
            self.toolbar.setMaximumHeight(h)
        self.ribbon.collapsed_changed.connect(_on_ribbon_collapse)

    # ------------------------------------------------------------------ #
    #  Print â€” QPrintDialog + PDF engine, KHÃ”NG dÃ¹ng ShellExecute         #
    # ------------------------------------------------------------------ #

    def print_current_pdf(self):
        """Mo xem truoc khi in bang QPrintPreviewDialog."""
        state = self._active_state()
        if not state:
            show_warning(self, "ChÆ°a má»Ÿ tá»‡p", "Vui lÃ²ng má»Ÿ tá»‡p PDF trÆ°á»›c khi in.")
            return

        pdf_path = state.get("source_path")
        if not pdf_path or not os.path.exists(pdf_path):
            show_warning(self, "Lá»—i", "KhÃ´ng tÃ¬m tháº¥y tá»‡p PDF.")
            return

        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        try:
            printer.setResolution(150)
        except Exception:
            pass
        try:
            pdf = get_pdf_engine().open(pdf_path)
            try:
                current_page = 1
                viewer = getattr(self, "viewer", None)
                if viewer and hasattr(viewer, "get_current_page"):
                    current_page = max(1, int(viewer.get_current_page() or 1))
                elif viewer and hasattr(viewer, "_current_page"):
                    current_page = max(1, int(getattr(viewer, "_current_page", 1) or 1))
                page_w_pt, page_h_pt = pdf.page_size(current_page)
                printer.setPageOrientation(self._page_orientation_for_pdf_size(page_w_pt, page_h_pt))
            finally:
                pdf.close()
        except Exception:
            pass

        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Xem truoc khi in")
        try:
            preview.resize(1100, 760)
        except Exception:
            pass
        preview.paintRequested.connect(lambda p: self._do_print_pages(p, pdf_path, show_progress=False))
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

    def _do_print_pages(self, printer: QPrinter, pdf_path: str, show_progress: bool = True):
        """Váº½ tá»«ng trang PDF lÃªn printer â€” cháº¡y trÃªn main thread qua paintRequested.

        Tiáº¿n Ä‘á»™ xá»­ lÃ½ qua QProgressDialog (hiá»‡n sau 1s náº¿u váº«n Ä‘ang cháº¡y) cho
        phÃ©p user há»§y. processEvents() giá»¯a cÃ¡c trang Ä‘á»ƒ UI váº«n pháº£n há»“i
        cho file dÃ y.

        Re-entry guard: QPrintPreviewDialog.paintRequested cÃ³ thá»ƒ fire nhiá»u
        láº§n (zoom/scroll) khi user cÃ²n Ä‘ang thao tÃ¡c. Náº¿u Ä‘ang render dá»Ÿ dang
        rá»“i mÃ  láº¡i fire tiáº¿p, chá»“ng thÃªm QProgressDialog + QPainter.begin trÃªn
        cÃ¹ng printer = crash. Bá» qua re-fire trong khi chÆ°a xong.
        """
        from packages.qt_compat.QtWidgets import QProgressDialog, QApplication

        if getattr(self, "_print_busy", False):
            return
        self._print_busy = True

        try:
            pdf = get_pdf_engine().open(pdf_path)
        except Exception as e:
            self._print_busy = False
            show_warning(self, "Lá»—i in", f"KhÃ´ng má»Ÿ Ä‘Æ°á»£c tÃ i liá»‡u: {e}")
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
            max_render_pixels = 5_000_000 if is_large_job else 12_000_000

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
                show_warning(self, "Lá»—i in", "KhÃ´ng thá»ƒ khá»Ÿi Ä‘á»™ng mÃ¡y in.")
                return

            cancelled = False
            for i, page_num in enumerate(page_list):
                if progress is not None and progress.wasCanceled():
                    cancelled = True
                    break
                if progress is not None:
                    progress.setValue(i)
                    progress.setLabelText(f"Dang in trang {page_num + 1} / {total}...")
                    QApplication.processEvents()
                try:
                    page_w_pt, page_h_pt = pdf.page_size(page_num + 1)
                except Exception:
                    page_w_pt, page_h_pt = 595.0, 842.0
                target_orientation = self._page_orientation_for_pdf_size(page_w_pt, page_h_pt)
                if i > 0:
                    if target_orientation != current_orientation:
                        self._apply_printer_orientation(printer, target_orientation)
                    printer.newPage()
                current_orientation = target_orientation

                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                w = int(page_rect.width())
                h = int(page_rect.height())
                page_pixels = max(1.0, page_w_pt * page_h_pt)
                scale_by_pixels = (max_render_pixels / page_pixels) ** 0.5
                target_scale = min(
                    1.15 if is_large_job else 2.0,
                    max(0.35, scale_by_pixels),
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
                        f"KhÃ´ng Ä‘á»§ bá»™ nhá»› Ä‘á»ƒ render trang {page_num + 1}. "
                        "HÃ£y thá»­ in Ã­t trang hÆ¡n hoáº·c giáº£m cháº¥t lÆ°á»£ng in."
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
                self.status.showMessage("ÄÃ£ há»§y in", 4000)
            elif show_progress:
                self.status.showMessage("âœ“ In hoÃ n táº¥t", 4000)
        except Exception as e:
            show_warning(self, "Lá»—i in", str(e))
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

        self.menu_file = top_menu("menu_file", self._t("menu.file", "Tá»‡p"))
        menu_file = self.menu_file
        menu_file.addAction(self.act_new_pdf)
        menu_file.addAction(self.act_open)
        self.menu_recent = menu_file.addMenu("Má»Ÿ gáº§n Ä‘Ã¢y")
        self.menu_recent.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        self.menu_recent.aboutToShow.connect(self._refresh_recent_menu)
        menu_file.addSeparator()
        menu_file.addAction(self.act_save)
        menu_file.addAction(self.act_print)
        menu_file.addSeparator()

        act_export_word = menu_file.addAction("Xuáº¥t ra Word (.docx)â€¦")
        act_export_word.setIcon(svg_icon("save_as.svg", size=16, color="#5b9cf6"))
        act_export_word.triggered.connect(lambda: export_pdf_to_word(self))

        act_export_excel = menu_file.addAction("Xuáº¥t ra Excel (.xlsx)â€¦")
        act_export_excel.setIcon(svg_icon("extract.svg", size=16, color="#4fc080"))
        act_export_excel.triggered.connect(lambda: export_pdf_to_excel(self))

        act_export_img = menu_file.addAction("Xuáº¥t trang ra áº£nhâ€¦")
        act_export_img.setIcon(svg_icon("insert_image.svg", size=16, color="#b060e0"))
        act_export_img.triggered.connect(lambda: export_pages_to_images(self))

        act_export_txt = menu_file.addAction("Xuáº¥t vÄƒn báº£n ra .txtâ€¦")
        act_export_txt.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        act_export_txt.triggered.connect(lambda: export_pdf_to_text(self))

        menu_file.addSeparator()

        act_file_info = menu_file.addAction("ThÃ´ng tin tá»‡p...")
        act_file_info.setShortcut(QKeySequence("Alt+Return"))
        act_file_info.triggered.connect(lambda: show_file_info(self))
        act_file_info.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))

        act_close_tab = menu_file.addAction("ÄÃ³ng tab")
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(self._close_current_tab)
        act_close_tab.setIcon(svg_icon("fullscreen.svg", size=16, color="#9b9bc0"))

        menu_file.addSeparator()
        act_exit = menu_file.addAction("ThoÃ¡t")
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)

        self.menu_nav = top_menu("menu_nav", self._t("menu.navigate", "Äiá»u hÆ°á»›ng"))
        menu_nav = self.menu_nav
        menu_nav.addAction(self.act_prev)
        menu_nav.addAction(self.act_next)
        act_goto = menu_nav.addAction("Äáº¿n trang...")
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
        act_toggle_toolbar.setText("Thanh cÃ´ng cá»¥")
        act_toggle_toolbar.setShortcut(QKeySequence("Ctrl+B"))
        menu_view.addAction(act_toggle_toolbar)
        act_customize_tb = menu_view.addAction("Tuá»³ chá»‰nh thanh cÃ´ng cá»¥...")
        act_customize_tb.triggered.connect(self._customize_toolbar)
        menu_view.addSeparator()
        menu_view.addAction(self.act_theme_toggle)
        menu_view.addAction(self.act_fullscreen)

        self.menu_tools = top_menu("menu_tools", self._t("menu.tools", "CÃ´ng cá»¥"))
        menu_tools = self.menu_tools

        # ChÃ¨n ná»™i dung
        menu_tools.addAction(self.act_insert_text)
        menu_tools.addAction(self.act_insert_image)
        menu_tools.addAction(self.act_draw)
        menu_tools.addSeparator()

        # Chá»‰nh sá»­a / xÃ³a object Ä‘Ã£ chÃ¨n
        menu_tools.addAction(self.act_select_inserted)
        menu_tools.addAction(self.act_delete_object)
        menu_tools.addAction(self.act_redact)
        menu_tools.addSeparator()

        # LÆ°u chá»‰nh sá»­a
        menu_tools.addAction(self.act_save_as)
        menu_tools.addAction(self.act_undo)
        menu_tools.addSeparator()

        # ChÃº thÃ­ch vÄƒn báº£n
        menu_tools.addAction(self.act_highlight)
        menu_tools.addAction(self.act_highlight_color)
        menu_tools.addAction(self.act_underline)
        menu_tools.addAction(self.act_strikeout)

        act_comment = menu_tools.addAction("ThÃªm ghi chÃº (Note)â€¦")
        act_comment.setIcon(svg_icon("history.svg", size=16, color="#f0a030"))
        act_comment.triggered.connect(lambda: add_comment(self))

        menu_tools.addSeparator()

        act_page_numbers = menu_tools.addAction("ThÃªm sá»‘ trangâ€¦")
        act_page_numbers.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))
        act_page_numbers.triggered.connect(lambda: add_page_numbers(self))

        menu_tools.addSeparator()

        act_find = menu_tools.addAction("TÃ¬m kiáº¿m vÄƒn báº£n...")
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(lambda: search_text(self))
        act_find.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))

        act_find_next = menu_tools.addAction("TÃ¬m tiáº¿p")
        act_find_next.setShortcut(QKeySequence("F3"))
        act_find_next.triggered.connect(lambda: search_next(self))
        act_find_next.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))

        act_find_prev = menu_tools.addAction("TÃ¬m trÆ°á»›c Ä‘Ã³")
        act_find_prev.setShortcut(QKeySequence("Shift+F3"))
        act_find_prev.triggered.connect(lambda: search_previous(self))
        act_find_prev.setIcon(svg_icon("chevron_left.svg", size=16, color="#9b9bc0"))

        menu_tabs = top_menu("menu_tabs", "Tab")
        act_tab_next = menu_tabs.addAction("Tab káº¿ tiáº¿p")
        act_tab_next.setShortcut(QKeySequence("Ctrl+Tab"))
        act_tab_next.triggered.connect(self._activate_next_tab)
        act_tab_prev = menu_tabs.addAction("Tab trÆ°á»›c Ä‘Ã³")
        act_tab_prev.setShortcut(QKeySequence("Ctrl+Shift+Tab"))
        act_tab_prev.triggered.connect(self._activate_prev_tab)
        menu_tabs.addAction(act_close_tab)

        self.menu_pages = top_menu("menu_pages", self._t("menu.page", "Trang"))
        menu_pages = self.menu_pages

        act_rotate_cw = menu_pages.addAction("Xoay pháº£i 90Â°")
        act_rotate_cw.setShortcut(QKeySequence("Ctrl+]"))
        act_rotate_cw.triggered.connect(lambda: rotate_page_cw(self))
        act_rotate_cw.setIcon(svg_icon("rotate_cw.svg", size=16, color="#50b8f0"))

        act_rotate_ccw = menu_pages.addAction("Xoay trÃ¡i 90Â°")
        act_rotate_ccw.setShortcut(QKeySequence("Ctrl+["))
        act_rotate_ccw.triggered.connect(lambda: rotate_page_ccw(self))
        act_rotate_ccw.setIcon(svg_icon("rotate_ccw.svg", size=16, color="#50b8f0"))

        menu_pages.addSeparator()

        act_del_page = menu_pages.addAction("XÃ³a trang nÃ y")
        act_del_page.setShortcut(QKeySequence("Ctrl+Delete"))
        act_del_page.triggered.connect(lambda: delete_current_page(self))
        act_del_page.setIcon(svg_icon("delete_page.svg", size=16, color="#e05050"))

        menu_pages.addSeparator()

        act_merge = menu_pages.addAction("GhÃ©p PDF vÃ o cuá»‘i...")
        act_merge.triggered.connect(lambda: merge_pdfs_action(self))
        act_merge.setIcon(svg_icon("merge_pdf.svg", size=16, color="#4fc080"))

        act_extract = menu_pages.addAction("TrÃ­ch xuáº¥t trang...")
        act_extract.triggered.connect(lambda: split_pdf_action(self))
        act_extract.setIcon(svg_icon("extract.svg", size=16, color="#f07858"))

        self.menu_security = top_menu("menu_security", self._t("menu.security", "Báº£o máº­t"))
        menu_security = self.menu_security

        act_watermark = menu_security.addAction("ThÃªm watermarkâ€¦")
        act_watermark.setIcon(svg_icon("pen.svg", size=16, color="#f0c050"))
        act_watermark.triggered.connect(lambda: add_watermark(self))

        act_remove_watermark = menu_security.addAction("XÃ³a watermarkâ€¦")
        act_remove_watermark.setIcon(svg_icon("trash.svg", size=16, color="#e05050"))
        act_remove_watermark.triggered.connect(lambda: remove_watermark(self))

        menu_security.addSeparator()

        act_set_pw = menu_security.addAction("Äáº·t máº­t kháº©u PDFâ€¦")
        act_set_pw.setIcon(svg_icon("sign_draw.svg", size=16, color="#b060e0"))
        act_set_pw.triggered.connect(lambda: set_pdf_password(self))

        act_rm_pw = menu_security.addAction("XÃ³a máº­t kháº©u PDFâ€¦")
        act_rm_pw.setIcon(svg_icon("trash.svg", size=16, color="#e05050"))
        act_rm_pw.triggered.connect(lambda: remove_pdf_password(self))

        menu_security.addSeparator()

        act_compress = menu_security.addAction("NÃ©n / Tá»‘i Æ°u PDF")
        act_compress.setIcon(svg_icon("save.svg", size=16, color="#4fc080"))
        act_compress.triggered.connect(lambda: compress_pdf(self))

        self.menu_sign = top_menu("menu_sign", self._t("menu.sign", "Chá»¯ kÃ½ sá»‘"))
        menu_sign = self.menu_sign

        act_sign_draw = menu_sign.addAction("KÃ½ tay / chÃ¨n dáº¥u...")
        act_sign_draw.triggered.connect(lambda: sign_handwritten(self))
        act_sign_draw.setIcon(svg_icon("sign_draw.svg", size=16, color="#b060e0"))

        menu_sign.addSeparator()
        menu_sign.addAction(self.act_check_token)
        menu_sign.addAction(self.act_sign)
        menu_sign.addAction(self.act_verify_signature)

        self.menu_ocr = top_menu("menu_ocr", self._t("menu.ocr", "OCR"))
        menu_ocr = self.menu_ocr
        act_ocr_page = menu_ocr.addAction("ðŸ”  OCR trang hiá»‡n táº¡i")
        act_ocr_page.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_ocr_page.triggered.connect(lambda: self._ocr_current_page())

        act_ocr_all = menu_ocr.addAction("ðŸ“„  OCR toÃ n bá»™ tÃ i liá»‡u")
        act_ocr_all.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act_ocr_all.triggered.connect(lambda: self._ocr_full_document())

        self.menu_ai = top_menu("menu_ai", self._t("menu.ai", "AI"))
        menu_ai = self.menu_ai

        act_ai_chat = menu_ai.addAction("ðŸ’¬  Chat vá»›i PDF...")
        act_ai_chat.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_ai_chat.triggered.connect(lambda: open_chat_dialog(self))

        act_ai_summarize = menu_ai.addAction("ðŸ“‹  TÃ³m táº¯t tÃ i liá»‡u...")
        act_ai_summarize.setShortcut(QKeySequence(AI_SUMMARIZE_SHORTCUT))
        act_ai_summarize.triggered.connect(lambda: open_summarize_dialog(self))

        act_ai_translate = menu_ai.addAction("ðŸŒ  Dá»‹ch trang hiá»‡n táº¡i...")
        act_ai_translate.setShortcut(QKeySequence("Ctrl+Shift+T"))
        act_ai_translate.triggered.connect(lambda: open_translate_dialog(self))

        act_ai_search = menu_ai.addAction("ðŸ”Ž  TÃ¬m kiáº¿m theo nghÄ©a...")
        act_ai_search.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_ai_search.triggered.connect(lambda: open_search_dialog(self))

        menu_ai.addSeparator()
        act_ai_settings = menu_ai.addAction("âš™ï¸  CÃ i Ä‘áº·t AI (API Key)...")
        act_ai_settings.triggered.connect(lambda: open_ai_settings(self))

        self.menu_license = top_menu("menu_license", self._t("menu.license", "License"))
        menu_license = self.menu_license

        self.menu_language = top_menu("menu_language", self._t("menu.language", "NgÃ´n ngá»¯"))
        self.act_lang_vi = self.menu_language.addAction(self._t("lang.vietnamese", "Tiáº¿ng Viá»‡t"))
        self.act_lang_en = self.menu_language.addAction(self._t("lang.english", "English"))
        self.act_lang_fr = self.menu_language.addAction(self._t("lang.french", "FranÃ§ais"))
        self.act_lang_zh = self.menu_language.addAction(self._t("lang.chinese", "ä¸­æ–‡"))
        self.act_lang_ko = self.menu_language.addAction(self._t("lang.korean", "í•œêµ­ì–´"))
        self.act_lang_th = self.menu_language.addAction(self._t("lang.thai", "à¹„à¸—à¸¢"))
        self.menu_language.addSeparator()
        self.act_lang_refresh = self.menu_language.addAction(self._t("lang.download", "Táº£i gÃ³i ngÃ´n ngá»¯..."))
        self.act_lang_vi.triggered.connect(lambda: self._set_language("vi"))
        self.act_lang_en.triggered.connect(lambda: self._set_language("en"))
        self.act_lang_fr.triggered.connect(lambda: self._set_language("fr"))
        self.act_lang_zh.triggered.connect(lambda: self._set_language("zh"))
        self.act_lang_ko.triggered.connect(lambda: self._set_language("ko"))
        self.act_lang_th.triggered.connect(lambda: self._set_language("th"))
        self.act_lang_refresh.triggered.connect(lambda: self._refresh_language_pack())
        act_activate = menu_license.addAction("ðŸ”‘  KÃ­ch hoáº¡t / Nháº­p key...")
        act_activate.setShortcut(QKeySequence("Ctrl+Shift+L"))
        act_activate.triggered.connect(lambda: self._open_license_dialog())

        self.menu_help = top_menu("menu_help", self._t("menu.help", "Trá»£ giÃºp"))
        menu_help = self.menu_help
        act_shortcuts = menu_help.addAction("Xem phÃ­m táº¯t")
        act_shortcuts.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        act_shortcuts.triggered.connect(self._show_shortcuts_hint)

        act_check_update = menu_help.addAction("Kiá»ƒm tra cáº­p nháº­t...")
        act_check_update.triggered.connect(self._check_for_update)

        act_audit_log = menu_help.addAction("ðŸ“‹  Nháº­t kÃ½ hoáº¡t Ä‘á»™ng...")
        act_audit_log.triggered.connect(self._show_audit_log)

        menu_help.addSeparator()
        act_about = menu_help.addAction("Giá»›i thiá»‡u 3T Reader...")
        act_about.triggered.connect(self._show_about)
        act_about.setIcon(app_logo_icon(16))

        for action in (
            self.act_open, self.act_new_pdf, self.act_recent,
            self.act_insert_text, self.act_insert_image, self.act_select_inserted,
            self.act_draw, self.act_redact, self.act_delete_object,
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

        title = meta.get("filename") or os.path.basename(state["display_path"])
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
            show_warning(self, "ChÆ°a cÃ³ tá»‡p", "KhÃ´ng tÃ¬m tháº¥y file PDF Ä‘á»ƒ kiá»ƒm tra chá»¯ kÃ½.")
            return
        try:
            if hasattr(self, "status"):
                self.status.showMessage("Äang kiá»ƒm tra chá»¯ kÃ½ sá»‘...", 2000)
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
                
                dlg_prog = QProgressDialog("Äang quÃ©t tÃ¬m USB kÃ½ sá»‘...", None, 0, 0, self)
                dlg_prog.setWindowTitle("Vui lÃ²ng chá»")
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
            show_warning(self, "Lá»—i kiá»ƒm tra chá»¯ kÃ½", str(exc))

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
        # ThÃ´ng bÃ¡o chat dialog khi Ä‘á»•i tÃ i liá»‡u
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
            self.file_label.setText("ChÆ°a má»Ÿ tá»‡p")
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
        self.file_label.setText(f"Má»Ÿ: {display_name}")
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
                        "ChÆ°a lÆ°u xong chÃº thÃ­ch",
                        "Má»™t sá»‘ thay Ä‘á»•i chÃº thÃ­ch chÆ°a lÆ°u xong. Vui lÃ²ng Ä‘á»£i vÃ i giÃ¢y rá»“i Ä‘Ã³ng tab láº¡i.",
                    )
                    return False
            except Exception as exc:
                QMessageBox.warning(self, "ChÆ°a lÆ°u xong chÃº thÃ­ch", str(exc))
                return False
        edit_state = state.get("_pdf_edit_state") if state else None
        if self._has_unsaved_changes(state) and edit_state and edit_state.get("ops"):
            title = self.tab_widget.tabText(index) or "tÃ i liá»‡u"
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("ChÆ°a lÆ°u thay Ä‘á»•i")
            box.setText(f"Tá»‡p '{title}' cÃ³ thay Ä‘á»•i chÆ°a lÆ°u.")
            box.setInformativeText("Báº¡n muá»‘n lÆ°u trÆ°á»›c khi Ä‘Ã³ng khÃ´ng?")

            save_btn = box.addButton("LÆ°u", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("KhÃ´ng lÆ°u", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = box.addButton("Há»§y", QMessageBox.ButtonRole.RejectRole)
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
                show_warning(self, "TÃ¡c vá»¥ Ä‘ang cháº¡y", "AI chat Ä‘ang xá»­ lÃ½ tÃ i liá»‡u nÃ y. HÃ£y chá» tÃ¡c vá»¥ hoÃ n táº¥t rá»“i Ä‘Ã³ng tab.")
                return False

        search = getattr(self, "_ai_search_dialog", None)
        if search is not None:
            search_busy = any(
                dialog_task_running(search, thread_attr=attr)
                for attr in ("_load_index_thread", "_build_index_thread", "_search_thread")
            )
            if search_busy and getattr(search, "_pdf_path", None) in related_paths:
                show_warning(self, "TÃ¡c vá»¥ Ä‘ang cháº¡y", "AI search Ä‘ang dá»±ng index hoáº·c tÃ¬m kiáº¿m trÃªn tÃ i liá»‡u nÃ y. HÃ£y chá» tÃ¡c vá»¥ hoÃ n táº¥t rá»“i Ä‘Ã³ng tab.")
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
            self, "PhÃ­m táº¯t",
            f"{s('Ctrl+O')}: Má»Ÿ tá»‡p\n"
            f"{s('Ctrl+W')}: ÄÃ³ng tab\n"
            f"{s('Ctrl+Tab')}: Tab káº¿ tiáº¿p\n"
            f"{s('Ctrl+Shift+Tab')}: Tab trÆ°á»›c Ä‘Ã³\n"
            f"{s('Ctrl+F')}: TÃ¬m kiáº¿m vÄƒn báº£n\n"
            "F3 / Shift+F3: TÃ¬m tiáº¿p / tÃ¬m trÆ°á»›c Ä‘Ã³\n"
            f"{s('Ctrl+S')}: LÆ°u\n"
            f"{s('Ctrl+P')}: In\n"
            f"{s('Ctrl+0')}: Vá»«a trang\n"
            f"{s('Ctrl+-')} / {s('Ctrl+=')} : Thu nhá» / phÃ³ng to\n"
            f"{fullscreen_shortcut_hint()}: ToÃ n mÃ n hÃ¬nh",
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

        # Kiá»ƒm tra thread Python Ä‘ang cháº¡y (thay QThread Ä‘á»ƒ trÃ¡nh bug PySide6 6.11+Python3.14)
        if self._update_check_thread is not None and self._update_check_thread.is_alive():
            if show_errors:
                self._pending_manual_update_check = True
                self.status.showMessage("Äang kiá»ƒm tra cáº­p nháº­t ná»n, sáº½ kiá»ƒm tra láº¡i ngay sau Ä‘Ã³...", 5000)
            return

        self._pending_manual_update_check = False
        self.status.showMessage("Äang kiá»ƒm tra cáº­p nháº­t...", 0 if show_errors else 3000)

        # Worker váº«n lÃ  QObject â€” nhÆ°ng KHÃ”NG moveToThread.
        # Worker á»Ÿ main thread, Python thread chá»‰ gá»i worker.run().
        # Signal emit tá»« Python thread sáº½ Ä‘Æ°á»£c Qt tá»± queue vá» main thread (thread-safe).
        worker = UpdateCheckWorker(VPS_LICENSE_BASE_URL, APP_VERSION, UPDATE_CHANNEL)
        worker.available.connect(self._show_update_dialog)
        if show_up_to_date:
            worker.up_to_date.connect(self._on_update_up_to_date)
        worker.error.connect(lambda msg: self._on_update_check_error(msg, show_errors))
        worker.finished.connect(lambda: QTimer.singleShot(0, self._cleanup_update_check_worker))

        self._update_check_worker = worker

        # DÃ¹ng Python thread â€” KHÃ”NG dÃ¹ng QThread Ä‘á»ƒ trÃ¡nh QObjectWrapper destructor bug
        def _run_and_cleanup():
            try:
                worker.run()
            except Exception:
                pass

        t = _threading.Thread(target=_run_and_cleanup, daemon=True, name="update-check")
        self._update_check_thread = t
        t.start()

    def _auto_check_update(self):
        """Silent check lÃºc khá»Ÿi Ä‘á»™ng â€” chá»‰ hiá»‡n dialog náº¿u cÃ³ báº£n má»›i."""
        self._start_update_check(show_up_to_date=False, show_errors=False)

    def _check_for_update(self):
        """Check thá»§ cÃ´ng tá»« menu â€” luÃ´n hiá»‡n káº¿t quáº£."""
        self._start_update_check(show_up_to_date=True, show_errors=True)

    def _show_update_dialog(self, info):
        from app.update_dialog import UpdateDialog
        dlg = UpdateDialog(self, info)
        dlg.exec()

    def _on_update_up_to_date(self, info):
        from app.dialogs import show_info
        from app.version import APP_VERSION

        latest = getattr(info, "latest_version", "") or APP_VERSION
        self.status.showMessage("Báº¡n Ä‘ang dÃ¹ng phiÃªn báº£n má»›i nháº¥t.", 4000)
        show_info(self, "ÄÃ£ cáº­p nháº­t", f"PhiÃªn báº£n {APP_VERSION} lÃ  má»›i nháº¥t.\nLatest server: {latest}")

    def _on_update_check_error(self, message: str, show_warning_dialog: bool):
        safe_message = message or "KhÃ´ng thá»ƒ kiá»ƒm tra cáº­p nháº­t."
        self.status.showMessage(f"KhÃ´ng kiá»ƒm tra Ä‘Æ°á»£c cáº­p nháº­t: {safe_message}", 7000)
        if show_warning_dialog:
            self.raise_()
            self.activateWindow()
            QMessageBox.warning(self, "KhÃ´ng kiá»ƒm tra Ä‘Æ°á»£c cáº­p nháº­t", safe_message)

    def _set_language(self, code: str):
        code = code if code in ("vi", "en", "fr", "zh", "ko", "th") else "vi"
        set_selected_language(code)
        self._language_code = code
        self._apply_language_texts()
        self.status.showMessage(f"ÄÃ£ chuyá»ƒn sang ngÃ´n ngá»¯: {code}", 3000)

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
                "Táº£i gÃ³i ngÃ´n ngá»¯",
                "ChÆ°a chá»n gÃ³i ngÃ´n ngá»¯ nÃ o Ä‘á»ƒ táº£i.",
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
            self.status.showMessage(f"ÄÃ£ táº£i xong gÃ³i ngÃ´n ngá»¯: {', '.join(successes)}", 5000)
            QMessageBox.information(
                self,
                "Táº£i gÃ³i ngÃ´n ngá»¯",
                "ÄÃ£ táº£i xong:\n" + "\n".join(f"â€¢ {name}" for name in successes),
            )
            return

        if successes or failures:
            message = []
            if successes:
                message.append("ÄÃ£ táº£i:\n" + "\n".join(f"â€¢ {name}" for name in successes))
            if failures:
                message.append("KhÃ´ng táº£i Ä‘Æ°á»£c:\n" + "\n".join(f"â€¢ {name}" for name in failures))
            self.raise_()
            self.activateWindow()
            QMessageBox.warning(self, "Táº£i gÃ³i ngÃ´n ngá»¯", "\n\n".join(message))

    def _apply_language_texts(self):
        def _set_action(attr: str, key: str, fallback: str):
            action = getattr(self, attr, None)
            if action is not None:
                action.setText(self._t(key, fallback))

        if hasattr(self, "menu_file"):
            self.menu_file.setTitle(self._t("menu.file", "Tá»‡p"))
        if hasattr(self, "menu_nav"):
            self.menu_nav.setTitle(self._t("menu.navigate", "Äiá»u hÆ°á»›ng"))
        if hasattr(self, "menu_view"):
            self.menu_view.setTitle(self._t("menu.view", "Xem"))
        if hasattr(self, "menu_tools"):
            self.menu_tools.setTitle(self._t("menu.tools", "CÃ´ng cá»¥"))
        if hasattr(self, "menu_pages"):
            self.menu_pages.setTitle(self._t("menu.page", "Trang"))
        if hasattr(self, "menu_security"):
            self.menu_security.setTitle(self._t("menu.security", "Báº£o máº­t"))
        if hasattr(self, "menu_sign"):
            self.menu_sign.setTitle(self._t("menu.sign", "Chá»¯ kÃ½ sá»‘"))
        if hasattr(self, "menu_ocr"):
            self.menu_ocr.setTitle(self._t("menu.ocr", "OCR"))
        if hasattr(self, "menu_ai"):
            self.menu_ai.setTitle(self._t("menu.ai", "AI"))
        if hasattr(self, "menu_license"):
            self.menu_license.setTitle(self._t("menu.license", "License"))
        if hasattr(self, "menu_language"):
            self.menu_language.setTitle(self._t("menu.language", "NgÃ´n ngá»¯"))
        if hasattr(self, "act_lang_vi"):
            self.act_lang_vi.setText(self._t("lang.vietnamese", "Tiáº¿ng Viá»‡t"))
        if hasattr(self, "act_lang_en"):
            self.act_lang_en.setText(self._t("lang.english", "English"))
        if hasattr(self, "act_lang_fr"):
            self.act_lang_fr.setText(self._t("lang.french", "FranÃ§ais"))
        if hasattr(self, "act_lang_zh"):
            self.act_lang_zh.setText(self._t("lang.chinese", "ä¸­æ–‡"))
        if hasattr(self, "act_lang_ko"):
            self.act_lang_ko.setText(self._t("lang.korean", "í•œêµ­ì–´"))
        if hasattr(self, "act_lang_th"):
            self.act_lang_th.setText(self._t("lang.thai", "à¹„à¸—à¸¢"))
        if hasattr(self, "act_lang_refresh"):
            self.act_lang_refresh.setText(self._t("lang.download", "Táº£i gÃ³i ngÃ´n ngá»¯..."))
        if hasattr(self, "_lang_toolbar_button"):
            self._lang_toolbar_button.setText(self._t("menu.language", "NgÃ´n ngá»¯"))
            self._lang_toolbar_button.setToolTip(self._t("menu.language", "NgÃ´n ngá»¯"))
        if hasattr(self, "act_lang_vi_tb"):
            self.act_lang_vi_tb.setText(self._t("lang.vietnamese", "Tiáº¿ng Viá»‡t"))
        if hasattr(self, "act_lang_en_tb"):
            self.act_lang_en_tb.setText(self._t("lang.english", "English"))
        if hasattr(self, "act_lang_fr_tb"):
            self.act_lang_fr_tb.setText(self._t("lang.french", "FranÃ§ais"))
        if hasattr(self, "act_lang_zh_tb"):
            self.act_lang_zh_tb.setText(self._t("lang.chinese", "ä¸­æ–‡"))
        if hasattr(self, "act_lang_ko_tb"):
            self.act_lang_ko_tb.setText(self._t("lang.korean", "í•œêµ­ì–´"))
        if hasattr(self, "act_lang_th_tb"):
            self.act_lang_th_tb.setText(self._t("lang.thai", "à¹„à¸—à¸¢"))
        if hasattr(self, "act_lang_refresh_tb"):
            self.act_lang_refresh_tb.setText(self._t("lang.download", "Táº£i gÃ³i ngÃ´n ngá»¯..."))
        if hasattr(self, "menu_help"):
            self.menu_help.setTitle(self._t("menu.help", "Trá»£ giÃºp"))
        _set_action("act_open", "action.open", "Má»Ÿ tá»‡p")
        _set_action("act_new_pdf", "action.new_pdf", "PDF má»›i")
        _set_action("act_recent", "action.recent", "Gáº§n Ä‘Ã¢y")
        _set_action("act_save", "action.save", "LÆ°u")
        _set_action("act_save_as", "action.save_as", "LÆ°u má»›i")
        _set_action("act_print", "action.print", "In")
        _set_action("act_prev", "action.prev", "Trang trÆ°á»›c")
        _set_action("act_next", "action.next", "Trang sau")
        _set_action("act_zoom_in", "action.zoom_in", "PhÃ³ng to")
        _set_action("act_zoom_out", "action.zoom_out", "Thu nhá»")
        _set_action("act_fit", "action.fit", "Vá»«a trang")
        _set_action("act_theme_toggle", "action.theme", "Giao diá»‡n")
        _set_action("act_fullscreen", "action.fullscreen", "ToÃ n mÃ n")
        _set_action("act_highlight", "action.highlight", "TÃ´ sÃ¡ng")
        _set_action("act_insert_text", "action.insert_text", "ChÃ¨n chá»¯")
        _set_action("act_insert_image", "action.insert_image", "ChÃ¨n áº£nh")
        _set_action("act_draw", "action.draw", "Váº½ tá»± do")
        _set_action("act_redact", "action.redact", "XÃ³a tráº¯ng")
        _set_action("act_delete_object", "action.delete_object", "XÃ³a Ä‘á»‘i tÆ°á»£ng")
        _set_action("act_highlight_color", "action.highlight_color", "MÃ u tÃ´")
        _set_action("act_underline", "action.underline", "Gáº¡ch dÆ°á»›i")
        _set_action("act_strikeout", "action.strikeout", "Gáº¡ch ngang")
        _set_action("act_toggle_annotations_btn", "action.annotations", "ChÃº thÃ­ch")
        _set_action("act_select_inserted", "action.select_object", "Chá»n & Xoay")
        _set_action("act_undo", "action.undo", "HoÃ n tÃ¡c")
        _set_action("act_sign", "action.sign", "KÃ½ sá»‘")
        _set_action("act_signature_field", "action.signature_field", "Ã” kÃ½")
        _set_action("act_verify_signature", "action.verify", "Kiá»ƒm tra")
        _set_action("act_tts", "action.tts", "Äá»c sÃ¡ch")
        if hasattr(self, "ribbon"):
            self.ribbon.set_tab_text(0, self._t("tab.file_view", "Tá»‡p & Xem"))
            self.ribbon.set_tab_text(1, self._t("tab.annotate", "ChÃº thÃ­ch"))
            self.ribbon.set_tab_text(2, self._t("tab.page", "Trang"))
            self.ribbon.set_tab_text(3, self._t("tab.security_export", "Báº£o máº­t & Xuáº¥t"))
            self.ribbon.set_tab_text(4, self._t("tab.ocr_ai", "OCR & AI"))
            self.ribbon.set_tab_text(5, self._t("tab.sign", "KÃ½ sá»‘"))
        if hasattr(self, "file_label") and self.file_label.text() == "ChÆ°a má»Ÿ tá»‡p":
            self.file_label.setText(self._t("status.no_file", "ChÆ°a má»Ÿ tá»‡p"))
        if hasattr(self, "page_label") and self.page_label.text() == "Trang: -":
            self.page_label.setText(self._t("status.page", "Trang: -"))

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
        self.status.showMessage("ÄÃ£ xÃ³a danh sÃ¡ch tá»‡p gáº§n Ä‘Ã¢y", 3000)

    

    def open_signing_settings(self):
        from packages.qt_compat.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout, QComboBox, QFileDialog, QGroupBox, QInputDialog, QCheckBox
        from app.config import VPS_LICENSE_BASE_URL
        import json
        import os
        import uuid
        
        dlg = QDialog(self)
        dlg.setWindowTitle("CÃ i Ä‘áº·t KÃ½ sá»‘ & TSA")
        dlg.resize(500, 450)
        
        layout = QVBoxLayout(dlg)
        
        # TSA Settings (Global)
        layout.addWidget(QLabel("Cáº¥u hÃ¬nh Dáº¥u Thá»i Gian (TSA):"))
        tsa_mode_combo = QComboBox(dlg)
        tsa_mode_combo.addItem("Theo há»‡ thá»‘ng mÃ¡y (Máº·c Ä‘á»‹nh)", "system")
        tsa_mode_combo.addItem("Theo mÃ¡y chá»§ á»©ng dá»¥ng (3T Company)", "server")
        tsa_mode_combo.addItem("NgÆ°á»i dÃ¹ng tá»± cáº¥u hÃ¬nh", "custom")
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
        grp = QGroupBox("Cáº¥u hÃ¬nh áº¢nh Chá»¯ kÃ½ (Profiles)", dlg)
        grp_layout = QVBoxLayout(grp)
        layout.addWidget(grp)
        
        prof_layout = QHBoxLayout()
        prof_combo = QComboBox(dlg)
        btn_add_prof = QPushButton("+", dlg)
        btn_add_prof.setFixedWidth(30)
        btn_del_prof = QPushButton("x", dlg)
        btn_del_prof.setFixedWidth(30)
        
        prof_layout.addWidget(QLabel("Máº«u chá»¯ kÃ½:"))
        prof_layout.addWidget(prof_combo, 1)
        prof_layout.addWidget(btn_add_prof)
        prof_layout.addWidget(btn_del_prof)
        grp_layout.addLayout(prof_layout)
        
        img_layout = QHBoxLayout()
        img_input = QLineEdit(dlg)
        img_input.setPlaceholderText("ÄÆ°á»ng dáº«n file áº£nh (.png, .jpg)...")
        img_btn = QPushButton("Chá»n áº£nh", dlg)
        img_layout.addWidget(img_input)
        img_layout.addWidget(img_btn)
        grp_layout.addLayout(img_layout)
        
        # State variables
        profiles_data = []
        active_prof_id = ""
        
        def browse_img():
            path, _ = QFileDialog.getOpenFileName(dlg, "Chá»n áº£nh chá»¯ kÃ½", "", "Images (*.png *.jpg *.jpeg)")
            if path:
                img_input.setText(path)
                idx = prof_combo.currentIndex()
                if idx >= 0:
                    prof_id = prof_combo.itemData(idx)
                    for p in profiles_data:
                        if p["id"] == prof_id:
                            p["path"] = path
                            
        img_btn.clicked.connect(browse_img)
        
        grp_layout.addWidget(QLabel("Kiá»ƒu hiá»ƒn thá»‹ áº£nh:"))
        mode_combo = QComboBox(dlg)
        mode_combo.addItem("áº¢nh bÃªn trÃ¡i, Text bÃªn pháº£i", "left")
        mode_combo.addItem("Chá»‰ hiá»ƒn thá»‹ áº£nh (KhÃ´ng cÃ³ Text)", "only")
        mode_combo.addItem("áº¢nh lÃ m ná»n má» (Watermark)", "bg")
        grp_layout.addWidget(mode_combo)
        
        # LTV Settings
        layout.addSpacing(10)
        ltv_check = QCheckBox("Báº­t XÃ¡c thá»±c DÃ i háº¡n (LTV - Cáº§n káº¿t ná»‘i máº¡ng Ä‘á»ƒ táº£i CRL/OCSP)")
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
            profiles_data = [{"id": p_id, "name": "Máº·c Ä‘á»‹nh", "path": old_path, "mode": old_mode}]
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
            name, ok = QInputDialog.getText(dlg, "ThÃªm Máº«u Má»›i", "TÃªn máº«u chá»¯ kÃ½:")
            if ok and name.strip():
                save_current_prof_state()
                p_id = uuid.uuid4().hex
                profiles_data.append({"id": p_id, "name": name.strip(), "path": "", "mode": "left"})
                nonlocal active_prof_id
                active_prof_id = p_id
                reload_combo()
                
        def on_del_prof():
            if len(profiles_data) <= 1:
                QMessageBox.warning(dlg, "Lá»—i", "Pháº£i cÃ³ Ã­t nháº¥t 1 máº«u chá»¯ kÃ½.")
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
        btn_save = QPushButton("LÆ°u cáº¥u hÃ¬nh", dlg)
        btn_save.clicked.connect(save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        dlg.exec()

    def _show_pdf_context_menu(self, viewer, pos):
        from packages.qt_compat.QtWidgets import QMenu
        from app.actions.sign import sign_document
        from app.actions.edit import insert_text_to_pdf, insert_image_to_pdf
        
        menu = QMenu(self)
        
        act_sign = menu.addAction("âœï¸ KÃ½ sá»‘ táº¡i vá»‹ trÃ­ nÃ y")
        act_sign.triggered.connect(lambda: sign_document(self))
        
        act_text = menu.addAction("ðŸ“ ChÃ¨n vÄƒn báº£n táº¡i Ä‘Ã¢y")
        act_text.triggered.connect(lambda: insert_text_to_pdf(self))
        
        act_img = menu.addAction("ðŸ–¼ï¸ ChÃ¨n áº£nh táº¡i Ä‘Ã¢y")
        act_img.triggered.connect(lambda: insert_image_to_pdf(self))
        
        menu.addSeparator()
        
        act_add_page = menu.addAction("ðŸ“„ ThÃªm trang tráº¯ng phÃ­a sau")
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
            act_copy = menu.addAction("Sao chÃ©p Ä‘Æ°á»ng dáº«n file")
            from packages.qt_compat.QtWidgets import QApplication
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(os.path.abspath(source_path)))

            act_open_dir = menu.addAction("Má»Ÿ thÆ° má»¥c chá»©a file")
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

        act_close = menu.addAction("ÄÃ³ng tab")
        act_close.triggered.connect(lambda: self._close_tab(index))

        act_close_others = menu.addAction("ÄÃ³ng tab khÃ¡c")
        act_close_others.setEnabled(self.tab_widget.count() > 1)
        act_close_others.triggered.connect(lambda: self._close_other_tabs(index))

        act_close_right = menu.addAction("ÄÃ³ng tab bÃªn pháº£i")
        act_close_right.setEnabled(index < self.tab_widget.count() - 1)
        act_close_right.triggered.connect(lambda: self._close_tabs_right(index))

        menu.addSeparator()
        act_next = menu.addAction("Chuyá»ƒn sang tab káº¿ tiáº¿p")
        act_next.triggered.connect(self._activate_next_tab)
        act_prev = menu.addAction("Chuyá»ƒn sang tab trÆ°á»›c Ä‘Ã³")
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
            "VÃ ng": "#facc15",
            "Xanh lÃ¡": "#22c55e",
            "Xanh dÆ°Æ¡ng": "#38bdf8",
            "Há»“ng": "#f472b6",
            "Cam": "#fb923c",
        }
        for label, hex_color in presets.items():
            action = menu.addAction(label)
            action.setIcon(svg_icon("highlight.svg", color=hex_color))
            action.triggered.connect(lambda _checked=False, c=hex_color: self._set_highlight_color(QColor(c)))
        menu.addSeparator()
        custom = menu.addAction("MÃ u khÃ¡c...")
        custom.triggered.connect(self._pick_custom_highlight_color)
        button = self.toolbar.widgetForAction(self.act_highlight) if hasattr(self, "toolbar") else None
        if button:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            menu.exec(self.cursor().pos())

    def _pick_highlight_color(self):
        presets = {
            "VÃ ng": "#facc15",
            "Xanh lÃ¡": "#22c55e",
            "Xanh dÆ°Æ¡ng": "#38bdf8",
            "Há»“ng": "#f472b6",
            "Cam": "#fb923c",
        }
        menu = QMenu(self)
        for label, hex_color in presets.items():
            action = menu.addAction(label)
            action.setIcon(svg_icon("highlight.svg", color=hex_color))
            action.triggered.connect(lambda _checked=False, c=hex_color: self._set_highlight_color(QColor(c)))
        menu.addSeparator()
        custom = menu.addAction("MÃ u khÃ¡c...")
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
        picked = QColorDialog.getColor(color, self, "Chá»n mÃ u tÃ´ sÃ¡ng")
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
            self.act_highlight_color.setToolTip("MÃ u tÃ´ sÃ¡ng hiá»‡n táº¡i: " + picked.name())
        if hasattr(self, "status"):
            self.status.showMessage("ÄÃ£ Ä‘á»•i mÃ u tÃ´ sÃ¡ng.", 1800)

    def _toggle_theme(self):
        toggle_theme()
        self._refresh_icons()
        self.ribbon.set_theme(is_dark())
        if is_dark():
            self.act_theme_toggle.setIcon(svg_icon("sun.svg", color="#f0c050"))
            self.act_theme_toggle.setText("â˜€ SÃ¡ng")
            self.act_theme_toggle.setToolTip("Chuyá»ƒn sang cháº¿ Ä‘á»™ sÃ¡ng (hiá»‡n: Tá»‘i)")
        else:
            self.act_theme_toggle.setIcon(svg_icon("moon.svg", color="#6c63ff"))
            self.act_theme_toggle.setText("ðŸŒ™ Tá»‘i")
            self.act_theme_toggle.setToolTip("Chuyá»ƒn sang cháº¿ Ä‘á»™ tá»‘i (hiá»‡n: SÃ¡ng)")
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
        if event.key() == Qt.Key.Key_Escape and self.search_panel.isVisible():
            self.hide_search_panel()
            return
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
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
            if any(u.toLocalFile().lower().endswith(".pdf") for u in urls):
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
        pdf_files = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(".pdf")]
        for path in pdf_files:
            if os.path.isfile(path):
                self.open_document(path)
        if pdf_files:
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
                    "Äang kÃ½ sá»‘",
                    "Vui lÃ²ng chá» thao tÃ¡c kÃ½ hiá»‡n táº¡i hoÃ n táº¥t rá»“i hÃ£y Ä‘Ã³ng á»©ng dá»¥ng.",
                )
                event.ignore()
                return
            else:
                signing_thread.join(timeout=3.0)
                if signing_thread.is_alive():
                    self._closing = False
                    QMessageBox.warning(
                        self,
                        "Äang kÃ½ sá»‘",
                        "Vui lÃ²ng chá» thao tÃ¡c kÃ½ hiá»‡n táº¡i hoÃ n táº¥t rá»“i hÃ£y Ä‘Ã³ng á»©ng dá»¥ng.",
                    )
                    event.ignore()
                    return

        if self._token_monitor_timer is not None:
            self._token_monitor_timer.stop()

        if self._token_check_thread is not None and getattr(self._token_check_thread, "is_alive", lambda: False)():
            # Python threading.Thread doesn't have quit(). Just wait briefly.
            self._token_check_thread.join(timeout=1.0)

        queue = getattr(self, "_annotation_op_queue", None)
        if queue is not None or has_pending_annotations(self):
            try:
                flush_all = getattr(queue, "flush_all", None)
                ok = flush_all() if callable(flush_all) else queue.flush()
                if not ok:
                    self._closing = False
                    QMessageBox.warning(
                        self,
                        "ChÆ°a lÆ°u xong chÃº thÃ­ch",
                        "Má»™t sá»‘ thay Ä‘á»•i chÃº thÃ­ch chÆ°a lÆ°u xong. Vui lÃ²ng Ä‘á»£i vÃ i giÃ¢y rá»“i thoÃ¡t láº¡i.",
                    )
                    event.ignore()
                    return
            except Exception as exc:
                self._closing = False
                QMessageBox.warning(self, "ChÆ°a lÆ°u xong chÃº thÃ­ch", str(exc))
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
        """Theo dÃµi USB token trong ná»n mÃ  khÃ´ng khÃ³a luá»“ng UI."""
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
        if thread is not None and getattr(thread, "is_alive", lambda: False)():
            thread.join(timeout=1.5)

    def _resume_token_monitor(self):
        """Resume USB presence checks after signing finishes."""
        self._token_monitor_suspended = False
        timer = self._token_monitor_timer
        if timer is not None and not timer.isActive():
            timer.start()

    def _check_token_presence(self):
        """Báº¯t Ä‘áº§u má»™t lÆ°á»£t kiá»ƒm tra token náº¿u lÆ°á»£t trÆ°á»›c Ä‘Ã£ hoÃ n táº¥t."""
        if getattr(self, "_token_monitor_suspended", False):
            return

        signing_thread = getattr(self, "_signing_thread", None)
        if signing_thread is not None and (getattr(signing_thread, "isRunning", lambda: False)() or getattr(signing_thread, "is_alive", lambda: False)()):
            return

        if self._token_check_thread is not None and getattr(self._token_check_thread, "is_alive", lambda: False)():
            return

        import threading
        worker = _TokenPresenceWorker()
        worker.result.connect(self._on_token_presence_result)
        worker.error.connect(self._on_token_presence_error)
        worker.finished.connect(self._cleanup_token_presence_worker)

        self._token_check_worker = worker
        self._token_check_thread = threading.Thread(target=worker.run, daemon=True)
        self._token_check_thread.start()

    def _cleanup_token_presence_worker(self):
        self._token_check_worker = None
        self._token_check_thread = None

    def _on_token_presence_result(self, token_found: bool):
        if token_found and not self._usb_token_detected:
            self._usb_token_detected = True
            self.status.showMessage("âœ“ ÄÃ£ phÃ¡t hiá»‡n USB kÃ½ sá»‘", 3000)
        elif not token_found and self._usb_token_detected:
            self._usb_token_detected = False
            self.status.showMessage("âœ— USB kÃ½ sá»‘ Ä‘Ã£ bá»‹ rÃºt ra", 3000)

    def _on_token_presence_error(self, message: str):
        if message:
            self.status.showMessage("KhÃ´ng kiá»ƒm tra Ä‘Æ°á»£c USB kÃ½ sá»‘", 3000)
