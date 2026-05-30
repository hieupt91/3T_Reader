import os
import sys
import subprocess

from packages.qt_compat.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from packages.qt_compat.QtWidgets import (
    QMainWindow,
    QToolBar,
    QLabel,
    QStatusBar,
    QSpinBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QMenu,
    QSizePolicy,
    QMessageBox,
)
from packages.qt_compat.QtGui import QAction, QKeySequence, QCloseEvent, QImage, QPainter
from packages.qt_compat.QtCore import Qt, QSize, QPoint, QTimer, QThread, QObject, pyqtSignal, QRect
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
    delete_current_page, merge_pdf, extract_pages,
    underline_text, strikeout_text, add_comment,
)
from app.actions.sign import (
    check_token,
    create_signature_field,
    sign_document,
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
from core.recent import load_recent, clear_recent
from packages.pdf_engine import get_pdf_engine

PDFJS_HIDE_TOOLBAR_CSS = """
var style = document.createElement('style');
style.innerHTML = `
#toolbarContainer { display: none !important; }
#loadingBar { display: none !important; }
#mainContainer { top: 0 !important; }
#viewerContainer { top: 0 !important; }
body { background-color: #0f0f13 !important; }
#viewer .page {
border: none !important;
box-shadow: 0 4px 24px rgba(0,0,0,0.5) !important;
margin: 16px auto !important;
border-radius: 4px !important;
}
`;
document.head.appendChild(style);
"""


# Màu icon cho chế độ tối
_ICON_COLORS = {
    "folder_open.svg":   "#5b9cf6",
    "history.svg":       "#5b9cf6",
    "save.svg":          "#4fc080",
    "print.svg":         "#9090c8",
    "chevron_left.svg":  "#a0a0c0",
    "chevron_right.svg": "#a0a0c0",
    "zoom_in.svg":       "#4fc080",
    "zoom_out.svg":      "#f07858",
    "fit_page.svg":      "#b060e0",
    "sidebar.svg":       "#30b8c8",
    "fullscreen.svg":    "#e09040",
    "sun.svg":           "#f0c050",
    "moon.svg":          "#6c63ff",
    "brightness_up.svg":    "#f0c050",
    "brightness_down.svg":  "#8090c8",
    "highlight.svg":     "#f0c050",
    "rotate_cw.svg":     "#50b8f0",
    "rotate_ccw.svg":    "#50b8f0",
    "delete_page.svg":   "#e05050",
    "merge_pdf.svg":     "#4fc080",
    "sign_draw.svg":     "#b060e0",
    "extract.svg":       "#f07858",
    "pen.svg":           "#2080e0",
    "toolbarButton-editorSignature.svg": "#4fc080",
    "redact.svg":        "#e05050",
    "trash.svg":         "#e05050",
    "save_as.svg":       "#4fc080",
    "insert_text.svg":   "#5b9cf6",
    "insert_image.svg":  "#4fc080",
    "usb.svg":           "#b060e0",
    "info.svg":          "#5b9cf6",
    "language.svg":      "#5b9cf6",
    "signature_check.svg": "#4fc080",
    "undo.svg":          "#9090c8",
    "edit_object.svg":   "#5b9cf6",
    "file_plus.svg":     "#4fc080",
}

# Màu icon cho chế độ sáng — đậm hơn để nổi trên nền trắng
_ICON_COLORS_LIGHT = {
    "folder_open.svg":   "#1a5cbf",
    "history.svg":       "#1a5cbf",
    "save.svg":          "#1a7a40",
    "print.svg":         "#4a4a8a",
    "chevron_left.svg":  "#505080",
    "chevron_right.svg": "#505080",
    "zoom_in.svg":       "#1a7a40",
    "zoom_out.svg":      "#c04020",
    "fit_page.svg":      "#7020b0",
    "sidebar.svg":       "#107090",
    "fullscreen.svg":    "#a05010",
    "sun.svg":           "#a07800",
    "moon.svg":          "#3020c0",
    "brightness_up.svg":    "#a07800",
    "brightness_down.svg":  "#4a4a8a",
    "highlight.svg":     "#b08000",
    "rotate_cw.svg":     "#1060b0",
    "rotate_ccw.svg":    "#1060b0",
    "delete_page.svg":   "#b01010",
    "merge_pdf.svg":     "#1a7a40",
    "sign_draw.svg":     "#7020b0",
    "extract.svg":       "#c04020",
    "pen.svg":           "#1050b0",
    "toolbarButton-editorSignature.svg": "#1a7a40",
    "redact.svg":        "#b01010",
    "trash.svg":         "#b01010",
    "save_as.svg":       "#1a7a40",
    "insert_text.svg":   "#1a5cbf",
    "insert_image.svg":  "#1a7a40",
    "usb.svg":           "#7020b0",
    "info.svg":          "#1a5cbf",
    "language.svg":      "#1a5cbf",
    "signature_check.svg": "#1a7a40",
    "undo.svg":          "#4a4a8a",
    "edit_object.svg":   "#1a5cbf",
    "file_plus.svg":     "#1a7a40",
}


class _PrintWorker(QObject):
    """Chạy việc in trong thread riêng để không block UI."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, pdf_path: str, printer: QPrinter):
        super().__init__()
        self._pdf_path = pdf_path
        self._printer  = printer

    def run(self):
        try:
            pdf = get_pdf_engine().open(self._pdf_path)
            painter = QPainter()

            if not painter.begin(self._printer):
                self.error.emit("Không thể khởi động máy in.")
                return

            page_rect = self._printer.pageRect(QPrinter.Unit.DevicePixel)
            w = int(page_rect.width())
            h = int(page_rect.height())

            from_page = self._printer.fromPage()
            to_page   = self._printer.toPage()
            total     = pdf.page_count
            pages     = range(total) if from_page == 0 else range(from_page - 1, to_page)
            render_scale = 2.0 if total <= 120 else 1.4 if total <= 300 else 1.2

            for i, page_num in enumerate(pages):
                if i > 0:
                    self._printer.newPage()

                self.progress.emit(f"Đang in trang {page_num + 1} / {total}...")

                rendered = pdf.render_page_rgb(page_num + 1, scale=render_scale)

                img = QImage(
                    rendered.samples,
                    rendered.width,
                    rendered.height,
                    rendered.stride,
                    QImage.Format.Format_RGB888,
                )

                scaled = img.scaled(
                    QSize(w, h),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                x = (w - scaled.width())  // 2
                y = (h - scaled.height()) // 2
                painter.drawImage(QRect(x, y, scaled.width(), scaled.height()), scaled)

            painter.end()
            pdf.close()

        except ImportError:
            self.error.emit(
                "Thiếu thư viện PDF engine.\n"
                "Vui lòng kiểm tra dependency trong requirements/pyproject\n"
                "rồi build lại bộ cài."
            )
        except Exception as e:
            self.error.emit(f"Lỗi in: {str(e)}")
        finally:
            self.finished.emit()


class _UpdateCheckWorker(QObject):
    finished = pyqtSignal()
    available = pyqtSignal(object)
    up_to_date = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, base_url: str, current_version: str, channel: str):
        super().__init__()
        self._base_url = base_url
        self._current_version = current_version
        self._channel = channel

    def run(self):
        try:
            from app.config import VPS_LICENSE_BASE_URL, UPDATE_CHANNEL
            from app.version import APP_VERSION
            from packages.update_client import check_for_update

            base_url = self._base_url or VPS_LICENSE_BASE_URL
            current_version = self._current_version or APP_VERSION
            channel = self._channel or UPDATE_CHANNEL
            info = check_for_update(base_url, current_version, channel)
            if info.error:
                self.error.emit(info.error)
            elif info.available:
                self.available.emit(info)
            else:
                self.up_to_date.emit(info)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class PDFReaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self._language_code = get_selected_language()
        self.setWindowIcon(app_logo_icon(256))
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 800)
        self.is_fullscreen = False
        self._tab_context_index = -1
        self._usb_token_detected = False

        self._brightness = 100
        self._action_icons: dict = {}   # {QAction: svg_filename} for theme refresh
        self._tabs_data = {}
        self._update_check_thread = None
        self._update_check_worker = None
        self._pending_manual_update_check = False
        self._global_state = {
            "source_path": None,
            "display_path": None,
            "web_view": None,
            "search_query": "",
            "temp_path": None,
        }

        self.setAcceptDrops(True)

        self._build_tab_host()

        self.sidebar = ThumbnailSidebar(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)

        self.toc_sidebar = BookmarkSidebar(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.toc_sidebar)
        self.toc_sidebar.hide()

        self._build_search_panel()
        self._build_toolbar()
        self._build_menubar()
        self._build_statusbar()
        self._connect_signals()
        self._apply_language_texts()
        self._start_token_monitor()
        self._apply_toolbar_prefs()
        QTimer.singleShot(200, self._check_license)
        QTimer.singleShot(15_000, self._auto_check_update)
        # Khôi phục AI API key đã lưu (nếu có)
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
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)
        self.setCentralWidget(self.tab_widget)
        self._show_welcome_tab()

    def _show_welcome_tab(self):
        from app.welcome_widget import WelcomeWidget
        from app.actions.file import open_file, show_recent_menu
        self._welcome_tab = WelcomeWidget(
            on_open=lambda: open_file(self),
            on_recent=lambda: show_recent_menu(self),
        )
        idx = self.tab_widget.addTab(self._welcome_tab, "Trang chủ")
        self.tab_widget.tabBar().setTabButton(idx, self.tab_widget.tabBar().ButtonPosition.RightSide, None)
        # Ẩn sidebar khi ở trang chủ
        QTimer.singleShot(0, self._hide_sidebars_for_welcome)

    def _hide_sidebars_for_welcome(self):
        if hasattr(self, "sidebar"):
            self.sidebar.hide()
        if hasattr(self, "toc_sidebar"):
            self.toc_sidebar.hide()

    def _remove_welcome_tab(self):
        if not hasattr(self, "_welcome_tab"):
            return
        idx = self.tab_widget.indexOf(self._welcome_tab)
        if idx >= 0:
            self.tab_widget.removeTab(idx)
        self._welcome_tab = None

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

        self._connect_viewer_signals(viewer)

        try:
            viewer.load_pdf(source_path, zoom="page-width", pagemode="thumbs")
        except Exception as e:
            self._close_tab(index)
            show_warning(self, "Không thể mở tệp", str(e))
            return False

        self.status.showMessage(f"Đã mở: {title}", 3000)
        try:
            from packages.audit import log_action, ACT_OPEN
            log_action(ACT_OPEN, source_path)
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------ #
    #  Viewer signals                                                      #
    # ------------------------------------------------------------------ #

    def _connect_viewer_signals(self, viewer):
        viewer.pdf_loaded.connect(lambda meta, v=viewer: self._on_pdf_loaded(v, meta))
        viewer.page_changed.connect(lambda cur, total, v=viewer: self._on_page_changed(v, cur, total))
        viewer.error_occurred.connect(lambda msg: self.status.showMessage(f"Cảnh báo: {msg}", 5000))
        viewer.find_not_found.connect(lambda q: show_warning(self, "Không tìm thấy", f"Không tìm thấy kết quả cho: \"{q}\""))
        viewer.page_ready.connect(lambda v=viewer: self._on_page_ready(v))

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

    def _inject_css(self):
        viewer = self.viewer
        if viewer:
            self._inject_css_for_viewer(viewer)

    # ------------------------------------------------------------------ #
    #  Search panel                                                        #
    # ------------------------------------------------------------------ #

    def _build_search_panel(self):
        self.search_panel = QFrame(self.tab_widget)
        self.search_panel.setObjectName("SearchPanel")
        self.search_panel.setVisible(False)

        row = QHBoxLayout(self.search_panel)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        title = QLabel("Tìm")
        title.setObjectName("SearchTitle")
        row.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Nhập từ khóa, Enter để tìm")
        self.search_input.returnPressed.connect(
            lambda: self._search_from_panel(find_previous=False, force_new=False)
        )
        row.addWidget(self.search_input, 1)

        self.btn_search_prev = QToolButton()
        self.btn_search_prev.setObjectName("SearchBtn")
        self.btn_search_prev.setToolTip("Tìm trước đó (Shift+F3)")
        self.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color=self._search_arrow_color()))
        self.btn_search_prev.clicked.connect(
            lambda: self._search_from_panel(find_previous=True, force_new=False)
        )
        row.addWidget(self.btn_search_prev)

        self.btn_search_next = QToolButton()
        self.btn_search_next.setObjectName("SearchBtn")
        self.btn_search_next.setToolTip("Tìm tiếp (F3)")
        self.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color=self._search_arrow_color()))
        self.btn_search_next.clicked.connect(
            lambda: self._search_from_panel(find_previous=False, force_new=False)
        )
        row.addWidget(self.btn_search_next)

        self.btn_search_close = QToolButton()
        self.btn_search_close.setObjectName("SearchBtnClose")
        self.btn_search_close.setToolTip("Đóng tìm kiếm (Esc)")
        self.btn_search_close.setText("Đóng")
        self.btn_search_close.clicked.connect(self.hide_search_panel)
        row.addWidget(self.btn_search_close)

        self.search_panel.adjustSize()
        self._reposition_search_panel()

    def _reposition_search_panel(self):
        if not hasattr(self, "search_panel"):
            return

        margin    = 14
        tab_bar_h = self.tab_widget.tabBar().height() if self.tab_widget.count() > 0 else 0
        self.search_panel.adjustSize()

        max_width  = max(340, self.tab_widget.width() - (margin * 2))
        panel_width = min(500, max_width)
        self.search_panel.setFixedWidth(panel_width)

        x = max(margin, self.tab_widget.width() - self.search_panel.width() - margin)
        y = tab_bar_h + margin
        self.search_panel.move(x, y)

    def show_search_panel(self):
        if not self.current_path:
            self.status.showMessage("Vui lòng mở tệp PDF trước khi tìm kiếm", 3000)
            return

        self._reposition_search_panel()
        self.search_panel.show()
        self.search_panel.raise_()
        if self.search_query and not self.search_input.text().strip():
            self.search_input.setText(self.search_query)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def hide_search_panel(self):
        self.search_panel.hide()

    def _search_from_panel(self, *, find_previous: bool, force_new: bool):
        query = self.search_input.text().strip()
        if not query:
            self.status.showMessage("Nhập từ khóa để tìm kiếm", 2500)
            return

        is_new = force_new or (query != (self.search_query or ""))
        execute_search(self, query, find_previous=find_previous, new_search=is_new)

    # ------------------------------------------------------------------ #
    #  Toolbar                                                             #
    # ------------------------------------------------------------------ #

    def _build_toolbar(self):
        # ── QToolBar chứa ribbon (không hiện widget riêng lẻ) ─────────────
        self.toolbar = QToolBar("Thanh công cụ")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setContentsMargins(0, 0, 0, 0)
        self._apply_toolbar_style()
        self.addToolBar(self.toolbar)

        def _ic(svg_file):
            colors = _ICON_COLORS if is_dark() else _ICON_COLORS_LIGHT
            return colors.get(svg_file, self._icon_color())

        def make(text, svg_file, tooltip, shortcut, slot):
            a = QAction(text, self)
            a.setIcon(svg_icon(svg_file, color=_ic(svg_file)))
            a.setToolTip(tooltip)
            a.setStatusTip(tooltip)
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
        self.act_zoom_in.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_zoom_out = make("Thu nhỏ",   "zoom_out.svg",      f"Thu nhỏ ({shortcut_label('Ctrl+-')})",   "Ctrl+-", lambda: zoom_out(self))
        self.act_zoom_out.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_fit    = make("Vừa trang",   "fit_page.svg",      f"Vừa trang ({shortcut_label('Ctrl+0')})", "Ctrl+0", lambda: zoom_fit(self))

        self.act_highlight    = make("Tô sáng",   "highlight.svg",    f"Tô sáng ({shortcut_label('Ctrl+H')})", "Ctrl+H", lambda: highlight_text(self))
        self.act_insert_text  = make("Chèn chữ",  "insert_text.svg",  "Chèn văn bản vào PDF",   None,          lambda: insert_text_to_pdf(self))
        self.act_insert_image = make("Chèn ảnh",  "insert_image.svg", "Chèn ảnh vào PDF",        None,          lambda: insert_image_to_pdf(self))
        self.act_draw         = make("Vẽ tự do",  "pen.svg",          "Vẽ tự do lên PDF",         None,          lambda: draw_on_pdf(self))
        self.act_redact       = make("Xóa trắng", "redact.svg",       "Che/tẩy vùng nội dung",   None,          lambda: redact_area(self))
        self.act_delete_object= make("Xóa obj",   "trash.svg",        "Xóa text/ảnh đã chèn",    None,          lambda: delete_inserted_object(self))
        self.act_select_inserted = make("Chọn & Xoay","edit_object.svg", "Chọn text/ảnh đã chèn → hiện nút ↻ Xoay, ✎ Sửa, × Xóa, ✥ Di chuyển", None,  lambda: select_inserted_object(self))
        self.act_undo         = make("Hoàn tác",  "undo.svg",         f"Hoàn tác ({shortcut_label('Ctrl+Z')})", "Ctrl+Z", lambda: undo_last_edit(self))

        self.act_toggle_sidebar_btn = make("Thumb", "sidebar.svg",   "Danh sách trang (Ctrl+\\)", "Ctrl+\\", self._toggle_sidebar)
        self.act_toggle_sidebar_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_toggle_toc_btn     = make("Mục lục","history.svg",  "Mục lục PDF (Ctrl+Alt+T)", "Ctrl+Alt+T", self._toggle_toc)
        self.act_toggle_toc_btn.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self._action_icons[self.act_toggle_toc_btn] = "history.svg"

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

        g_file = RibbonGroup("Tệp")
        g_file.add(make_action_btn(self.act_open,    "Mở"))
        g_file.add(make_action_btn(self.act_new_pdf, "Mới"))
        g_file.add(make_action_btn(self.act_recent,  "Gần đây"))
        g_file.add(make_action_btn(self.act_save,    "Lưu"))
        g_file.add(make_action_btn(self.act_save_as, "Lưu mới"))
        g_file.add(make_action_btn(self.act_print,   "In"))
        p0.add_group(g_file)

        g_nav = RibbonGroup("Điều hướng")
        g_nav.add(make_action_btn(self.act_prev, "Trước"))
        g_nav.add(self.page_spin)
        g_nav.add(self.total_label)
        g_nav.add(make_action_btn(self.act_next, "Sau"))
        p0.add_group(g_nav)

        g_zoom = RibbonGroup("Zoom")
        g_zoom.add(make_action_btn(self.act_zoom_in,  "Phóng to"))
        g_zoom.add(self.zoom_spin)
        g_zoom.add(make_action_btn(self.act_zoom_out, "Thu nhỏ"))
        g_zoom.add(make_action_btn(self.act_fit,      "Vừa trang"))
        p0.add_group(g_zoom)

        g_view = RibbonGroup("Giao diện")
        g_view.add(make_action_btn(self.act_toggle_sidebar_btn, "Thumb"))
        g_view.add(make_action_btn(self.act_toggle_toc_btn,     "Mục lục"))
        g_view.add(make_action_btn(self.act_theme_toggle,       "Chủ đề"))
        g_view.add(make_action_btn(self.act_fullscreen,         "Toàn màn"))

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
        g_view.add(self._lang_toolbar_button)
        p0.add_group(g_view, add_sep=False)
        p0.add_stretch()

        self.ribbon.add_tab(self._t("tab.file_view", "Tệp & Xem"), p0)

        # ─── Tab 1: Chú thích ─────────────────────────────────────────────
        p1 = RibbonPanel()

        g_mark = RibbonGroup("Đánh dấu")
        g_mark.add(make_action_btn(self.act_highlight, "Tô sáng"))
        _act_underline = make("Gạch dưới", "highlight.svg", "Gạch dưới văn bản", None, lambda: underline_text(self))
        _act_underline.setIcon(svg_icon("highlight.svg", color="#60BFFF"))
        self._action_icons[_act_underline] = "highlight.svg"
        g_mark.add(make_action_btn(_act_underline, "Gạch dưới"))
        _act_strike = make("Gạch ngang", "highlight.svg", "Gạch ngang văn bản", None, lambda: strikeout_text(self))
        _act_strike.setIcon(svg_icon("highlight.svg", color="#FF7070"))
        self._action_icons[_act_strike] = "highlight.svg"
        g_mark.add(make_action_btn(_act_strike, "Gạch ngang"))
        _act_comment = make("Ghi chú", "insert_text.svg", "Thêm ghi chú", None, lambda: add_comment(self))
        g_mark.add(make_action_btn(_act_comment, "Ghi chú"))
        p1.add_group(g_mark)

        g_edit = RibbonGroup("Chỉnh sửa")
        g_edit.add(make_action_btn(self.act_insert_text,  "Chèn chữ"))
        g_edit.add(make_action_btn(self.act_insert_image, "Chèn ảnh"))
        g_edit.add(make_action_btn(self.act_draw,         "Vẽ tự do"))
        g_edit.add(make_action_btn(self.act_redact,       "Xóa trắng"))
        g_edit.add(make_action_btn(self.act_select_inserted, "Chọn & Xoay"))
        g_edit.add(make_action_btn(self.act_delete_object,"Xóa obj"))
        p1.add_group(g_edit)

        g_undo = RibbonGroup("Lịch sử")
        g_undo.add(make_action_btn(self.act_undo, "Hoàn tác"))
        p1.add_group(g_undo, add_sep=False)
        p1.add_stretch()

        self.ribbon.add_tab(self._t("tab.annotate", "Chú thích"), p1)

        # ─── Tab 2: Trang ─────────────────────────────────────────────────
        p2 = RibbonPanel()

        g_rot = RibbonGroup("Xoay / Xóa")
        _act_rcw = make("Xoay phải", "rotate_cw.svg",  "Xoay phải 90°", None, lambda: rotate_page_cw(self))
        _act_rccw= make("Xoay trái", "rotate_ccw.svg", "Xoay trái 90°", None, lambda: rotate_page_ccw(self))
        _act_del = make("Xóa trang", "trash.svg", "Xóa trang hiện tại", None, lambda: delete_current_page(self))
        g_rot.add(make_action_btn(_act_rcw,  "Xoay phải"))
        g_rot.add(make_action_btn(_act_rccw, "Xoay trái"))
        g_rot.add(make_action_btn(_act_del,  "Xóa trang"))
        p2.add_group(g_rot)

        g_org = RibbonGroup("Tổ chức")
        _act_merge   = make("Ghép PDF",   "folder_open.svg", "Ghép PDF vào cuối", None, lambda: merge_pdf(self))
        _act_extract = make("Trích xuất", "save.svg",        "Trích xuất trang",   None, lambda: extract_pages(self))
        _act_pgnum   = make("Số trang",   "insert_text.svg", "Thêm số trang",      None, lambda: add_page_numbers(self))
        g_org.add(make_action_btn(_act_merge,   "Ghép PDF"))
        g_org.add(make_action_btn(_act_extract, "Trích xuất"))
        g_org.add(make_action_btn(_act_pgnum,   "Số trang"))
        p2.add_group(g_org, add_sep=False)
        p2.add_stretch()

        self.ribbon.add_tab(self._t("tab.page", "Trang"), p2)

        # ─── Tab 3: Bảo mật & Xuất ────────────────────────────────────────
        p3 = RibbonPanel()

        g_sec = RibbonGroup("Bảo mật")
        _act_wm   = make("Watermark",   "pen.svg",      "Thêm watermark",     None, lambda: add_watermark(self))
        _act_rmwm = make("Xóa watermark","trash.svg",   "Xóa watermark vừa thêm", None, lambda: remove_watermark(self))
        _act_setpw= make("Đặt mật khẩu","save.svg",     "Đặt mật khẩu PDF",  None, lambda: set_pdf_password(self))
        _act_rmpw = make("Xóa mật khẩu","trash.svg",    "Xóa mật khẩu PDF",  None, lambda: remove_pdf_password(self))
        _act_comp = make("Nén PDF",     "save.svg",     "Nén / tối ưu PDF",   None, lambda: compress_pdf(self))
        g_sec.add(make_action_btn(_act_wm,    "Watermark"))
        g_sec.add(make_action_btn(_act_rmwm,  "Xóa watermark"))
        g_sec.add(make_action_btn(_act_setpw, "Đặt mật khẩu"))
        g_sec.add(make_action_btn(_act_rmpw,  "Xóa mật khẩu"))
        g_sec.add(make_action_btn(_act_comp,  "Nén PDF"))
        p3.add_group(g_sec)

        g_exp = RibbonGroup("Xuất")
        _act_word = make("Word",   "save.svg", "Xuất ra Word (.docx)", None, lambda: export_pdf_to_word(self))
        _act_xl   = make("Excel",  "save.svg", "Xuất ra Excel (.xlsx)",None, lambda: export_pdf_to_excel(self))
        _act_img  = make("Ảnh",   "save.svg",  "Xuất trang ra ảnh",    None, lambda: export_pages_to_images(self))
        _act_txt  = make("Văn bản","save.svg", "Xuất văn bản (.txt)",  None, lambda: export_pdf_to_text(self))
        g_exp.add(make_action_btn(_act_word, "Word"))
        g_exp.add(make_action_btn(_act_xl,   "Excel"))
        g_exp.add(make_action_btn(_act_img,  "Ảnh"))
        g_exp.add(make_action_btn(_act_txt,  "Văn bản"))
        p3.add_group(g_exp, add_sep=False)
        p3.add_stretch()

        self.ribbon.add_tab(self._t("tab.security_export", "Bảo mật & Xuất"), p3)

        # ─── Tab 4: OCR & AI ──────────────────────────────────────────────
        p4 = RibbonPanel()

        g_ocr = RibbonGroup("OCR")
        from app.actions.ocr import ocr_current_page, ocr_full_document
        _act_ocr1 = make("OCR trang",    "zoom_in.svg",  "OCR trang hiện tại",  None, lambda: ocr_current_page(self))
        _act_ocr2 = make("OCR tài liệu", "zoom_in.svg",  "OCR toàn bộ tài liệu",None, lambda: ocr_full_document(self))
        g_ocr.add(make_action_btn(_act_ocr1, "OCR trang"))
        g_ocr.add(make_action_btn(_act_ocr2, "OCR toàn bộ"))
        p4.add_group(g_ocr)

        g_ai = RibbonGroup("AI")
        _act_chat  = make("Chat PDF",    "pen.svg",          "Chat với PDF (Ctrl+Shift+C)", "Ctrl+Shift+C", lambda: open_chat_dialog(self))
        _act_sum   = make("Tóm tắt",     "insert_text.svg",  "Tóm tắt tài liệu",           "Ctrl+Shift+S", lambda: open_summarize_dialog(self))
        _act_trans = make("Dịch",        "sidebar.svg",      "Dịch trang hiện tại",         "Ctrl+Shift+T", lambda: open_translate_dialog(self))
        _act_srch  = make("Tìm nghĩa",   "zoom_in.svg",      "Tìm kiếm theo nghĩa",         "Ctrl+Shift+F", lambda: open_search_dialog(self))
        _act_aiset = make("Cài đặt AI",  "save.svg",         "Cài đặt AI (API Key)",         None,           lambda: open_ai_settings(self))
        g_ai.add(make_action_btn(_act_chat,  "Chat PDF"))
        g_ai.add(make_action_btn(_act_sum,   "Tóm tắt"))
        g_ai.add(make_action_btn(_act_trans, "Dịch"))
        g_ai.add(make_action_btn(_act_srch,  "Tìm nghĩa"))
        g_ai.add(make_action_btn(_act_aiset, "AI Key"))
        p4.add_group(g_ai, add_sep=False)
        p4.add_stretch()

        self.ribbon.add_tab(self._t("tab.ocr_ai", "OCR & AI"), p4)

        # ─── Tab 5: Ký số ─────────────────────────────────────────────────
        p5 = RibbonPanel()

        g_sign = RibbonGroup("Chữ ký số")
        _act_token = make("USB token",  "usb.svg",  "Kiểm tra USB ký số",  None, lambda: check_token(self))
        _act_sign2 = make("Ký số",      "usb.svg",  "Ký số tài liệu",      None, lambda: sign_document(self))
        _act_sign3 = make("Ký PFX",     "file_plus.svg",    "Ký bằng file PFX/P12", None, lambda: sign_with_pfx(self))
        _act_field = make("Ô ký",       "object_plus.svg",  "Tạo ô ký số trên PDF", None, lambda: create_signature_field(self))
        _act_handw = make("Ký tay/dấu", "pen.svg",  "Chèn chữ ký tay, mẫu chữ ký hoặc con dấu PNG", None, lambda: sign_handwritten(self))
        g_sign.add(make_action_btn(_act_token, "Kiểm tra USB"))
        g_sign.add(make_action_btn(_act_sign2, "Ký số"))
        g_sign.add(make_action_btn(_act_sign3, "Ký PFX"))
        g_sign.add(make_action_btn(_act_field, "Ô ký"))
        g_sign.add(make_action_btn(_act_handw, "Ký tay/dấu"))
        p5.add_group(g_sign, add_sep=False)

        g_verify = RibbonGroup("Kiểm tra")
        g_verify.add(make_action_btn(self.act_verify_signature, "Kiểm tra"))
        p5.add_group(g_verify, add_sep=False)
        p5.add_stretch()

        # Sync với self.act_check_token / self.act_sign (dùng trong menu)
        self.act_check_token = _act_token
        self.act_sign        = _act_sign2
        self.act_sign_file   = _act_sign3
        self.act_signature_field = _act_field

        self.ribbon.add_tab(self._t("tab.sign", "Ký số"), p5)

        # ── Thêm ribbon vào toolbar ───────────────────────────────────────
        self.ribbon.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toolbar.addWidget(self.ribbon)
        # Áp dụng đúng theme ngay từ đầu
        self.ribbon.set_theme(is_dark())

    # ------------------------------------------------------------------ #
    #  Print — QPrintDialog + PyMuPDF, KHÔNG dùng ShellExecute            #
    # ------------------------------------------------------------------ #

    def print_current_pdf(self):
        """In PDF với xem trước — QPrintPreviewDialog, không dùng ShellExecute."""
        state = self._active_state()
        if not state:
            show_warning(self, "Chưa mở tệp", "Vui lòng mở tệp PDF trước khi in.")
            return

        pdf_path = state.get("source_path")
        if not pdf_path or not os.path.exists(pdf_path):
            show_warning(self, "Lỗi", "Không tìm thấy tệp PDF.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Xem trước khi in")
        preview.resize(1000, 700)
        preview.paintRequested.connect(lambda p: self._do_print_pages(p, pdf_path))
        preview.exec()

    def _do_print_pages(self, printer: QPrinter, pdf_path: str):
        """Vẽ từng trang PDF lên printer — chạy trên main thread qua paintRequested."""
        try:
            pdf = get_pdf_engine().open(pdf_path)
            painter = QPainter()
            if not painter.begin(printer):
                show_warning(self, "Lỗi in", "Không thể khởi động máy in.")
                return

            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            w = int(page_rect.width())
            h = int(page_rect.height())

            from_page = printer.fromPage()
            to_page   = printer.toPage()
            total     = pdf.page_count
            pages = range(total) if from_page == 0 else range(from_page - 1, to_page)
            render_scale = 2.0 if total <= 120 else 1.4 if total <= 300 else 1.2

            for i, page_num in enumerate(pages):
                if i > 0:
                    printer.newPage()
                self.status.showMessage(f"Đang in trang {page_num + 1} / {total}…", 2000)

                rendered = pdf.render_page_rgb(page_num + 1, scale=render_scale)
                img = QImage(
                    rendered.samples,
                    rendered.width,
                    rendered.height,
                    rendered.stride,
                    QImage.Format.Format_RGB888,
                )
                scaled = img.scaled(
                    QSize(w, h),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (w - scaled.width())  // 2
                y = (h - scaled.height()) // 2
                painter.drawImage(QRect(x, y, scaled.width(), scaled.height()), scaled)

            painter.end()
            pdf.close()
            self.status.showMessage("✓ In hoàn tất", 4000)
        except Exception as e:
            show_warning(self, "Lỗi in", str(e))

    # ------------------------------------------------------------------ #
    #  Menubar                                                             #
    # ------------------------------------------------------------------ #

    def _build_menubar(self):
        bar = self.menuBar()
        bar.setNativeMenuBar(use_native_menubar())

        self.menu_file = bar.addMenu(self._t("menu.file", "Tệp"))
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

        self.menu_nav = bar.addMenu(self._t("menu.navigate", "Điều hướng"))
        menu_nav = self.menu_nav
        menu_nav.addAction(self.act_prev)
        menu_nav.addAction(self.act_next)
        act_goto = menu_nav.addAction("Đến trang...")
        act_goto.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))
        act_goto.triggered.connect(self._focus_page_input)

        self.menu_view = bar.addMenu(self._t("menu.view", "Xem"))
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
        act_toggle_toolbar = self.toolbar.toggleViewAction()
        act_toggle_toolbar.setText("Thanh công cụ")
        act_toggle_toolbar.setShortcut(QKeySequence("Ctrl+B"))
        menu_view.addAction(act_toggle_toolbar)
        act_customize_tb = menu_view.addAction("Tuỳ chỉnh thanh công cụ...")
        act_customize_tb.triggered.connect(self._customize_toolbar)
        menu_view.addSeparator()
        menu_view.addAction(self.act_theme_toggle)
        menu_view.addAction(self.act_fullscreen)

        self.menu_tools = bar.addMenu(self._t("menu.tools", "Công cụ"))
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
        menu_tools.addSeparator()

        # Lưu chỉnh sửa
        menu_tools.addAction(self.act_save_as)
        menu_tools.addAction(self.act_undo)
        menu_tools.addSeparator()

        # Chú thích văn bản
        menu_tools.addAction(self.act_highlight)

        act_underline = menu_tools.addAction("Gạch dưới văn bản")
        act_underline.setIcon(svg_icon("highlight.svg", size=16, color="#4a90d9"))
        act_underline.triggered.connect(lambda: underline_text(self))

        act_strikeout = menu_tools.addAction("Gạch ngang văn bản")
        act_strikeout.setIcon(svg_icon("highlight.svg", size=16, color="#e05050"))
        act_strikeout.triggered.connect(lambda: strikeout_text(self))

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

        menu_tabs = bar.addMenu("Tab")
        act_tab_next = menu_tabs.addAction("Tab kế tiếp")
        act_tab_next.setShortcut(QKeySequence("Ctrl+Tab"))
        act_tab_next.triggered.connect(self._activate_next_tab)
        act_tab_prev = menu_tabs.addAction("Tab trước đó")
        act_tab_prev.setShortcut(QKeySequence("Ctrl+Shift+Tab"))
        act_tab_prev.triggered.connect(self._activate_prev_tab)
        menu_tabs.addAction(act_close_tab)

        self.menu_pages = bar.addMenu(self._t("menu.page", "Trang"))
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
        act_merge.triggered.connect(lambda: merge_pdf(self))
        act_merge.setIcon(svg_icon("merge_pdf.svg", size=16, color="#4fc080"))

        act_extract = menu_pages.addAction("Trích xuất trang...")
        act_extract.triggered.connect(lambda: extract_pages(self))
        act_extract.setIcon(svg_icon("extract.svg", size=16, color="#f07858"))

        self.menu_security = bar.addMenu(self._t("menu.security", "Bảo mật"))
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

        self.menu_sign = bar.addMenu(self._t("menu.sign", "Chữ ký số"))
        menu_sign = self.menu_sign

        act_sign_draw = menu_sign.addAction("Ký tay / chèn dấu...")
        act_sign_draw.triggered.connect(lambda: sign_handwritten(self))
        act_sign_draw.setIcon(svg_icon("sign_draw.svg", size=16, color="#b060e0"))

        menu_sign.addSeparator()
        menu_sign.addAction(self.act_check_token)
        menu_sign.addAction(self.act_sign)
        menu_sign.addAction(self.act_verify_signature)

        self.menu_ocr = bar.addMenu(self._t("menu.ocr", "OCR"))
        menu_ocr = self.menu_ocr
        act_ocr_page = menu_ocr.addAction("🔍  OCR trang hiện tại")
        act_ocr_page.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_ocr_page.triggered.connect(lambda: self._ocr_current_page())

        act_ocr_all = menu_ocr.addAction("📄  OCR toàn bộ tài liệu")
        act_ocr_all.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act_ocr_all.triggered.connect(lambda: self._ocr_full_document())

        self.menu_ai = bar.addMenu(self._t("menu.ai", "AI"))
        menu_ai = self.menu_ai

        act_ai_chat = menu_ai.addAction("💬  Chat với PDF...")
        act_ai_chat.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_ai_chat.triggered.connect(lambda: open_chat_dialog(self))

        act_ai_summarize = menu_ai.addAction("📋  Tóm tắt tài liệu...")
        act_ai_summarize.setShortcut(QKeySequence("Ctrl+Shift+S"))
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

        self.menu_license = bar.addMenu(self._t("menu.license", "License"))
        menu_license = self.menu_license

        self.menu_language = bar.addMenu(self._t("menu.language", "Ngôn ngữ"))
        self.act_lang_vi = self.menu_language.addAction(self._t("lang.vietnamese", "Tiếng Việt"))
        self.act_lang_en = self.menu_language.addAction(self._t("lang.english", "English"))
        self.act_lang_fr = self.menu_language.addAction(self._t("lang.french", "Français"))
        self.act_lang_zh = self.menu_language.addAction(self._t("lang.chinese", "中文"))
        self.act_lang_ko = self.menu_language.addAction(self._t("lang.korean", "한국어"))
        self.act_lang_th = self.menu_language.addAction(self._t("lang.thai", "ไทย"))
        self.menu_language.addSeparator()
        self.act_lang_refresh = self.menu_language.addAction(self._t("lang.download", "Tải gói ngôn ngữ..."))
        self.act_lang_vi.triggered.connect(lambda: self._set_language("vi"))
        self.act_lang_en.triggered.connect(lambda: self._set_language("en"))
        self.act_lang_fr.triggered.connect(lambda: self._set_language("fr"))
        self.act_lang_zh.triggered.connect(lambda: self._set_language("zh"))
        self.act_lang_ko.triggered.connect(lambda: self._set_language("ko"))
        self.act_lang_th.triggered.connect(lambda: self._set_language("th"))
        self.act_lang_refresh.triggered.connect(lambda: self._refresh_language_pack())
        act_activate = menu_license.addAction("🔑  Kích hoạt / Nhập key...")
        act_activate.setShortcut(QKeySequence("Ctrl+Shift+L"))
        act_activate.triggered.connect(lambda: self._open_license_dialog())

        self.menu_help = bar.addMenu(self._t("menu.help", "Trợ giúp"))
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
            self.act_draw, self.act_redact, self.act_delete_object,
            self.act_save, self.act_save_as, self.act_print, self.act_prev, self.act_next,
            self.act_zoom_in, self.act_zoom_out, self.act_fit, self.act_fullscreen,
            self.act_check_token, self.act_sign, self.act_verify_signature,
            act_find, act_find_next, act_find_prev,
            act_file_info, act_close_tab, act_tab_next, act_tab_prev,
            act_goto, self.act_toggle_sidebar_btn, act_shortcuts, act_exit,
            self.act_highlight, self.act_undo, act_rotate_cw, act_rotate_ccw, act_del_page,
            act_merge, act_extract, act_sign_draw, self.act_toggle_toc_btn,
        ):
            action.setIconVisibleInMenu(True)

    # ------------------------------------------------------------------ #
    #  Statusbar                                                           #
    # ------------------------------------------------------------------ #

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.file_label = QLabel("Chưa mở tệp")
        self.page_label = QLabel("Trang: -")
        self.status.addWidget(self.file_label)
        self.status.addPermanentWidget(self.page_label)

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

    def _on_page_ready(self, viewer):
        if viewer is not self.viewer:
            return
        wv = self._get_webview_for_viewer(viewer)
        if wv:
            apply_brightness_to_webview(self, wv)

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
        self.page_spin.setValue(cur)
        self.sidebar.highlight_page(cur)

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

    def _on_tab_changed(self, _index):
        self._update_chrome_for_active_tab()
        self._reposition_search_panel()
        self._load_toc_for_active()
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
            self.page_spin.setValue(1)
            self.search_input.clear()
            self.hide_search_panel()
            self.sidebar.list.clear()
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
        self.page_spin.setValue(max(1, cur))
        if total and total > 0:
            self.total_label.setText(f" / {total}")
            self.page_label.setText(f"Trang {cur} / {total}")
        else:
            self.total_label.setText(" / -")
            self.page_label.setText(f"Trang {cur} / -")
        self.search_input.setText(state.get("search_query", ""))

        self.sidebar.load_thumbnails(
            state["source_path"],
            on_click=lambda page, v=viewer: v.goto_page(page),
        )

    # ------------------------------------------------------------------ #
    #  Tab management                                                      #
    # ------------------------------------------------------------------ #

    def _close_current_tab(self):
        index = self.tab_widget.currentIndex()
        if index >= 0:
            self._close_tab(index)

    def _close_tab(self, index) -> bool:
        tab = self.tab_widget.widget(index)
        if not tab:
            return True

        state = self._tabs_data.get(tab)
        edit_state = state.get("_pdf_edit_state") if state else None
        if edit_state and edit_state.get("ops"):
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
            self._update_chrome_for_active_tab()
            self.toc_sidebar.clear()
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
        from app.config import VPS_LICENSE_BASE_URL, UPDATE_CHANNEL
        from app.version import APP_VERSION

        if self._update_check_thread is not None and self._update_check_thread.isRunning():
            if show_errors:
                self._pending_manual_update_check = True
                self.status.showMessage("Đang kiểm tra cập nhật nền, sẽ kiểm tra lại ngay sau đó...", 5000)
            return

        self._pending_manual_update_check = False

        self.status.showMessage("Đang kiểm tra cập nhật...", 0 if show_errors else 3000)

        worker = _UpdateCheckWorker(VPS_LICENSE_BASE_URL, APP_VERSION, UPDATE_CHANNEL)
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.available.connect(self._show_update_dialog)
        if show_up_to_date:
            worker.up_to_date.connect(self._on_update_up_to_date)
        worker.error.connect(lambda msg: self._on_update_check_error(msg, show_errors))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_update_check_worker)
        thread.started.connect(worker.run)

        self._update_check_worker = worker
        self._update_check_thread = thread
        thread.start()

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
        def _set_action(attr: str, key: str, fallback: str):
            action = getattr(self, attr, None)
            if action is not None:
                action.setText(self._t(key, fallback))

        if hasattr(self, "menu_file"):
            self.menu_file.setTitle(self._t("menu.file", "Tệp"))
        if hasattr(self, "menu_nav"):
            self.menu_nav.setTitle(self._t("menu.navigate", "Điều hướng"))
        if hasattr(self, "menu_view"):
            self.menu_view.setTitle(self._t("menu.view", "Xem"))
        if hasattr(self, "menu_tools"):
            self.menu_tools.setTitle(self._t("menu.tools", "Công cụ"))
        if hasattr(self, "menu_pages"):
            self.menu_pages.setTitle(self._t("menu.page", "Trang"))
        if hasattr(self, "menu_security"):
            self.menu_security.setTitle(self._t("menu.security", "Bảo mật"))
        if hasattr(self, "menu_sign"):
            self.menu_sign.setTitle(self._t("menu.sign", "Chữ ký số"))
        if hasattr(self, "menu_ocr"):
            self.menu_ocr.setTitle(self._t("menu.ocr", "OCR"))
        if hasattr(self, "menu_ai"):
            self.menu_ai.setTitle(self._t("menu.ai", "AI"))
        if hasattr(self, "menu_license"):
            self.menu_license.setTitle(self._t("menu.license", "License"))
        if hasattr(self, "menu_language"):
            self.menu_language.setTitle(self._t("menu.language", "Ngôn ngữ"))
        if hasattr(self, "act_lang_vi"):
            self.act_lang_vi.setText(self._t("lang.vietnamese", "Tiếng Việt"))
        if hasattr(self, "act_lang_en"):
            self.act_lang_en.setText(self._t("lang.english", "English"))
        if hasattr(self, "act_lang_fr"):
            self.act_lang_fr.setText(self._t("lang.french", "Français"))
        if hasattr(self, "act_lang_zh"):
            self.act_lang_zh.setText(self._t("lang.chinese", "中文"))
        if hasattr(self, "act_lang_ko"):
            self.act_lang_ko.setText(self._t("lang.korean", "한국어"))
        if hasattr(self, "act_lang_th"):
            self.act_lang_th.setText(self._t("lang.thai", "ไทย"))
        if hasattr(self, "act_lang_refresh"):
            self.act_lang_refresh.setText(self._t("lang.download", "Tải gói ngôn ngữ..."))
        if hasattr(self, "_lang_toolbar_button"):
            self._lang_toolbar_button.setText(self._t("menu.language", "Ngôn ngữ"))
            self._lang_toolbar_button.setToolTip(self._t("menu.language", "Ngôn ngữ"))
        if hasattr(self, "act_lang_vi_tb"):
            self.act_lang_vi_tb.setText(self._t("lang.vietnamese", "Tiếng Việt"))
        if hasattr(self, "act_lang_en_tb"):
            self.act_lang_en_tb.setText(self._t("lang.english", "English"))
        if hasattr(self, "act_lang_fr_tb"):
            self.act_lang_fr_tb.setText(self._t("lang.french", "Français"))
        if hasattr(self, "act_lang_zh_tb"):
            self.act_lang_zh_tb.setText(self._t("lang.chinese", "中文"))
        if hasattr(self, "act_lang_ko_tb"):
            self.act_lang_ko_tb.setText(self._t("lang.korean", "한국어"))
        if hasattr(self, "act_lang_th_tb"):
            self.act_lang_th_tb.setText(self._t("lang.thai", "ไทย"))
        if hasattr(self, "act_lang_refresh_tb"):
            self.act_lang_refresh_tb.setText(self._t("lang.download", "Tải gói ngôn ngữ..."))
        if hasattr(self, "menu_help"):
            self.menu_help.setTitle(self._t("menu.help", "Trợ giúp"))
        _set_action("act_open", "action.open", "Mở tệp")
        _set_action("act_new_pdf", "action.new_pdf", "PDF mới")
        _set_action("act_recent", "action.recent", "Gần đây")
        _set_action("act_save", "action.save", "Lưu")
        _set_action("act_save_as", "action.save_as", "Lưu mới")
        _set_action("act_print", "action.print", "In")
        _set_action("act_prev", "action.prev", "Trang trước")
        _set_action("act_next", "action.next", "Trang sau")
        _set_action("act_zoom_in", "action.zoom_in", "Phóng to")
        _set_action("act_zoom_out", "action.zoom_out", "Thu nhỏ")
        _set_action("act_fit", "action.fit", "Vừa trang")
        _set_action("act_theme_toggle", "action.theme", "Giao diện")
        _set_action("act_fullscreen", "action.fullscreen", "Toàn màn")
        _set_action("act_highlight", "action.highlight", "Tô sáng")
        _set_action("act_insert_text", "action.insert_text", "Chèn chữ")
        _set_action("act_insert_image", "action.insert_image", "Chèn ảnh")
        _set_action("act_draw", "action.draw", "Vẽ tự do")
        _set_action("act_redact", "action.redact", "Xóa trắng")
        _set_action("act_delete_object", "action.delete_object", "Xóa obj")
        _set_action("act_select_inserted", "action.select_object", "Chọn & Xoay")
        _set_action("act_undo", "action.undo", "Hoàn tác")
        _set_action("act_sign", "action.sign", "Ký số")
        _set_action("act_signature_field", "action.signature_field", "Ô ký")
        _set_action("act_verify_signature", "action.verify", "Kiểm tra")
        if hasattr(self, "ribbon"):
            self.ribbon.set_tab_text(0, self._t("tab.file_view", "Tệp & Xem"))
            self.ribbon.set_tab_text(1, self._t("tab.annotate", "Chú thích"))
            self.ribbon.set_tab_text(2, self._t("tab.page", "Trang"))
            self.ribbon.set_tab_text(3, self._t("tab.security_export", "Bảo mật & Xuất"))
            self.ribbon.set_tab_text(4, self._t("tab.ocr_ai", "OCR & AI"))
            self.ribbon.set_tab_text(5, self._t("tab.sign", "Ký số"))
        if hasattr(self, "file_label") and self.file_label.text() == "Chưa mở tệp":
            self.file_label.setText(self._t("status.no_file", "Chưa mở tệp"))
        if hasattr(self, "page_label") and self.page_label.text() == "Trang: -":
            self.page_label.setText(self._t("status.page", "Trang: -"))

    def _show_audit_log(self):
        from app.audit_log_dialog import AuditLogDialog
        dlg = AuditLogDialog(self)
        dlg.exec()

    def _refresh_recent_menu(self):
        self.menu_recent.clear()
        _populate_recent_menu(self.menu_recent, self)

    def _clear_recent_from_menu(self):
        clear_recent()
        self.status.showMessage("Đã xóa danh sách tệp gần đây", 3000)

    def _show_tab_context_menu(self, pos: QPoint):
        tab_bar = self.tab_widget.tabBar()
        index   = tab_bar.tabAt(pos)
        if index < 0:
            return

        self._tab_context_index = index
        menu = QMenu(self)

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
        web_view = state.get("web_view")
        if web_view:
            try:
                page = web_view.page()
                if page:
                    page.setWebChannel(None)
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
        colors = _ICON_COLORS if is_dark() else _ICON_COLORS_LIGHT
        for action, svg_file in self._action_icons.items():
            if svg_file not in ("sun.svg", "moon.svg"):
                color = colors.get(svg_file, fallback)
                action.setIcon(svg_icon(svg_file, color=color))
        sc = self._search_arrow_color()
        self.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color=sc))
        self.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color=sc))
        self._apply_toolbar_style()

    def _toggle_sidebar(self):
        visible = self.sidebar.isVisible()
        self.sidebar.setVisible(not visible)

    def _toggle_toc(self):
        visible = self.toc_sidebar.isVisible()
        self.toc_sidebar.setVisible(not visible)

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
        for idx in range(self.tab_widget.count() - 1, -1, -1):
            if not self._close_tab(idx):
                event.ignore()
                return
        self._tabs_data.clear()
        self._global_state["web_view"] = None
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    #  USB token monitor                                                   #
    # ------------------------------------------------------------------ #

    def _start_token_monitor(self):
        """Khởi tạo biến theo dõi USB token."""
        pass

    def _check_token_presence(self):
        """Kiểm tra USB token — FIX: dùng sys.executable thay vì 'python'."""
        try:
            result = subprocess.run(
                [
                    sys.executable,   # ✅ Đúng exe đang chạy, không hardcode "python"
                    "-c",
                    "from packages.signing import get_signing_provider; "
                    "print(get_signing_provider().detect_driver() is not None)",
                ],
                cwd=os.path.dirname(os.path.abspath(sys.executable)),
                capture_output=True,
                text=True,
                timeout=5,
            )
            token_found = result.stdout.strip() == "True"

            if token_found and not self._usb_token_detected:
                self._usb_token_detected = True
                show_info(
                    self,
                    "USB ký số được phát hiện",
                    "Thiết bị ký số đã được cắm vào.\nBạn có thể sử dụng tính năng ký số.",
                )
                self.status.showMessage("✓ Đã phát hiện USB ký số", 3000)
            elif not token_found and self._usb_token_detected:
                self._usb_token_detected = False
                self.status.showMessage("✗ USB ký số đã bị rút ra", 3000)
        except Exception:
            pass
