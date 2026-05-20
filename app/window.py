import os
import sys
import subprocess

from packages.qt_compat.QtPrintSupport import QPrinter, QPrintDialog
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
)
from packages.qt_compat.QtGui import QAction, QKeySequence, QCloseEvent, QImage, QPainter
from packages.qt_compat.QtCore import Qt, QSize, QPoint, QTimer, QThread, QObject, pyqtSignal, QRect
from packages.qt_compat.QtWebEngineWidgets import QWebEngineView
from app.pdf_viewer import PDFViewerWidget

from app.actions.file import open_file, show_recent_menu, _populate_recent_menu
from app.actions.document import search_text, search_next, search_previous, show_file_info, execute_search
from app.actions.edit import (
    create_new_pdf,
    insert_image_to_pdf,
    insert_text_to_pdf,
    select_inserted_object,
    undo_last_edit,
)
from app.actions.navigate import prev_page, next_page, jump_to_page
from app.actions.zoom import zoom_in, zoom_out, apply_zoom, zoom_fit
from app.actions.brightness import brightness_up, brightness_down, apply_brightness_to_webview
from styles.theme import toggle_theme, is_dark
from app.actions.sign import check_token, sign_document
from app.sidebar import ThumbnailSidebar
from app.icon_utils import svg_icon
from app.dialogs import show_warning, show_info
from app.config import WINDOW_TITLE
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

            for i, page_num in enumerate(pages):
                if i > 0:
                    self._printer.newPage()

                self.progress.emit(f"Đang in trang {page_num + 1} / {total}...")

                rendered = pdf.render_page_rgb(page_num + 1, scale=2.0)

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


class PDFReaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 800)
        self.is_fullscreen = False
        self._tab_context_index = -1
        self._usb_token_detected = False

        self._brightness = 100
        self._action_icons: dict = {}   # {QAction: svg_filename} for theme refresh
        self._tabs_data = {}
        self._global_state = {
            "source_path": None,
            "display_path": None,
            "web_view": None,
            "search_query": "",
            "temp_path": None,
        }

        self._build_tab_host()

        self.sidebar = ThumbnailSidebar(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)

        self._build_search_panel()
        self._build_toolbar()
        self._build_menubar()
        self._build_statusbar()
        self._connect_signals()
        self._start_token_monitor()

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
        self.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color="#dcdcff"))
        self.btn_search_prev.clicked.connect(
            lambda: self._search_from_panel(find_previous=True, force_new=False)
        )
        row.addWidget(self.btn_search_prev)

        self.btn_search_next = QToolButton()
        self.btn_search_next.setObjectName("SearchBtn")
        self.btn_search_next.setToolTip("Tìm tiếp (F3)")
        self.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color="#dcdcff"))
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
        self.toolbar = QToolBar("Thanh công cụ")
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setFixedHeight(52)
        self.addToolBar(self.toolbar)

        ic = self._icon_color()   # màu icon theo theme hiện tại

        def add(text, svg_file, tooltip, shortcut, slot):
            a = QAction(text, self)
            a.setIcon(svg_icon(svg_file, color=ic))
            a.setToolTip(tooltip)
            a.setStatusTip(tooltip)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            self.toolbar.addAction(a)
            self._action_icons[a] = svg_file
            return a

        def make(text, svg_file, tooltip, shortcut, slot):
            """Tạo QAction KHÔNG thêm vào toolbar (dùng cho menu)."""
            a = QAction(text, self)
            a.setIcon(svg_icon(svg_file, color=ic))
            a.setToolTip(tooltip)
            a.setStatusTip(tooltip)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            self._action_icons[a] = svg_file
            return a

        # ── File ──────────────────────────────────────────────────────────
        self.act_open   = add("Mở tệp",     "folder_open.svg", f"Mở tệp ({shortcut_label('Ctrl+O')})", "Ctrl+O", lambda: open_file(self))
        self.act_recent = add("Tệp gần đây", "history.svg",    "Tệp gần đây",                          None,     lambda: show_recent_menu(self))
        self.act_save   = add("Lưu",         "save.svg",       f"Lưu ({shortcut_label('Ctrl+S')})",    "Ctrl+S", lambda: self.viewer.save_pdf() if self.viewer else None)
        self.act_print  = add("In",          "print.svg",      f"In ({shortcut_label('Ctrl+P')})",     "Ctrl+P", self.print_current_pdf)
        self.toolbar.addSeparator()

        # ── Điều hướng ────────────────────────────────────────────────────
        self.act_prev = add("Trang trước", "chevron_left.svg", "Trang trước (Left)", "Left", lambda: prev_page(self))

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(9999)
        self.page_spin.setFixedWidth(64)
        self.page_spin.setToolTip("Nhập số trang rồi Enter")
        self.page_spin.editingFinished.connect(lambda: jump_to_page(self))
        self.toolbar.addWidget(self.page_spin)

        self.total_label = QLabel(" / -")
        self.toolbar.addWidget(self.total_label)

        self.act_next = add("Trang sau", "chevron_right.svg", "Trang sau (Right)", "Right", lambda: next_page(self))
        self.toolbar.addSeparator()

        # ── Zoom  [+][100%][−][Fit] ───────────────────────────────────────
        self.act_zoom_in = add("Phóng to",  "zoom_in.svg",  f"Phóng to ({shortcut_label('Ctrl+=')})",  "Ctrl+=", lambda: zoom_in(self))
        self.act_zoom_in.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(25, 400)
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setFixedWidth(78)
        self.zoom_spin.setToolTip("Zoom — double-click để về 100%")
        self.zoom_spin.editingFinished.connect(lambda: apply_zoom(self))
        self.zoom_spin.installEventFilter(self)
        self.toolbar.addWidget(self.zoom_spin)

        self.act_zoom_out = add("Thu nhỏ",  "zoom_out.svg", f"Thu nhỏ ({shortcut_label('Ctrl+-')})", "Ctrl+-", lambda: zoom_out(self))
        self.act_zoom_out.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_fit      = add("Vừa trang", "fit_page.svg", f"Vừa trang ({shortcut_label('Ctrl+0')})", "Ctrl+0", lambda: zoom_fit(self))
        self.toolbar.addSeparator()

        # ── Sidebar toggle ─────────────────────────────────────────────────
        self.act_toggle_sidebar_btn = self.sidebar.toggleViewAction()
        self.act_toggle_sidebar_btn.setIcon(svg_icon("sidebar.svg", color=ic))
        self.act_toggle_sidebar_btn.setToolTip("Ẩn/Hiện thanh trang (Ctrl+\\)")
        self.act_toggle_sidebar_btn.setShortcut(QKeySequence("Ctrl+\\"))
        self.toolbar.addAction(self.act_toggle_sidebar_btn)
        self._action_icons[self.act_toggle_sidebar_btn] = "sidebar.svg"
        self.toolbar.addSeparator()

        # ── Giao diện + Toàn màn hình ─────────────────────────────────────
        self.act_theme_toggle = add("☀ Sáng", "sun.svg", "Chuyển sang chế độ sáng (hiện: Tối)", None, self._toggle_theme)
        self.act_theme_toggle.setIcon(svg_icon("sun.svg", color="#f0c050"))  # icon mặt trời màu vàng, nổi trên nền tối
        theme_btn = self.toolbar.widgetForAction(self.act_theme_toggle)
        if theme_btn:
            theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.act_fullscreen = add("Toàn màn hình", "fullscreen.svg", f"Toàn màn hình (F11)", "F11", self.toggle_fullscreen)

        # ── Menu-only: Độ sáng tài liệu ───────────────────────────────────
        self.act_brightness_up   = make("Sáng hơn", "brightness_up.svg",   f"Tăng độ sáng tài liệu ({shortcut_label('Ctrl+Shift+=')})", "Ctrl+Shift+=", lambda: brightness_up(self))
        self.act_brightness_down = make("Tối hơn",  "brightness_down.svg", f"Giảm độ sáng tài liệu ({shortcut_label('Ctrl+Shift+-')})", "Ctrl+Shift+-", lambda: brightness_down(self))

        # ── Menu-only: Công cụ chỉnh sửa ──────────────────────────────────
        self.act_new_pdf         = make("PDF mới",      "file_plus.svg",   f"Tạo PDF mới ({shortcut_label('Ctrl+N')})", "Ctrl+N", lambda: create_new_pdf(self))
        self.act_insert_text     = make("Chèn text",    "object_plus.svg", "Chèn văn bản vào PDF", None, lambda: insert_text_to_pdf(self))
        self.act_insert_image    = make("Chèn ảnh",     "object_plus.svg", "Chèn ảnh vào PDF",     None, lambda: insert_image_to_pdf(self))
        self.act_select_inserted = make("Chỉnh object", "edit_object.svg", "Chỉnh sửa object",     None, lambda: select_inserted_object(self))
        self.act_undo            = make("Hoàn tác",     "undo.svg",        f"Hoàn tác ({shortcut_label('Ctrl+Z')})", "Ctrl+Z", lambda: undo_last_edit(self))

        # ── Menu-only: Ký số ──────────────────────────────────────────────
        self.act_check_token = make("USB ký số", "usb.svg", "Kiểm tra USB ký số", None, lambda: check_token(self))
        self.act_sign        = make("Ký số",     "pen.svg", "Ký số tài liệu",     None, lambda: sign_document(self))

    # ------------------------------------------------------------------ #
    #  Print — QPrintDialog + PyMuPDF, KHÔNG dùng ShellExecute            #
    # ------------------------------------------------------------------ #

    def print_current_pdf(self):
        """In PDF bằng QPrintDialog thuần Qt.
        Không dùng ShellExecute / subprocess gọi exe ngoài
        → không bao giờ gây re-launch app sau khi đóng gói PyInstaller."""
        state = self._active_state()
        if not state:
            show_warning(self, "Chưa mở tệp", "Vui lòng mở tệp PDF trước khi in.")
            return

        pdf_path = state.get("source_path")
        if not pdf_path or not os.path.exists(pdf_path):
            show_warning(self, "Lỗi", "Không tìm thấy tệp PDF.")
            return

        # Hiện dialog chọn máy in — Qt native, không qua ShellExecute
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog  = QPrintDialog(printer, self)
        dialog.setWindowTitle("In tài liệu")

        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return  # Người dùng bấm Cancel

        # In trong thread riêng để UI không bị đơ
        self._print_thread = QThread(self)
        self._print_worker = _PrintWorker(pdf_path, printer)
        self._print_worker.moveToThread(self._print_thread)

        self._print_thread.started.connect(self._print_worker.run)
        self._print_worker.finished.connect(self._print_thread.quit)
        self._print_worker.finished.connect(self._print_worker.deleteLater)
        self._print_thread.finished.connect(self._print_thread.deleteLater)
        self._print_worker.progress.connect(
            lambda msg: self.status.showMessage(msg, 2000)
        )
        self._print_worker.error.connect(
            lambda msg: show_warning(self, "Lỗi in", msg)
        )
        self._print_thread.finished.connect(
            lambda: self.status.showMessage("✓ In hoàn tất", 4000)
        )

        self.status.showMessage("Đang gửi lệnh in...", 2000)
        self._print_thread.start()

    # ------------------------------------------------------------------ #
    #  Menubar                                                             #
    # ------------------------------------------------------------------ #

    def _build_menubar(self):
        bar = self.menuBar()
        bar.setNativeMenuBar(use_native_menubar())

        menu_file = bar.addMenu("Tệp")
        menu_file.addAction(self.act_new_pdf)
        menu_file.addAction(self.act_open)
        self.menu_recent = menu_file.addMenu("Mở gần đây")
        self.menu_recent.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        self.menu_recent.aboutToShow.connect(self._refresh_recent_menu)
        menu_file.addSeparator()
        menu_file.addAction(self.act_save)
        menu_file.addAction(self.act_print)
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

        menu_nav = bar.addMenu("Điều hướng")
        menu_nav.addAction(self.act_prev)
        menu_nav.addAction(self.act_next)
        act_goto = menu_nav.addAction("Đến trang...")
        act_goto.setIcon(svg_icon("chevron_right.svg", size=16, color="#9b9bc0"))
        act_goto.triggered.connect(self._focus_page_input)

        menu_view = bar.addMenu("Xem")
        menu_view.addAction(self.act_zoom_in)
        menu_view.addAction(self.act_zoom_out)
        menu_view.addAction(self.act_fit)
        menu_view.addSeparator()
        menu_view.addAction(self.act_brightness_up)
        menu_view.addAction(self.act_brightness_down)
        menu_view.addSeparator()
        self.act_toggle_sidebar_btn.setText("Thanh trang thu nhỏ")
        menu_view.addAction(self.act_toggle_sidebar_btn)
        act_toggle_toolbar = self.toolbar.toggleViewAction()
        act_toggle_toolbar.setText("Thanh công cụ")
        act_toggle_toolbar.setShortcut(QKeySequence("Ctrl+B"))
        menu_view.addAction(act_toggle_toolbar)
        menu_view.addSeparator()
        menu_view.addAction(self.act_theme_toggle)
        menu_view.addAction(self.act_fullscreen)

        menu_tools = bar.addMenu("Công cụ")
        menu_tools.addAction(self.act_insert_text)
        menu_tools.addAction(self.act_insert_image)
        menu_tools.addAction(self.act_select_inserted)
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

        menu_sign = bar.addMenu("Chữ ký số")
        menu_sign.addAction(self.act_check_token)
        menu_sign.addAction(self.act_sign)

        menu_help = bar.addMenu("Trợ giúp")
        act_shortcuts = menu_help.addAction("Xem phím tắt")
        act_shortcuts.setIcon(svg_icon("history.svg", size=16, color="#9b9bc0"))
        act_shortcuts.triggered.connect(self._show_shortcuts_hint)

        for action in (
            self.act_open, self.act_new_pdf, self.act_recent,
            self.act_insert_text, self.act_insert_image, self.act_select_inserted,
            self.act_save, self.act_print, self.act_prev, self.act_next,
            self.act_zoom_in, self.act_zoom_out, self.act_fit, self.act_fullscreen,
            self.act_check_token, self.act_sign,
            act_find, act_find_next, act_find_prev,
            act_file_info, act_close_tab, act_tab_next, act_tab_prev,
            act_goto, act_toggle_sidebar, act_shortcuts, act_exit,
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
            self._update_chrome_for_active_tab()

    def _on_page_ready(self, viewer):
        if viewer is not self.viewer:
            return
        wv = self._get_webview_for_viewer(viewer)
        if wv:
            apply_brightness_to_webview(self, wv)

    def _on_page_changed(self, viewer, cur, total):
        if viewer is not self.viewer:
            return
        self.page_label.setText(f"Trang {cur} / {total}")
        self.page_spin.setValue(cur)
        self.total_label.setText(f" / {total}")
        self.sidebar.highlight_page(cur)

    def _on_tab_changed(self, _index):
        self._update_chrome_for_active_tab()
        self._reposition_search_panel()

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
        self.total_label.setText(f" / {total if total else '-'}")
        self.page_label.setText(f"Trang {cur} / {total}")
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

    def _close_tab(self, index):
        tab = self.tab_widget.widget(index)
        if not tab:
            return
        state = self._tabs_data.pop(tab, None)
        self._dispose_tab_resources(state)
        self.tab_widget.removeTab(index)
        tab.deleteLater()
        if self.tab_widget.count() == 0:
            self.hide_search_panel()
            self._update_chrome_for_active_tab()

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
                self._close_tab(idx)

    def _close_tabs_right(self, index: int):
        for idx in range(self.tab_widget.count() - 1, index, -1):
            self._close_tab(idx)

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
        color = self._icon_color()
        for action, svg_file in self._action_icons.items():
            if svg_file not in ("sun.svg", "moon.svg"):
                action.setIcon(svg_icon(svg_file, color=color))

    def _toggle_theme(self):
        toggle_theme()
        self._refresh_icons()
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

    def closeEvent(self, event: QCloseEvent):
        for idx in range(self.tab_widget.count() - 1, -1, -1):
            self._close_tab(idx)
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
