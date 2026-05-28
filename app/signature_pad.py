import os

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QColorDialog, QSlider, QSizePolicy, QMessageBox, QInputDialog,
)
from packages.qt_compat.QtGui import QPainter, QPen, QColor, QImage, QPixmap
from packages.qt_compat.QtCore import Qt, QPoint

from app.dialogs import show_info, show_warning
from app.signature_templates import save_signature_template


class DrawingCanvas(QWidget):
    def __init__(self, parent=None, width: int = 520, height: int = 180,
                 transparent: bool = False):
        super().__init__(parent)
        self._w = width
        self._h = height
        self._transparent = transparent
        self.setFixedSize(width, height)
        self._image = QImage(width, height, QImage.Format.Format_ARGB32)
        self._bg_color = QColor(255, 255, 255, 0 if transparent else 255)
        self._image.fill(self._bg_color)
        self._drawing = False
        self._last = QPoint()
        self._has_content = False
        self._pen_color = QColor(10, 10, 80)
        self._pen_size = 2

    def set_pen_color(self, color: QColor) -> None:
        self._pen_color = color

    def set_pen_size(self, size: int) -> None:
        self._pen_size = max(1, size)

    def paintEvent(self, event):
        p = QPainter(self)
        if self._transparent:
            # Checkerboard background to show transparency
            cell = 10
            light = QColor(200, 200, 200)
            dark = QColor(160, 160, 160)
            for row in range(0, self._h, cell):
                for col in range(0, self._w, cell):
                    c = light if (row // cell + col // cell) % 2 == 0 else dark
                    p.fillRect(col, row, cell, cell, c)
        p.drawImage(0, 0, self._image)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._last = event.position().toPoint()
            self._has_content = True

    def mouseMoveEvent(self, event):
        if self._drawing:
            p = QPainter(self._image)
            pen = QPen(self._pen_color, self._pen_size, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(self._last, event.position().toPoint())
            self._last = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False

    def clear(self):
        self._image.fill(self._bg_color)
        self._has_content = False
        self.update()

    def is_empty(self) -> bool:
        return not self._has_content

    def get_pixmap(self) -> QPixmap:
        return QPixmap.fromImage(self._image)


class SignaturePadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vẽ chữ ký tay")
        self.setModal(True)
        self._pixmap: QPixmap | None = None
        self._setup_ui()
        self.adjustSize()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        hint = QLabel("Vẽ chữ ký của bạn bằng chuột hoặc trackpad:")
        layout.addWidget(hint)

        self.canvas = DrawingCanvas(self)
        self.canvas.setStyleSheet(
            "background: white; border: 2px solid #444; border-radius: 6px;"
        )
        layout.addWidget(self.canvas)

        btns = QHBoxLayout()
        btn_clear = QPushButton("Xóa lại")
        btn_clear.clicked.connect(self.canvas.clear)
        btn_save_template = QPushButton("Lưu mẫu")
        btn_save_template.clicked.connect(self._save_template)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Đặt chữ ký lên PDF")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_accept)
        btns.addWidget(btn_clear)
        btns.addWidget(btn_save_template)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _on_accept(self):
        if self.canvas.is_empty():
            QMessageBox.information(self, "Chưa vẽ", "Hãy vẽ chữ ký trước khi xác nhận.")
            return
        self._pixmap = self.canvas.get_pixmap()
        self.accept()

    def _save_template(self):
        if self.canvas.is_empty():
            show_warning(self, "Chưa vẽ", "Hãy vẽ chữ ký trước khi lưu mẫu.")
            return
        name, ok = QInputDialog.getText(
            self,
            "Lưu mẫu chữ ký",
            "Nhập mã mẫu chữ ký (vd: ky1, chu_ky_giam_doc):",
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            show_warning(self, "Thiếu mã", "Vui lòng nhập mã mẫu chữ ký.")
            return
        try:
            path = save_signature_template(name, self.canvas.get_pixmap())
            saved_code = os.path.splitext(os.path.basename(path))[0]
            show_info(
                self,
                "Đã lưu mẫu",
                f"Đã lưu mẫu chữ ký với mã:\n{saved_code}\n\nĐường dẫn:\n{path}",
            )
        except Exception as exc:
            show_warning(self, "Không lưu được mẫu", str(exc))

    def get_pixmap(self) -> QPixmap | None:
        return self._pixmap


class DrawOnPdfDialog(QDialog):
    """Dialog vẽ tự do lên vùng PDF đã chọn — nền trong suốt, hỗ trợ chọn màu/size bút."""

    def __init__(self, parent=None, canvas_w: int = 600, canvas_h: int = 400):
        super().__init__(parent)
        self.setWindowTitle("Vẽ lên PDF")
        self.setModal(True)
        self._pixmap: QPixmap | None = None
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h
        self._setup_ui()
        self.adjustSize()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar: màu bút + kích thước
        toolbar = QHBoxLayout()

        self._color_btn = QPushButton("  Màu bút")
        self._color_btn.setFixedHeight(28)
        self._pen_color = QColor(10, 10, 200)
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        toolbar.addWidget(self._color_btn)

        toolbar.addWidget(QLabel("  Cỡ bút:"))
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(1, 20)
        self._size_slider.setValue(2)
        self._size_slider.setFixedWidth(100)
        self._size_slider.valueChanged.connect(self._on_size_changed)
        toolbar.addWidget(self._size_slider)

        toolbar.addStretch()

        btn_clear = QPushButton("Xóa lại")
        btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(btn_clear)
        layout.addLayout(toolbar)

        # Canvas
        self.canvas = DrawingCanvas(
            self, width=self._canvas_w, height=self._canvas_h, transparent=True
        )
        self.canvas.set_pen_color(self._pen_color)
        self.canvas.set_pen_size(2)
        self.canvas.setStyleSheet("border: 2px solid #888; border-radius: 4px;")
        layout.addWidget(self.canvas)

        hint = QLabel("Vẽ lên vùng đã chọn. Phần trắng sẽ trong suốt.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        # Buttons
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Chèn vào PDF")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_accept)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(self._pen_color, self, "Chọn màu bút")
        if c.isValid():
            self._pen_color = c
            self.canvas.set_pen_color(c)
            self._update_color_btn()

    def _update_color_btn(self):
        c = self._pen_color
        luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        txt = "#000" if luma > 128 else "#fff"
        self._color_btn.setStyleSheet(
            f"background:{c.name()}; color:{txt}; border-radius:4px; padding:0 8px;"
        )

    def _on_size_changed(self, val: int):
        self.canvas.set_pen_size(val)

    def _clear(self):
        self.canvas.clear()

    def _on_accept(self):
        if self.canvas.is_empty():
            QMessageBox.information(self, "Chưa vẽ", "Hãy vẽ nội dung trước khi xác nhận.")
            return
        self._pixmap = self.canvas.get_pixmap()
        self.accept()

    def get_pixmap(self) -> QPixmap | None:
        return self._pixmap
