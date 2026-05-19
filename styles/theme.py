STYLESHEET = """
    QMainWindow {
        background-color: #0f0f13;
    }
    QMenuBar {
        background-color: #101016;
        border-bottom: 1px solid #1a1a26;
        color: #b9b9d6;
        padding: 2px 8px;
        font-size: 13px;
        font-weight: 500;
    }
    QMenuBar::item {
        background: transparent;
        border-radius: 8px;
        padding: 6px 10px;
        margin: 2px 2px;
    }
    QMenuBar::item:selected {
        background-color: #1f1f2e;
        color: #f0f0ff;
    }
    QMenuBar::item:pressed {
        background-color: #6c63ff;
        color: #ffffff;
    }
    QToolBar {
        background-color: #13131a;
        border: none;
        border-bottom: 1px solid #1e1e2e;
        padding: 4px 10px;
        spacing: 4px;
    }
    QToolBar::separator {
        background-color: #1e1e2e;
        width: 1px;
        margin: 7px 5px;
    }
    QToolButton {
        background-color: transparent;
        color: #9090b8;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 6px;
        min-width: 32px;
    }
    QToolButton:hover {
        background-color: #1e1e2e;
        color: #e4e4f5;
    }
    QToolButton:pressed {
        background-color: #6c63ff;
        color: #ffffff;
    }
    QToolButton:focus {
        border-color: #8b83ff;
        background-color: #1b1b28;
    }
    QSpinBox {
        background-color: #0f0f13;
        color: #d6d6ea;
        border: 1px solid #1e1e2e;
        border-radius: 8px;
        padding: 4px 8px;
        font-size: 13px;
    }
    QSpinBox:hover { border-color: #6c63ff; }
    QSpinBox:focus {
        border-color: #6c63ff;
        color: #f2f2ff;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #1e1e2e;
        border: none;
        width: 16px;
        border-radius: 4px;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background-color: #6c63ff;
    }
    QLabel {
        color: #8d8da8;
        font-size: 13px;
        padding: 0 2px;
    }
    QStatusBar {
        background-color: #0d0d12;
        border-top: 1px solid #1a1a26;
        font-size: 12px;
        padding: 0 12px;
    }
    QStatusBar QLabel {
        color: #a3a3bf;
        font-size: 12px;
        padding: 4px 0;
    }
    QMenu {
        background-color: #13131a;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 8px;
        color: #d6d6ea;
        font-size: 13px;
    }
    QMenu::icon {
        padding-left: 4px;
    }
    QMenu::item {
        padding: 9px 24px 9px 30px;
        border-radius: 8px;
    }
    QMenu::item:selected {
        background-color: #6c63ff;
        color: #ffffff;
    }
    QMenu::right-arrow {
        image: none;
        width: 10px;
    }
    QMenu::separator {
        height: 1px;
        background-color: #1e1e2e;
        margin: 4px 10px;
    }
    QDialog#AppMessageDialog {
        background-color: #13131a;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
    }
    QDialog#AppMessageDialog QLabel#DialogIcon {
        padding-top: 2px;
    }
    QDialog#AppMessageDialog QScrollArea#DialogScroll {
        background: transparent;
        border: none;
    }
    QDialog#AppMessageDialog QLabel#DialogMessage {
        background-color: #171723;
        color: #ececff;
        border: 1px solid #25253a;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
    }
    QDialog#AppMessageDialog QPushButton#DialogAccept {
        background-color: #6c63ff;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 8px 24px;
        font-size: 13px;
        min-width: 120px;
        min-height: 34px;
    }
    QDialog#AppMessageDialog QPushButton#DialogAccept:hover {
        background-color: #7d75ff;
    }
    QDialog#AppMessageDialog QPushButton#DialogAccept:focus {
        border: 1px solid #9a94ff;
    }
    QFrame#SearchPanel {
        background-color: rgba(19, 19, 30, 0.96);
        border: 1px solid #2a2a40;
        border-radius: 12px;
    }
    QFrame#SearchPanel QLabel#SearchTitle {
        color: #c7c7e8;
        font-size: 12px;
        font-weight: 600;
        padding-right: 2px;
    }
    QFrame#SearchPanel QLineEdit#SearchInput {
        background-color: #0f0f18;
        color: #ececff;
        border: 1px solid #2b2b43;
        border-radius: 8px;
        padding: 6px 10px;
        min-height: 28px;
        font-size: 13px;
    }
    QFrame#SearchPanel QLineEdit#SearchInput:focus {
        border-color: #6c63ff;
    }
    QFrame#SearchPanel QToolButton#SearchBtn {
        background-color: #1b1b2a;
        border: 1px solid #2d2d47;
        border-radius: 8px;
        min-width: 28px;
        min-height: 28px;
        padding: 4px;
    }
    QFrame#SearchPanel QToolButton#SearchBtn:hover {
        background-color: #282842;
        border-color: #6c63ff;
    }
    QFrame#SearchPanel QToolButton#SearchBtnClose {
        background-color: transparent;
        color: #d0d0ee;
        border: 1px solid #2d2d47;
        border-radius: 8px;
        min-height: 28px;
        padding: 4px 10px;
    }
    QFrame#SearchPanel QToolButton#SearchBtnClose:hover {
        background-color: #222237;
        border-color: #6c63ff;
    }
    QMessageBox {
        background-color: #13131a;
        color: #e0e0f0;
        min-width: 420px;
    }
    QMessageBox QLabel {
        color: #e0e0f0;
        font-size: 13px;
        line-height: 1.35;
    }
    QMessageBox QLabel#qt_msgbox_label {
        min-width: 300px;
        padding: 2px 0 2px 2px;
    }
    QMessageBox QLabel#qt_msgboxex_icon_label {
        min-width: 26px;
        max-width: 26px;
        padding-right: 10px;
    }
    QMessageBox QPushButton {
        background-color: #6c63ff;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 8px 24px;
        font-size: 13px;
        min-width: 80px;
        min-height: 34px;
    }
    QMessageBox QPushButton:hover { background-color: #7d75ff; }
    QInputDialog {
        background-color: #13131a;
        color: #e0e0f0;
    }
    QInputDialog QPushButton {
        background-color: #6c63ff;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 8px 20px;
    }
    QInputDialog QLineEdit {
        background-color: #0f0f13;
        color: #e0e0f0;
        border: 1px solid #1e1e2e;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
    }
    QLineEdit:focus {
        border-color: #6c63ff;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 6px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background-color: #2a2a40;
        border-radius: 3px;
        min-height: 40px;
    }
    QScrollBar::handle:vertical:hover { background-color: #6c63ff; }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical { height: 0; }
"""