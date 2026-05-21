import os
import sys
import subprocess

import qdarktheme

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
    QVBoxLayout,
    QTabWidget,
    QMenu,
    QComboBox,
    QFileDialog,
    QDockWidget,
    QTextEdit,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QWidget,
    QStackedWidget,
)
from packages.qt_compat.QtGui import QAction, QActionGroup, QKeySequence, QCloseEvent, QImage, QPainter
from packages.qt_compat.QtCore import Qt, QSize, QPoint, QTimer, QThread, QObject, pyqtSignal, QRect
from packages.qt_compat.QtWebEngineWidgets import QWebEngineView
from app.pdf_viewer import PDFViewerWidget

from app.actions.file import open_file, show_recent_menu, _populate_recent_menu
from app.actions.document import (
    search_text,
    search_next,
    search_previous,
    show_file_info,
    execute_search,
    export_to_docx,
    export_to_excel,
)
from app.actions.edit import (
    create_new_pdf,
    redo_last_edit,
    save_document,
    save_document_as,
    undo_last_edit,
)
from app.actions.navigate import prev_page, next_page, jump_to_page
from app.actions.zoom import zoom_in, zoom_out, apply_zoom, reset_zoom, zoom_fit
from app.actions.sign import check_token, sign_document
from app.about_dialog import AboutDialog
from app.sidebar import ThumbnailSidebar
from app.icon_utils import svg_icon, svg_pixmap
from app.dialogs import show_warning, show_info
from app.config import WINDOW_TITLE
from app.platform_ui import shortcut_label, use_native_menubar, fullscreen_shortcut_hint
from core.recent import load_recent, clear_recent
from packages.pdf_engine import get_pdf_engine
from styles.theme import THEME_STYLESHEETS
from app.welcome_widget import WelcomeWidget


def _pdfjs_hide_toolbar_css(theme_mode: str) -> str:
    body_color = "#f4f6fb" if theme_mode == "light" else "#0f0f13"
    shadow = "0 8px 24px rgba(15, 23, 42, 0.12)" if theme_mode == "light" else "0 4px 24px rgba(0,0,0,0.5)"
    return f"""
(function() {{
var existing = document.getElementById('app-pdfjs-theme');
if (existing) existing.remove();
var style = document.createElement('style');
style.id = 'app-pdfjs-theme';
style.innerHTML = `
#toolbarContainer {{ display: none !important; }}
#loadingBar {{ display: none !important; }}
#mainContainer {{ top: 0 !important; }}
#viewerContainer {{ top: 0 !important; }}
body {{ background-color: {body_color} !important; }}
#viewer .page {{
border: none !important;
box-shadow: {shadow} !important;
margin: 16px auto !important;
border-radius: 4px !important;
}}
`;
document.head.appendChild(style);
}})();
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
        self._theme_preference = "dark"
        self._theme_mode = "dark"
        self._selected_insert_image_path = ""
        self._selected_replacement_image_path = ""
        self._content_stack = None

        self._tabs_data = {}
        self._global_state = {
            "source_path": None,
            "display_path": None,
            "web_view": None,
            "search_query": "",
            "temp_path": None,
            "edit_state": None,
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
        self.apply_theme(self._theme_preference)

    # ------------------------------------------------------------------ #
    #  Tab host                                                            #
    # ------------------------------------------------------------------ #

    def _build_tab_host(self):
        self.welcome_widget = WelcomeWidget(self)
        self.welcome_widget.openRequested.connect(lambda: open_file(self))
        self.welcome_widget.recentRequested.connect(lambda: show_recent_menu(self))

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.welcome_widget)
        self.content_stack.addWidget(self.tab_widget)
        self.content_stack.setCurrentWidget(self.welcome_widget)
        self.setCentralWidget(self.content_stack)

    def _build_edit_inspector(self):
        self.edit_inspector = QDockWidget("Công cụ chèn/sửa", self)
        self.edit_inspector.setObjectName("EditInspectorDock")
        self.edit_inspector.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.edit_inspector.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        body = QWidget(self.edit_inspector)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.inspector_hint = QLabel(
            "Thiết lập ở đây trước khi bấm `Text` hoặc `Ảnh` trên toolbar.\n"
            "Khi chọn được đối tượng, phần chỉnh sửa bên dưới sẽ bật lên."
        )
        self.inspector_hint.setWordWrap(True)
        layout.addWidget(self.inspector_hint)

        insert_form = QFormLayout()

        insert_header = QLabel("Thiết lập khi chèn mới")
        insert_header.setObjectName("InspectorSectionTitle")
        layout.addWidget(insert_header)

        self.insert_text_input = QLineEdit()
        self.insert_text_input.setObjectName("EditTextInput")
        self.insert_text_input.setPlaceholderText("Nội dung text cần chèn")
        insert_form.addRow("Text", self.insert_text_input)

        self.insert_font_size_spin = QSpinBox()
        self.insert_font_size_spin.setObjectName("EditFontSizeSpin")
        self.insert_font_size_spin.setRange(6, 96)
        self.insert_font_size_spin.setValue(12)
        self.insert_font_size_spin.setSuffix(" pt")
        insert_form.addRow("Cỡ chữ", self.insert_font_size_spin)

        self.insert_bold = QCheckBox("In đậm")
        insert_form.addRow("Kiểu chữ", self.insert_bold)

        self.insert_underline = QCheckBox("Gạch chân")
        insert_form.addRow("", self.insert_underline)

        self.insert_image_button = QToolButton()
        self.insert_image_button.setObjectName("ImagePickButton")
        self.insert_image_button.setAutoRaise(True)
        self.insert_image_button.setText("Chọn ảnh...")
        self.insert_image_button.setToolTip("Chọn ảnh để chèn lên PDF")
        self.insert_image_button.clicked.connect(self._choose_insert_image_source)
        insert_form.addRow("Ảnh", self.insert_image_button)

        self.insert_image_size_combo = QComboBox()
        self.insert_image_size_combo.setObjectName("ImageSizeCombo")
        self.insert_image_size_combo.addItems(["Ảnh nhỏ", "Ảnh vừa", "Ảnh lớn"])
        self.insert_image_size_combo.setToolTip("Kích thước mặc định khi chỉ bấm một điểm trên PDF")
        insert_form.addRow("Cỡ ảnh", self.insert_image_size_combo)

        layout.addLayout(insert_form)

        insert_separator = QFrame()
        insert_separator.setFrameShape(QFrame.Shape.HLine)
        insert_separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(insert_separator)

        selected_header = QLabel("Đối tượng đang chọn")
        selected_header.setObjectName("InspectorSectionTitle")
        layout.addWidget(selected_header)

        selected_form = QFormLayout()

        self.inspector_type = QLabel("-")
        selected_form.addRow("Loại", self.inspector_type)

        self.inspector_text = QTextEdit()
        self.inspector_text.setPlaceholderText("Nội dung text")
        self.inspector_text.setMinimumHeight(110)
        selected_form.addRow("Nội dung", self.inspector_text)

        self.inspector_font_size = QSpinBox()
        self.inspector_font_size.setRange(6, 96)
        self.inspector_font_size.setSuffix(" pt")
        selected_form.addRow("Cỡ chữ", self.inspector_font_size)

        self.inspector_rotation = QComboBox()
        self.inspector_rotation.addItems(["0°", "90°", "180°", "270°"])
        selected_form.addRow("Xoay", self.inspector_rotation)

        self.inspector_bold = QCheckBox("In đậm")
        selected_form.addRow("Kiểu chữ", self.inspector_bold)

        self.inspector_underline = QCheckBox("Gạch chân")
        selected_form.addRow("", self.inspector_underline)

        self.inspector_image = QLabel("Chưa chọn ảnh")
        self.inspector_image.setWordWrap(True)
        selected_form.addRow("Ảnh", self.inspector_image)

        self.inspector_change_image = QPushButton("Đổi ảnh...")
        self.inspector_change_image.clicked.connect(self._choose_replacement_image_for_selected)
        self.inspector_change_image.setVisible(False)
        selected_form.addRow("", self.inspector_change_image)

        layout.addLayout(selected_form)

        button_row = QHBoxLayout()
        self.inspector_apply = QPushButton("Áp dụng")
        self.inspector_delete = QPushButton("Xóa")
        self.inspector_repick = QPushButton("Đặt lại vị trí")
        button_row.addWidget(self.inspector_apply)
        button_row.addWidget(self.inspector_repick)
        button_row.addWidget(self.inspector_delete)
        layout.addLayout(button_row)

        self.inspector_apply.clicked.connect(self._apply_selected_object_changes)
        self.inspector_delete.clicked.connect(self._delete_selected_object_from_inspector)
        self.inspector_repick.clicked.connect(self._repick_selected_object_placement)

        self.edit_inspector.setWidget(body)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.edit_inspector)
        self._set_inspector_enabled(False)

    def _active_selected_op_id(self):
        state = self._active_state()
        return state.get("selected_op_id") if state else None

    def _set_active_selected_op_id(self, op_id):
        state = self._active_state()
        if state is not None:
            state["selected_op_id"] = op_id

    def _active_edit_state(self):
        state = self._active_state()
        if state is not None:
            return state.get("edit_state")
        return self._global_state.get("edit_state")

    def _set_inspector_enabled(self, enabled: bool):
        return

    def _selected_op(self):
        edit_state = self._active_edit_state()
        selected_id = self._active_selected_op_id()
        if not edit_state or selected_id is None:
            return None
        for op in edit_state.get("ops", []):
            if op.get("id") == selected_id:
                return op
        return None

    def show_selected_object_in_inspector(self, op: dict | None):
        self._set_active_selected_op_id(op.get("id") if op else None)
        self._selected_replacement_image_path = ""

    def _choose_replacement_image_for_selected(self):
        target_op = self._selected_op()
        if not target_op or target_op.get("type") != "image":
            return
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh thay thế",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not image_path:
            return
        self._selected_replacement_image_path = image_path
        self.inspector_image.setText(os.path.basename(image_path))
        self.status.showMessage(f"Đã chọn ảnh thay thế: {os.path.basename(image_path)}", 3000)

    def _apply_selected_object_preview_adjustment(self, page_number, left, bottom, right, top):
        state = self._active_edit_state()
        if not state:
            return

        selected_id = self._active_selected_op_id()
        if selected_id is None:
            return

        target_op = None
        for op in state.get("ops", []):
            if op.get("id") == selected_id:
                target_op = op
                break
        if not target_op:
            self.show_selected_object_in_inspector(None)
            return

        target_op["page_number"] = max(1, int(page_number))
        target_op["box"] = (left, bottom, right, top)
        state["redo_ops"] = []

        from app.actions.edit import _render_edit_state
        _render_edit_state(self, state, "Đã di chuyển/đổi kích thước đối tượng")
        self.show_selected_object_in_inspector(target_op)

    # ------------------------------------------------------------------ #
    #  State helpers                                                       #
    # ------------------------------------------------------------------ #

    def _active_state(self):
        index = self.tab_widget.currentIndex()
        if index < 0:
            return None
        tab = self.tab_widget.widget(index)
        return self._tabs_data.get(tab)

    def _show_welcome_screen(self):
        if hasattr(self, "content_stack") and hasattr(self, "welcome_widget"):
            self.content_stack.setCurrentWidget(self.welcome_widget)
        if hasattr(self, "welcome_widget"):
            self.welcome_widget.apply_theme(self._theme_mode)

    def _show_tabs_screen(self):
        if hasattr(self, "content_stack") and hasattr(self, "tab_widget"):
            self.content_stack.setCurrentWidget(self.tab_widget)

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
            "edit_state":   None,
            "selected_op_id": None,
        }
        self._tabs_data[tab] = state

        title = os.path.basename(state["display_path"]) if state["display_path"] else "PDF"
        index = self.tab_widget.addTab(tab, title)
        self.tab_widget.setCurrentIndex(index)
        self._show_tabs_screen()

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

    def _icon_color(self, role: str) -> str:
        palette = {
            "dark": {
                "toolbar": "#9090b8",
                "menu": "#9b9bc0",
                "search": "#dcdcff",
            },
            "light": {
                "toolbar": "#475569",
                "menu": "#475569",
                "search": "#334155",
            },
        }
        return palette[self._theme_mode].get(role, palette[self._theme_mode]["toolbar"])

    def menu_icon_color(self) -> str:
        return self._icon_color("menu")

    def _set_action_icon(self, action: QAction, svg_file: str, *, role: str, size: int = 20):
        action.setProperty("icon_svg", svg_file)
        action.setProperty("icon_role", role)
        action.setProperty("icon_size", size)
        icon_color = action.property("icon_color_override") or self._icon_color(role)
        action.setIcon(svg_icon(svg_file, size=size, color=icon_color))

    def _set_action_icon_color(self, action: QAction, color: str):
        action.setProperty("icon_color_override", color)
        svg_file = action.property("icon_svg")
        role = action.property("icon_role")
        size = action.property("icon_size")
        if svg_file and role:
            self._set_action_icon(action, svg_file, role=role, size=int(size) if size else 20)

    def _refresh_theme_icons(self):
        for action in self.findChildren(QAction):
            svg_file = action.property("icon_svg")
            role = action.property("icon_role")
            size = action.property("icon_size")
            if svg_file and role:
                icon_size = int(size) if size else 20
                icon_color = action.property("icon_color_override") or self._icon_color(role)
                action.setIcon(svg_icon(svg_file, size=icon_size, color=icon_color))

        if hasattr(self, "btn_search_prev"):
            self.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color=self._icon_color("search")))
            self.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color=self._icon_color("search")))
        if hasattr(self, "theme_button"):
            self.theme_button.setIcon(svg_icon(self._theme_icon_name(), size=16, color=self._icon_color("toolbar")))
        if hasattr(self, "sidebar_toggle_button"):
            visible = self.sidebar.isVisible() if hasattr(self, "sidebar") else self.act_toggle_sidebar.isChecked()
            self.sidebar_toggle_button.setIcon(svg_icon(self._sidebar_icon_name(visible), size=16, color="#46c7d9"))

    def _inject_css_for_viewer(self, viewer):
        wv = self._get_webview_for_viewer(viewer)
        if wv:
            wv.page().runJavaScript(_pdfjs_hide_toolbar_css(self._theme_mode))

    def _inject_css(self):
        viewer = self.viewer
        if viewer:
            self._inject_css_for_viewer(viewer)

    def _system_theme_mode(self) -> str:
        from packages.qt_compat.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return "dark"
        scheme = app.styleHints().colorScheme()
        return "light" if scheme == Qt.ColorScheme.Light else "dark"

    def _resolved_theme_mode(self, theme_preference: str) -> str:
        if theme_preference == "system":
            return self._system_theme_mode()
        return "light" if theme_preference == "light" else "dark"

    def apply_theme(self, theme_preference: str):
        from packages.qt_compat.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return

        normalized_preference = "light" if theme_preference == "light" else "dark"
        resolved_mode = normalized_preference
        app.setStyleSheet(qdarktheme.load_stylesheet(resolved_mode) + THEME_STYLESHEETS[resolved_mode])
        self._theme_preference = normalized_preference
        self._theme_mode = resolved_mode
        if hasattr(self, "theme_button"):
            next_label = "Sáng" if resolved_mode == "dark" else "Tối"
            self.theme_button.setToolTip(f"Bấm để đổi sang giao diện {next_label}")
            self.theme_button.setStatusTip(f"Đổi sang {next_label}")
            self.theme_button.setIcon(svg_icon(self._theme_icon_name(), size=16, color=self._icon_color("toolbar")))

        self._refresh_theme_icons()
        if hasattr(self, "sidebar"):
            self.sidebar.apply_theme(resolved_mode)
        if hasattr(self, "welcome_widget"):
            self.welcome_widget.apply_theme(resolved_mode)

        for state in self._tabs_data.values():
            viewer = state.get("viewer")
            if viewer:
                self._inject_css_for_viewer(viewer)

    def _sync_sidebar_toggle_ui(self, visible: bool):
        if not hasattr(self, "sidebar_toggle_button"):
            return
        self.act_toggle_sidebar.setChecked(visible)
        self.sidebar_toggle_button.setChecked(visible)
        icon_name = self._sidebar_icon_name(visible)
        self.act_toggle_sidebar.setIcon(svg_icon(icon_name, size=16, color="#46c7d9"))
        self.sidebar_toggle_button.setIcon(svg_icon(icon_name, size=16, color="#46c7d9"))
        menu_label = "Ẩn cột trang" if visible else "Hiện cột trang"
        button_tip = "Ẩn cột trang bên trái" if visible else "Hiện cột trang bên trái"
        self.sidebar_toggle_button.setToolTip(button_tip)
        self.sidebar_toggle_button.setStatusTip(button_tip)
        self.act_toggle_sidebar.setText(menu_label)
        self.act_toggle_sidebar.setToolTip("Bật/tắt cột trang bên trái")
        self.act_toggle_sidebar.setStatusTip(menu_label)

    def _theme_icon_name(self) -> str:
        return "theme_light.svg" if self._theme_mode == "light" else "theme_dark.svg"

    def _toggle_theme_from_button(self):
        self.apply_theme("light" if self._theme_mode == "dark" else "dark")

    def _sidebar_icon_name(self, visible: bool) -> str:
        return "sidebar_hide.svg" if visible else "sidebar_show.svg"

    def _toggle_sidebar_from_button(self, checked: bool):
        self.sidebar.setVisible(checked)

    def _style_toolbar_action_button(
        self,
        action: QAction,
        *,
        text: str | None = None,
        icon_only: bool = False,
        icon_size: int | None = None,
    ):
        button = self.toolbar.widgetForAction(action)
        if not isinstance(button, QToolButton):
            return
        if text is not None:
            button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if icon_only else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAutoRaise(True)
        if icon_size is not None:
            button.setIconSize(QSize(icon_size, icon_size))

    def _truncate_middle(self, text: str, limit: int = 22) -> str:
        if len(text) <= limit:
            return text
        keep = max(4, (limit - 3) // 2)
        return f"{text[:keep]}...{text[-keep:]}"

    def _choose_insert_image_source(self):
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh để chèn",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not image_path:
            return
        self.set_selected_insert_image_path(image_path)
        self.status.showMessage(f"Đã chọn ảnh chèn: {os.path.basename(image_path)}", 3000)

    def set_selected_insert_image_path(self, image_path: str):
        self._selected_insert_image_path = image_path or ""
        if hasattr(self, "insert_image_button"):
            if self._selected_insert_image_path:
                name = os.path.basename(self._selected_insert_image_path)
                self.insert_image_button.setText(self._truncate_middle(name))
                self.insert_image_button.setToolTip(self._selected_insert_image_path)
                self.insert_image_button.setStatusTip(f"Ảnh đã chọn: {name}")
            else:
                self.insert_image_button.setText("Chọn ảnh...")
                self.insert_image_button.setToolTip("Chọn ảnh để chèn lên PDF")
                self.insert_image_button.setStatusTip("Chọn ảnh để chèn lên PDF")

    def current_insert_image_path(self) -> str:
        return self._selected_insert_image_path or ""

    def current_insert_text(self) -> str:
        return ""

    def current_insert_font_size(self) -> int:
        return 12

    def current_insert_image_box_size(self) -> tuple[float, float]:
        return (180.0, 120.0)

    def _set_edit_controls_visible(self, *, text_mode: bool, image_mode: bool):
        # Edit controls now live in the dock inspector, so toolbar visibility
        # does not need to change per mode.
        return

    def begin_edit_mode(self, mode_key: str, status_text: str):
        mode_titles = {
            "text": "Đặt text",
            "image": "Đặt ảnh",
            "edit": "Chọn/Sửa",
            "delete": "Xóa nội dung",
        }
        mode_actions = getattr(self, "_edit_mode_actions", {})
        for key, action in mode_actions.items():
            action.blockSignals(True)
            action.setChecked(key == mode_key)
            action.blockSignals(False)
        self._set_edit_controls_visible(text_mode=(mode_key == "text"), image_mode=(mode_key == "image"))
        self.status.showMessage(status_text, 5000)

    def end_edit_mode(self, status_text: str | None = None):
        mode_actions = getattr(self, "_edit_mode_actions", {})
        for action in mode_actions.values():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)
        self._set_edit_controls_visible(text_mode=False, image_mode=False)
        if status_text:
            self.status.showMessage(status_text, 3500)

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
        self.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color=self._icon_color("search")))
        self.btn_search_prev.clicked.connect(
            lambda: self._search_from_panel(find_previous=True, force_new=False)
        )
        row.addWidget(self.btn_search_prev)

        self.btn_search_next = QToolButton()
        self.btn_search_next.setObjectName("SearchBtn")
        self.btn_search_next.setToolTip("Tìm tiếp (F3)")
        self.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color=self._icon_color("search")))
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
        self.toolbar.setIconSize(QSize(18, 18))
        self.toolbar.setFixedHeight(48)
        self.addToolBar(self.toolbar)

        def add(text, svg_file, tooltip, shortcut, slot):
            a = QAction(text, self)
            self._set_action_icon(a, svg_file, role="toolbar")
            a.setToolTip(tooltip)
            a.setStatusTip(tooltip)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            self.toolbar.addAction(a)
            return a

        self.brand_widget = QFrame(self)
        self.brand_widget.setObjectName("ToolbarBrand")
        brand_layout = QHBoxLayout(self.brand_widget)
        brand_layout.setContentsMargins(10, 4, 12, 4)
        brand_layout.setSpacing(8)
        brand_icon = QLabel()
        brand_icon.setPixmap(svg_pixmap("logo_mark.svg", size=26))
        brand_icon.setFixedSize(28, 28)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_text = QLabel("3T Reader")
        brand_text.setObjectName("ToolbarBrandText")
        brand_layout.addWidget(brand_icon)
        brand_layout.addWidget(brand_text)
        self.toolbar.addWidget(self.brand_widget)
        self.toolbar.addSeparator()

        # Group: File Ops
        self.act_open   = add("Mở tệp",     "folder_open.svg", f"Mở tệp ({shortcut_label('Ctrl+O')})", "Ctrl+O", lambda: open_file(self))
        self.act_recent = add("Tệp gần đây", "history.svg",     "Tệp gần đây",     None,     lambda: show_recent_menu(self))
        self.act_save   = add("Lưu",         "save.svg",        f"Lưu ({shortcut_label('Ctrl+S')})",    "Ctrl+S", lambda: save_document(self))
        self.act_print  = add("In",          "print.svg",       f"In ({shortcut_label('Ctrl+P')})",     "Ctrl+P", self.print_current_pdf)
        self.act_save_as = QAction("Lưu thành...", self)
        self._set_action_icon(self.act_save_as, "save.svg", role="toolbar")
        self._set_action_icon_color(self.act_save_as, "#7bd39a")
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setToolTip("Lưu thành (Ctrl+Shift+S)")
        self.act_save_as.setStatusTip("Lưu tài liệu sang tệp PDF khác")
        self.act_save_as.triggered.connect(lambda: save_document_as(self))
        self.toolbar.addAction(self.act_save_as)
        self._set_action_icon_color(self.act_open, "#4ea1ff")
        self._set_action_icon_color(self.act_recent, "#5d8dff")
        self._set_action_icon_color(self.act_save, "#56c271")
        self._set_action_icon_color(self.act_print, "#b38cff")
        self.toolbar.addSeparator()

        # Group: Navigation
        self.act_prev = add("Trang trước", "chevron_left.svg", "Trang trước (Left)", "Left", lambda: prev_page(self))
        self._set_action_icon_color(self.act_prev, "#9fa9c9")

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(9999)
        self.page_spin.setFixedWidth(64)
        self.page_spin.setToolTip("Nhập số trang và Enter")
        self.page_spin.editingFinished.connect(lambda: jump_to_page(self))
        self.toolbar.addWidget(self.page_spin)

        self.total_label = QLabel(" / -")
        self.toolbar.addWidget(self.total_label)

        self.act_next = add("Trang sau", "chevron_right.svg", "Trang sau (Right)", "Right", lambda: next_page(self))
        self._set_action_icon_color(self.act_next, "#9fa9c9")
        self.toolbar.addSeparator()

        # Group: View
        self.act_zoom_out = add("Thu nhỏ", "zoom_out.svg", f"Thu nhỏ ({shortcut_label('Ctrl+-')})", "Ctrl+-", lambda: zoom_out(self))
        self._set_action_icon_color(self.act_zoom_out, "#ff9a52")

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(25, 400)
        self.zoom_spin.setValue(100)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setFixedWidth(78)
        self.zoom_spin.setToolTip("Zoom (double-click → 100%)")
        self.zoom_spin.editingFinished.connect(lambda: apply_zoom(self))
        self.zoom_spin.installEventFilter(self)
        self.toolbar.addWidget(self.zoom_spin)

        self.zoom_reset_button = QToolButton(self)
        self.zoom_reset_button.setObjectName("ZoomResetButton")
        self.zoom_reset_button.setAutoRaise(True)
        self.zoom_reset_button.setText("100%")
        self.zoom_reset_button.setToolTip("Đưa zoom về 100%")
        self.zoom_reset_button.clicked.connect(lambda: reset_zoom(self))
        self.toolbar.addWidget(self.zoom_reset_button)

        self.act_zoom_in = add("Phóng to",  "zoom_in.svg",  f"Phóng to ({shortcut_label('Ctrl+=')})",  "Ctrl+=", lambda: zoom_in(self))
        self.act_fit     = add("Vừa trang", "fit_page.svg", f"Vừa trang ({shortcut_label('Ctrl+0')})", "Ctrl+0", lambda: zoom_fit(self))
        self._set_action_icon_color(self.act_zoom_in, "#57c86f")
        self._set_action_icon_color(self.act_fit, "#cf78ff")
        self.act_toggle_sidebar = self.sidebar.toggleViewAction()
        self.act_toggle_sidebar.setText("Cột trang")
        self.act_toggle_sidebar.setToolTip("Ẩn/hiện cột trang bên trái")
        self._set_action_icon(self.act_toggle_sidebar, self._sidebar_icon_name(self.sidebar.isVisible()), role="toolbar")
        self._set_action_icon_color(self.act_toggle_sidebar, "#46c7d9")
        self.sidebar_toggle_button = QToolButton(self)
        self.sidebar_toggle_button.setObjectName("SidebarToggleButton")
        self.sidebar_toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.sidebar_toggle_button.setIcon(self.act_toggle_sidebar.icon())
        self.sidebar_toggle_button.setIconSize(QSize(16, 16))
        self.sidebar_toggle_button.setFixedSize(32, 28)
        self.sidebar_toggle_button.setAutoRaise(True)
        self.sidebar_toggle_button.setCheckable(True)
        self.sidebar_toggle_button.clicked.connect(self._toggle_sidebar_from_button)
        self.toolbar.addWidget(self.sidebar_toggle_button)
        self._sync_sidebar_toggle_ui(self.sidebar.isVisible())
        self.toolbar.addSeparator()

        # Group: Edit / Tools
        self.act_new_pdf         = add("PDF mới",       "file_plus.svg",   f"Tạo PDF mới ({shortcut_label('Ctrl+N')})", "Ctrl+N", lambda: create_new_pdf(self))
        self.act_undo            = add("Hoàn tác",     "undo.svg",        f"Hoàn tác ({shortcut_label('Ctrl+Z')})", "Ctrl+Z", lambda: undo_last_edit(self))
        self.act_redo            = add("Làm lại",      "redo.svg",        f"Làm lại ({shortcut_label('Ctrl+Y')})", "Ctrl+Y", lambda: redo_last_edit(self))
        self._edit_mode_actions = {}
        self._set_action_icon_color(self.act_new_pdf, "#7a8cff")
        self._set_action_icon_color(self.act_undo, "#b39dbb")
        self._set_action_icon_color(self.act_redo, "#8bc6ff")
        self.toolbar.addSeparator()

        # Group: Advanced
        self.act_check_token = add("USB ký số",    "usb.svg",        "Kiểm tra USB ký số", None,  lambda: check_token(self))
        self.act_sign        = add("Ký số",         "pen.svg",        "Ký số tài liệu",     None,  lambda: sign_document(self))
        self.toolbar.addSeparator()
        self.act_fullscreen  = add("Toàn màn hình", "fullscreen.svg", "Toàn màn hình (F11)", "F11", self.toggle_fullscreen)
        self._set_action_icon_color(self.act_check_token, "#a6b0ca")
        self._set_action_icon_color(self.act_sign, "#d9d1e5")
        self._set_action_icon_color(self.act_fullscreen, "#ffbf66")

        self.theme_button = QToolButton(self)
        self.theme_button.setObjectName("ThemeButton")
        self.theme_button.setPopupMode(QToolButton.ToolButtonPopupMode.NoPopup)
        self.theme_button.setAutoRaise(True)
        self.theme_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.theme_button.setIconSize(QSize(16, 16))
        self.theme_button.setFixedSize(32, 28)
        self.theme_button.setIcon(svg_icon(self._theme_icon_name(), size=16, color=self._icon_color("toolbar")))
        self.theme_button.clicked.connect(self._toggle_theme_from_button)
        self.theme_button.setToolTip("Bấm để đổi theme")
        self.theme_button.setStatusTip("Bấm để đổi theme")
        self.toolbar.addWidget(self.theme_button)

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
        self._set_action_icon(self.menu_recent.menuAction(), "history.svg", role="menu", size=16)
        self.menu_recent.aboutToShow.connect(self._refresh_recent_menu)
        menu_file.addSeparator()
        menu_file.addAction(self.act_save)
        menu_file.addAction(self.act_save_as)
        menu_file.addAction(self.act_print)
        act_export_docx = menu_file.addAction("Xuat DOCX...")
        self._set_action_icon(act_export_docx, "save.svg", role="menu", size=16)
        act_export_docx.triggered.connect(lambda: export_to_docx(self))
        act_export_excel = menu_file.addAction("Xuat Excel...")
        self._set_action_icon(act_export_excel, "save.svg", role="menu", size=16)
        act_export_excel.triggered.connect(lambda: export_to_excel(self))
        menu_file.addSeparator()

        act_file_info = menu_file.addAction("Thông tin tệp...")
        act_file_info.setShortcut(QKeySequence("Alt+Return"))
        act_file_info.triggered.connect(lambda: show_file_info(self))
        self._set_action_icon(act_file_info, "info.svg", role="menu", size=16)

        act_close_tab = menu_file.addAction("Đóng tab")
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(self._close_current_tab)
        self._set_action_icon(act_close_tab, "fullscreen.svg", role="menu", size=16)

        menu_file.addSeparator()
        act_exit = menu_file.addAction("Thoát")
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)

        menu_nav = bar.addMenu("Điều hướng")
        menu_nav.addAction(self.act_prev)
        menu_nav.addAction(self.act_next)
        act_goto = menu_nav.addAction("Đến trang...")
        self._set_action_icon(act_goto, "chevron_right.svg", role="menu", size=16)
        act_goto.triggered.connect(self._focus_page_input)

        menu_view = bar.addMenu("Xem")
        menu_view.addAction(self.act_zoom_in)
        menu_view.addAction(self.act_zoom_out)
        menu_view.addAction(self.act_fit)
        menu_view.addSeparator()
        self._set_action_icon(self.act_toggle_sidebar, self._sidebar_icon_name(self.sidebar.isVisible()), role="menu", size=16)
        menu_view.addAction(self.act_toggle_sidebar)
        self._sync_sidebar_toggle_ui(self.sidebar.isVisible())
        menu_view.addAction(self.act_fullscreen)

        menu_tools = bar.addMenu("Công cụ")
        menu_tools.addAction(self.act_undo)
        menu_tools.addAction(self.act_redo)
        menu_tools.addSeparator()

        act_find = menu_tools.addAction("Tìm kiếm văn bản...")
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(lambda: search_text(self))
        self._set_action_icon(act_find, "search.svg", role="menu", size=16)

        act_find_next = menu_tools.addAction("Tìm tiếp")
        act_find_next.setShortcut(QKeySequence("F3"))
        act_find_next.triggered.connect(lambda: search_next(self))
        self._set_action_icon(act_find_next, "chevron_right.svg", role="menu", size=16)

        act_find_prev = menu_tools.addAction("Tìm trước đó")
        act_find_prev.setShortcut(QKeySequence("Shift+F3"))
        act_find_prev.triggered.connect(lambda: search_previous(self))
        self._set_action_icon(act_find_prev, "chevron_left.svg", role="menu", size=16)

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
        self._set_action_icon(act_shortcuts, "history.svg", role="menu", size=16)
        act_shortcuts.triggered.connect(self._show_shortcuts_hint)
        menu_help.addSeparator()
        act_about = menu_help.addAction("Giới thiệu 3T Reader")
        self._set_action_icon(act_about, "info.svg", role="menu", size=16)
        act_about.triggered.connect(self._show_about_dialog)

        for action in (
            self.act_open, self.act_new_pdf, self.act_recent,
            self.act_undo, self.act_redo,
            self.act_save, self.act_save_as, self.act_print, self.act_prev, self.act_next,
            self.act_zoom_in, self.act_zoom_out, self.act_fit, self.act_fullscreen,
            self.act_check_token, self.act_sign,
            act_find, act_find_next, act_find_prev,
            act_file_info, act_close_tab, act_tab_next, act_tab_prev,
            act_export_docx, act_export_excel,
            act_goto, self.act_toggle_sidebar, act_shortcuts, act_about, act_exit,
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
        self.act_toggle_sidebar.toggled.connect(self._sync_sidebar_toggle_ui)
        self.sidebar.visibilityChanged.connect(self._sync_sidebar_toggle_ui)

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
            self.show_selected_object_in_inspector(None)
            self._show_welcome_screen()
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
        selected_op = None
        selected_id = state.get("selected_op_id")
        edit_state = state.get("edit_state")
        if selected_id is not None and edit_state:
            for op in edit_state.get("ops", []):
                if op.get("id") == selected_id:
                    selected_op = op
                    break
        self._show_tabs_screen()
        self.show_selected_object_in_inspector(selected_op)

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
            self._show_welcome_screen()
            self._update_chrome_for_active_tab()
        else:
            self._show_tabs_screen()

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

    def _show_about_dialog(self):
        dialog = AboutDialog(self, self._theme_mode)
        dialog.exec()

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

        edit_state = state.get("edit_state")
        if edit_state:
            for path_key in ("base_snapshot", "working_file"):
                path = edit_state.get(path_key)
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            staged_dir = edit_state.get("staged_assets_dir")
            if staged_dir and os.path.isdir(staged_dir):
                try:
                    import shutil
                    shutil.rmtree(staged_dir, ignore_errors=True)
                except OSError:
                    pass

    def eventFilter(self, obj, event):
        from packages.qt_compat.QtCore import QEvent
        if obj is self.zoom_spin and event.type() == QEvent.Type.MouseButtonDblClick:
            self.zoom_spin.setValue(100)
            apply_zoom(self)
            return True
        return super().eventFilter(obj, event)

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
