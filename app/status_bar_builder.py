from packages.qt_compat.QtWidgets import QLabel, QStatusBar


def build_status_bar(window) -> QStatusBar:
    status = QStatusBar()
    window.setStatusBar(status)
    window.status = status
    window.file_label = QLabel("Chưa mở tệp")
    window.page_label = QLabel("Trang: -")
    status.addWidget(window.file_label)
    status.addPermanentWidget(window.page_label)
    return status
