from packages.qt_compat.QtCore import Qt, QTimer, QThread, QCoreApplication
from packages.qt_compat.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)


def _icon_for_level(style, level: str):
    if level == "warning":
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
    if level == "error":
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
    return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)


def _screen_geometry(parent):
    if parent is not None and parent.windowHandle() and parent.windowHandle().screen():
        return parent.windowHandle().screen().availableGeometry()
    screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


def _show_dialog(parent, title: str, message: str, level: str):
    # macOS requires all UI on main thread — defer if called from a background thread
    app = QCoreApplication.instance()
    if app and QThread.currentThread() is not app.thread():
        QTimer.singleShot(0, lambda: _show_dialog(parent, title, message, level))
        return

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
    root.setContentsMargins(14, 14, 14, 12)
    root.setSpacing(12)

    content_row = QHBoxLayout()
    content_row.setSpacing(10)

    style = parent.style() if parent is not None else dialog.style()
    icon_label = QLabel()
    icon_label.setObjectName("DialogIcon")
    icon_label.setPixmap(_icon_for_level(style, level).pixmap(22, 22))
    icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
    icon_label.setFixedWidth(28)
    content_row.addWidget(icon_label, 0)

    message_label = QLabel(message)
    message_label.setObjectName("DialogMessage")
    message_label.setWordWrap(True)
    message_label.setTextFormat(Qt.TextFormat.PlainText)
    message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    scroll = QScrollArea()
    scroll.setObjectName("DialogScroll")
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(message_label)
    content_row.addWidget(scroll, 1)

    root.addLayout(content_row, 1)

    button_row = QHBoxLayout()
    button_row.addStretch(1)
    ok_button = QPushButton("Đồng ý")
    ok_button.setObjectName("DialogAccept")
    ok_button.setDefault(True)
    ok_button.clicked.connect(dialog.accept)
    button_row.addWidget(ok_button)
    root.addLayout(button_row, 0)

    dialog.exec()


def show_warning(parent, title: str, message: str):
    _show_dialog(parent, title, message, "warning")


def show_info(parent, title: str, message: str):
    _show_dialog(parent, title, message, "info")


def show_error(parent, title: str, message: str):
    _show_dialog(parent, title, message, "error")
