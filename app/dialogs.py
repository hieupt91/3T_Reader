from packages.qt_compat.QtCore import Qt, QTimer, QThread, QCoreApplication
from packages.qt_compat.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)

# Màu nhấn theo mức độ - dùng cho vòng tròn nền icon + nút chính, để cảnh báo/lỗi
# nổi bật rõ ràng thay vì mọi mức độ đều tím giống hệt nhau như trước.
_LEVEL_ACCENT = {
    "info": "#6c63ff",
    "question": "#6c63ff",
    "warning": "#f5a524",
    "error": "#ef4444",
}


def _rgba(hex_color: str, alpha: float) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _icon_for_level(style, level: str):
    if level == "warning":
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
    if level == "error":
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
    if level == "question":
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
    return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)


def _screen_geometry(parent):
    if parent is not None and parent.windowHandle() and parent.windowHandle().screen():
        return parent.windowHandle().screen().availableGeometry()
    screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


def _build_dialog(parent, title: str, message: str, level: str, *, buttons: list[tuple[str, bool]]):
    """Dựng dialog dùng chung cho mọi mức độ (info/warning/error/question).

    `buttons`: danh sách (nhãn, is_primary) theo đúng thứ tự hiển thị trái->phải.
    Trả về index nút đã bấm, hoặc -1 nếu đóng dialog bằng nút [X]/Esc.
    """
    accent = _LEVEL_ACCENT.get(level, _LEVEL_ACCENT["info"])

    dialog = QDialog(parent)
    dialog.setObjectName("AppMessageDialog")
    dialog.setWindowTitle(title)
    dialog.setModal(True)

    screen_geo = _screen_geometry(parent)
    if screen_geo:
        max_w = max(320, int(screen_geo.width() * 0.92))
        max_h = max(220, int(screen_geo.height() * 0.88))
        base_w = min(560, max_w)
        base_h = min(300, max_h)
        dialog.setMaximumSize(max_w, max_h)
        dialog.resize(base_w, base_h)
    else:
        dialog.resize(560, 300)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(16, 16, 16, 14)
    root.setSpacing(14)

    content_row = QHBoxLayout()
    content_row.setSpacing(12)

    style = parent.style() if parent is not None else dialog.style()
    icon_badge = QLabel()
    icon_badge.setObjectName("DialogIcon")
    icon_badge.setPixmap(_icon_for_level(style, level).pixmap(22, 22))
    icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_badge.setFixedSize(40, 40)
    icon_badge.setStyleSheet(
        f"background-color: {_rgba(accent, 0.16)}; border-radius: 20px;"
    )
    content_row.addWidget(icon_badge, 0, Qt.AlignmentFlag.AlignTop)

    title_label = QLabel(title)
    title_label.setObjectName("DialogTitle")
    title_label.setWordWrap(True)
    title_label.setStyleSheet(f"color: {accent}; font-size: 15px; font-weight: 700;")

    message_label = QLabel(message)
    message_label.setObjectName("DialogMessage")
    message_label.setWordWrap(True)
    message_label.setTextFormat(Qt.TextFormat.PlainText)
    message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    text_col = QVBoxLayout()
    text_col.setSpacing(8)
    text_col.addWidget(title_label)

    scroll = QScrollArea()
    scroll.setObjectName("DialogScroll")
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(message_label)
    text_col.addWidget(scroll, 1)

    content_row.addLayout(text_col, 1)
    root.addLayout(content_row, 1)

    clicked = {"index": -1}
    button_row = QHBoxLayout()
    button_row.setSpacing(8)
    button_row.addStretch(1)
    for index, (text, is_primary) in enumerate(buttons):
        btn = QPushButton(text)
        btn.setObjectName("DialogAccept" if is_primary else "DialogSecondary")
        if is_primary:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {accent}; }}"
                f"QPushButton:hover {{ background-color: {_rgba(accent, 0.85)}; }}"
            )
            btn.setDefault(True)
        else:
            btn.setStyleSheet(
                f"border: 1px solid {_rgba(accent, 0.45)};"
            )

        def _on_click(_checked=False, index=index):
            clicked["index"] = index
            dialog.accept()

        btn.clicked.connect(_on_click)
        button_row.addWidget(btn)
    root.addLayout(button_row, 0)

    dialog.exec()
    return clicked["index"]


def _show_dialog(parent, title: str, message: str, level: str):
    # macOS requires all UI on main thread — defer if called from a background thread
    app = QCoreApplication.instance()
    if app and QThread.currentThread() is not app.thread():
        QTimer.singleShot(0, lambda: _show_dialog(parent, title, message, level))
        return
    _build_dialog(parent, title, message, level, buttons=[("Đồng ý", True)])


def show_warning(parent, title: str, message: str):
    _show_dialog(parent, title, message, "warning")


def show_info(parent, title: str, message: str):
    _show_dialog(parent, title, message, "info")


def show_error(parent, title: str, message: str):
    _show_dialog(parent, title, message, "error")


def ask_yes_no(parent, title: str, message: str, *, default_no: bool = False):
    """Hỏi Có/Không, cùng bộ khung dialog với show_warning/info/error thay vì
    QMessageBox mặc định (trước đây khác giao diện hẳn với 3 hàm kia).
    Trả về đúng QMessageBox.StandardButton.Yes/No để giữ nguyên mọi chỗ gọi
    đang so sánh reply == /!= StandardButton.Yes."""
    buttons = [("Không", default_no), ("Có", not default_no)]
    index = _build_dialog(parent, title, message, "question", buttons=buttons)
    return QMessageBox.StandardButton.Yes if index == 1 else QMessageBox.StandardButton.No
