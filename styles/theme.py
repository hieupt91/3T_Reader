DARK_STYLESHEET = """
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
    QToolButton#ThemeButton {
        background-color: #2a2345;
        color: #f7f5ff;
        border: 1px solid #8b83ff;
        border-radius: 10px;
        padding: 4px;
        min-width: 32px;
        font-weight: 600;
    }
    QToolButton#ThemeButton:hover {
        background-color: #3a2f63;
        color: #ffffff;
        border-color: #a59fff;
    }
    QToolButton#ThemeButton::menu-indicator {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 10px;
    }
    QToolButton#SidebarToggleButton {
        background-color: #18202b;
        color: #dff7ff;
        border: 1px solid #22485a;
        border-radius: 10px;
        padding: 4px;
        min-width: 32px;
        font-weight: 600;
    }
    QToolButton#SidebarToggleButton:hover {
        background-color: #1d2b39;
        border-color: #46c7d9;
    }
    QToolButton#SidebarToggleButton:checked {
        background-color: #123844;
        color: #f0fdff;
        border-color: #46c7d9;
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
    QLabel#InspectorSectionTitle {
        color: #f0f6ff;
        background-color: #18202b;
        border: 1px solid #28465f;
        border-radius: 9px;
        padding: 4px 10px;
        font-weight: 600;
        margin-top: 4px;
    }
    QLabel#EditModeLabel {
        color: #f0f6ff;
        background-color: #1d2b39;
        border: 1px solid #28465f;
        border-radius: 10px;
        padding: 4px 10px;
        font-weight: 600;
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
    QDockWidget {
        color: #d6d6ea;
    }
    QDockWidget::title {
        background-color: #171722;
        color: #f0f0ff;
        padding: 6px 10px;
        border-bottom: 1px solid #6c63ff;
        font-weight: 600;
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
    QLineEdit#EditTextInput, QComboBox#ImageSizeCombo {
        background-color: #0f0f18;
        color: #ececff;
        border: 1px solid #2b2b43;
        border-radius: 8px;
        padding: 5px 8px;
        min-height: 28px;
    }
    QSpinBox#EditFontSizeSpin {
        background-color: #0f0f18;
        color: #ececff;
        border: 1px solid #2b2b43;
        border-radius: 8px;
        padding: 4px 8px;
        min-height: 28px;
    }
    QToolButton#ImagePickButton {
        background-color: #1a2633;
        color: #e6f6ff;
        border: 1px solid #31516d;
        border-radius: 8px;
        padding: 4px 10px;
        min-height: 28px;
    }
    QToolButton#ImagePickButton:hover {
        background-color: #24384b;
        border-color: #46c7d9;
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

LIGHT_STYLESHEET = """
    QMainWindow {
        background-color: #f4f6fb;
    }
    QMenuBar {
        background-color: #f8f9fd;
        border-bottom: 1px solid #d7ddea;
        color: #334155;
    }
    QMenuBar::item:selected {
        background-color: #e8edf9;
        color: #0f172a;
    }
    QMenuBar::item:pressed {
        background-color: #3b82f6;
        color: #ffffff;
    }
    QToolBar {
        background-color: #f8f9fd;
        border-bottom: 1px solid #d7ddea;
    }
    QToolBar::separator {
        background-color: #d7ddea;
    }
    QToolButton {
        color: #475569;
    }
    QToolButton:hover {
        background-color: #e8edf9;
        color: #0f172a;
    }
    QToolButton:pressed {
        background-color: #3b82f6;
        color: #ffffff;
    }
    QToolButton:focus {
        border-color: #60a5fa;
        background-color: #e8edf9;
    }
    QToolButton#ThemeButton {
        background-color: #dbeafe;
        color: #0f172a;
        border: 1px solid #60a5fa;
        border-radius: 10px;
        padding: 4px;
        min-width: 32px;
        font-weight: 600;
    }
    QToolButton#ThemeButton:hover {
        background-color: #bfdbfe;
        color: #0f172a;
        border-color: #2563eb;
    }
    QToolButton#ThemeButton::menu-indicator {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 10px;
    }
    QToolButton#SidebarToggleButton {
        background-color: #ecfeff;
        color: #164e63;
        border: 1px solid #67e8f9;
        border-radius: 10px;
        padding: 4px;
        min-width: 32px;
        font-weight: 600;
    }
    QToolButton#SidebarToggleButton:hover {
        background-color: #cffafe;
        border-color: #06b6d4;
    }
    QToolButton#SidebarToggleButton:checked {
        background-color: #bae6fd;
        color: #0c4a6e;
        border-color: #0ea5e9;
    }
    QSpinBox {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
    }
    QSpinBox:hover, QSpinBox:focus {
        border-color: #3b82f6;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        background-color: #e8edf9;
    }
    QLabel {
        color: #475569;
    }
    QLabel#InspectorSectionTitle {
        color: #1f2937;
        background-color: #e6eef8;
        border: 1px solid #b8c9df;
        border-radius: 9px;
        padding: 4px 10px;
        font-weight: 600;
        margin-top: 4px;
    }
    QLabel#EditModeLabel {
        color: #114b5f;
        background-color: #e9f7ff;
        border: 1px solid #9edbed;
        border-radius: 10px;
        padding: 4px 10px;
        font-weight: 600;
    }
    QStatusBar {
        background-color: #f8f9fd;
        border-top: 1px solid #d7ddea;
    }
    QStatusBar QLabel {
        color: #475569;
    }
    QDockWidget {
        color: #334155;
    }
    QDockWidget::title {
        background-color: #eff6ff;
        color: #0f172a;
        padding: 6px 10px;
        border-bottom: 1px solid #60a5fa;
        font-weight: 600;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #d7ddea;
        color: #0f172a;
    }
    QMenu::item:selected {
        background-color: #3b82f6;
        color: #ffffff;
    }
    QLineEdit#EditTextInput, QComboBox#ImageSizeCombo {
        background-color: #ffffff;
        color: #1f2937;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 5px 8px;
        min-height: 28px;
    }
    QSpinBox#EditFontSizeSpin {
        background-color: #ffffff;
        color: #1f2937;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 4px 8px;
        min-height: 28px;
    }
    QToolButton#ImagePickButton {
        background-color: #edf6ff;
        color: #15576a;
        border: 1px solid #9edbed;
        border-radius: 8px;
        padding: 4px 10px;
        min-height: 28px;
    }
    QToolButton#ImagePickButton:hover {
        background-color: #ddefff;
        border-color: #46c7d9;
    }
    QMenu::separator {
        background-color: #e2e8f0;
    }
    QDialog#AppMessageDialog {
        background-color: #ffffff;
        border: 1px solid #d7ddea;
    }
    QDialog#AppMessageDialog QLabel#DialogMessage {
        background-color: #f8fafc;
        color: #0f172a;
        border: 1px solid #d7ddea;
    }
    QDialog#AppMessageDialog QPushButton#DialogAccept {
        background-color: #3b82f6;
    }
    QDialog#AppMessageDialog QPushButton#DialogAccept:hover {
        background-color: #2563eb;
    }
    QFrame#SearchPanel {
        background-color: rgba(255, 255, 255, 0.97);
        border: 1px solid #d7ddea;
    }
    QFrame#SearchPanel QLabel#SearchTitle {
        color: #334155;
    }
    QFrame#SearchPanel QLineEdit#SearchInput {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
    }
    QFrame#SearchPanel QLineEdit#SearchInput:focus {
        border-color: #3b82f6;
    }
    QFrame#SearchPanel QToolButton#SearchBtn {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
    }
    QFrame#SearchPanel QToolButton#SearchBtn:hover {
        background-color: #e8edf9;
        border-color: #3b82f6;
    }
    QFrame#SearchPanel QToolButton#SearchBtnClose {
        color: #334155;
        border: 1px solid #cbd5e1;
    }
    QFrame#SearchPanel QToolButton#SearchBtnClose:hover {
        background-color: #e8edf9;
        border-color: #3b82f6;
    }
    QMessageBox {
        background-color: #ffffff;
        color: #0f172a;
    }
    QMessageBox QLabel {
        color: #0f172a;
    }
    QMessageBox QPushButton {
        background-color: #3b82f6;
    }
    QMessageBox QPushButton:hover {
        background-color: #2563eb;
    }
    QInputDialog {
        background-color: #ffffff;
        color: #0f172a;
    }
    QInputDialog QPushButton {
        background-color: #3b82f6;
    }
    QInputDialog QLineEdit {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
    }
    QLineEdit:focus {
        border-color: #3b82f6;
    }
    QScrollBar::handle:vertical {
        background-color: #cbd5e1;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #60a5fa;
    }
"""

THEME_STYLESHEETS = {
    "dark": DARK_STYLESHEET,
    "light": LIGHT_STYLESHEET,
}

STYLESHEET = DARK_STYLESHEET
