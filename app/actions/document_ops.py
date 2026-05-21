"""Phase 2 document operations: watermark, password, compress, export-to-image."""
from __future__ import annotations

import os
import shutil
import tempfile

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QSpinBox, QSlider,
    QComboBox, QCheckBox, QFileDialog, QInputDialog,
    QColorDialog,
)
from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtGui import QColor

from app.actions._guard import require_document
from app.dialogs import show_warning, show_info


# ─── helpers ─────────────────────────────────────────────────────────────────

def _fitz():
    try:
        import fitz
        return fitz
    except ImportError:
        raise ImportError("Thiếu PyMuPDF.\npip install PyMuPDF==1.27.2.2")


def _tmp_pdf():
    return tempfile.mktemp(suffix=".pdf", dir=tempfile.gettempdir())


def _reload(window, path: str):
    try:
        cur = window.viewer.get_current_page()
    except Exception:
        cur = 1
    window.current_path = path
    window.viewer.load_pdf(path, page=max(1, cur), zoom="page-width")


# ─── Watermark ───────────────────────────────────────────────────────────────

class _WatermarkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thêm watermark")
        self.setMinimumWidth(360)
        self._color = QColor(180, 180, 180)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Text
        root.addWidget(QLabel("Nội dung watermark:"))
        self._text = QLineEdit("BẢN NHÁP")
        self._text.setPlaceholderText("Nhập nội dung…")
        root.addWidget(self._text)

        # Font size + opacity
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Cỡ chữ:"))
        self._size = QSpinBox()
        self._size.setRange(12, 200)
        self._size.setValue(60)
        self._size.setFixedWidth(72)
        row1.addWidget(self._size)
        row1.addSpacing(16)
        row1.addWidget(QLabel("Độ mờ (0–1):"))
        self._opacity = QSpinBox()
        self._opacity.setRange(1, 100)
        self._opacity.setValue(20)
        self._opacity.setSuffix("%")
        self._opacity.setFixedWidth(72)
        row1.addWidget(self._opacity)
        row1.addStretch()
        root.addLayout(row1)

        # Color + rotation
        row2 = QHBoxLayout()
        self._color_btn = QPushButton("Màu chữ")
        self._color_btn.setFixedWidth(90)
        self._color_btn.clicked.connect(self._pick_color)
        self._refresh_color()
        row2.addWidget(self._color_btn)
        row2.addSpacing(16)
        row2.addWidget(QLabel("Góc xoay:"))
        self._angle = QSpinBox()
        self._angle.setRange(-180, 180)
        self._angle.setValue(45)
        self._angle.setSuffix("°")
        self._angle.setFixedWidth(72)
        row2.addWidget(self._angle)
        row2.addStretch()
        root.addLayout(row2)

        # Scope
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Áp dụng:"))
        self._scope = QComboBox()
        self._scope.addItems(["Tất cả trang", "Trang hiện tại"])
        row3.addWidget(self._scope)
        row3.addStretch()
        root.addLayout(row3)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Màu watermark")
        if c.isValid():
            self._color = c
            self._refresh_color()

    def _refresh_color(self):
        c = self._color
        luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        fg = "#000" if luma > 128 else "#FFF"
        self._color_btn.setStyleSheet(
            f"QPushButton{{background:{c.name()};color:{fg};"
            "border:1px solid #555;border-radius:4px;}}"
        )

    def params(self):
        c = self._color
        return {
            "text":    self._text.text().strip() or "WATERMARK",
            "size":    self._size.value(),
            "opacity": self._opacity.value() / 100.0,
            "color":   (c.redF(), c.greenF(), c.blueF()),
            "angle":   self._angle.value(),
            "all_pages": self._scope.currentIndex() == 0,
        }


@require_document(show_message=True)
def add_watermark(window):
    dlg = _WatermarkDialog(window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    p = dlg.params()
    if not p["text"]:
        return

    fitz = _fitz()
    src  = window.current_path
    out  = _tmp_pdf()

    from packages.platform.fonts import get_vietnamese_font_path
    font_path = get_vietnamese_font_path()

    try:
        doc = fitz.open(src)
        cur_page = 0
        try:
            cur_page = max(0, window.viewer.get_current_page() - 1)
        except Exception:
            pass

        pages = range(doc.page_count) if p["all_pages"] else [cur_page]

        for i in pages:
            page = doc[i]
            w, h = page.rect.width, page.rect.height
            cx, cy = w / 2, h / 2

            tw = fitz.get_text_length(p["text"], fontsize=p["size"])
            r  = fitz.Rect(cx - tw / 2 - 20, cy - p["size"] - 10,
                           cx + tw / 2 + 20, cy + p["size"] + 10)

            extra = {}
            if font_path:
                extra = {"fontfile": font_path, "fontname": "wmfont"}
            else:
                extra = {"fontname": "helv"}

            page.insert_textbox(
                r, p["text"],
                fontsize=p["size"],
                color=p["color"],
                rotate=p["angle"],
                opacity=p["opacity"],
                align=fitz.TEXT_ALIGN_CENTER,
                **extra,
            )

        doc.save(out)
        doc.close()
        shutil.copy2(out, src)
        os.remove(out)
        _reload(window, src)
        scope = "tất cả trang" if p["all_pages"] else "trang hiện tại"
        window.status.showMessage(f"Đã thêm watermark '{p['text']}' vào {scope}", 4000)

    except Exception as e:
        show_warning(window, "Lỗi watermark", str(e))
        if os.path.exists(out):
            os.remove(out)


# ─── Password ────────────────────────────────────────────────────────────────

class _PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Đặt mật khẩu PDF")
        self.setMinimumWidth(320)
        root = QVBoxLayout(self)
        root.setSpacing(8)

        root.addWidget(QLabel("Mật khẩu mở file:"))
        self._pw1 = QLineEdit()
        self._pw1.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw1.setPlaceholderText("Nhập mật khẩu…")
        root.addWidget(self._pw1)

        root.addWidget(QLabel("Nhập lại mật khẩu:"))
        self._pw2 = QLineEdit()
        self._pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw2.setPlaceholderText("Xác nhận mật khẩu…")
        root.addWidget(self._pw2)

        self._show = QCheckBox("Hiện mật khẩu")
        self._show.toggled.connect(self._toggle_echo)
        root.addWidget(self._show)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _toggle_echo(self, show):
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self._pw1.setEchoMode(mode)
        self._pw2.setEchoMode(mode)

    def _validate(self):
        if not self._pw1.text():
            show_warning(self, "Mật khẩu trống", "Vui lòng nhập mật khẩu.")
            return
        if self._pw1.text() != self._pw2.text():
            show_warning(self, "Không khớp", "Hai mật khẩu không giống nhau.")
            return
        self.accept()

    def password(self) -> str:
        return self._pw1.text()


@require_document(show_message=True)
def set_pdf_password(window):
    dlg = _PasswordDialog(window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    password = dlg.password()
    fitz = _fitz()
    src  = window.current_path
    out  = _tmp_pdf()

    try:
        doc = fitz.open(src)
        perm = (
            fitz.PDF_PERM_PRINT
            | fitz.PDF_PERM_COPY
            | fitz.PDF_PERM_ANNOTATE
        )
        doc.save(
            out,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw=password + "_owner",
            permissions=perm,
        )
        doc.close()
        shutil.copy2(out, src)
        os.remove(out)
        _reload(window, src)
        window.status.showMessage("Đã đặt mật khẩu PDF", 4000)
    except Exception as e:
        show_warning(window, "Lỗi đặt mật khẩu", str(e))
        if os.path.exists(out):
            os.remove(out)


@require_document(show_message=True)
def remove_pdf_password(window):
    src = window.current_path
    fitz = _fitz()

    try:
        doc = fitz.open(src)
        if not doc.is_encrypted:
            show_info(window, "Không có mật khẩu", "File PDF này chưa được đặt mật khẩu.")
            doc.close()
            return

        pw, ok = QInputDialog.getText(
            window, "Nhập mật khẩu", "Mật khẩu hiện tại:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not pw:
            doc.close()
            return

        if not doc.authenticate(pw):
            show_warning(window, "Sai mật khẩu", "Mật khẩu không đúng.")
            doc.close()
            return

        out = _tmp_pdf()
        doc.save(out, encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        shutil.copy2(out, src)
        os.remove(out)
        _reload(window, src)
        window.status.showMessage("Đã xóa mật khẩu PDF", 4000)
    except Exception as e:
        show_warning(window, "Lỗi xóa mật khẩu", str(e))


# ─── Compress ────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def compress_pdf(window):
    src  = window.current_path
    out  = _tmp_pdf()
    fitz = _fitz()

    try:
        orig_size = os.path.getsize(src)
        doc = fitz.open(src)
        doc.save(
            out,
            garbage=4,      # xóa object thừa, tối ưu xref
            deflate=True,   # nén stream
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
        )
        doc.close()

        new_size = os.path.getsize(out)
        shutil.copy2(out, src)
        os.remove(out)
        _reload(window, src)

        saved = orig_size - new_size
        pct   = saved / orig_size * 100 if orig_size else 0

        def _fmt(b):
            return f"{b/1024:.1f} KB" if b < 1_048_576 else f"{b/1048576:.2f} MB"

        if saved > 0:
            window.status.showMessage(
                f"Nén xong: {_fmt(orig_size)} → {_fmt(new_size)} (giảm {pct:.1f}%)", 6000
            )
        else:
            window.status.showMessage(
                f"File đã được tối ưu, không thể nén thêm ({_fmt(orig_size)})", 4000
            )

    except Exception as e:
        show_warning(window, "Lỗi nén PDF", str(e))
        if os.path.exists(out):
            os.remove(out)


# ─── Export to image ─────────────────────────────────────────────────────────

class _ExportImgDialog(QDialog):
    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Xuất trang ra ảnh")
        self.setMinimumWidth(340)
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Format
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Định dạng:"))
        self._fmt = QComboBox()
        self._fmt.addItems(["PNG (chất lượng cao)", "JPEG", "WEBP"])
        r1.addWidget(self._fmt)
        r1.addStretch()
        root.addLayout(r1)

        # DPI
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Độ phân giải (DPI):"))
        self._dpi = QComboBox()
        self._dpi.addItems(["72 dpi", "96 dpi", "150 dpi", "200 dpi (khuyến nghị)", "300 dpi"])
        self._dpi.setCurrentIndex(3)
        r2.addWidget(self._dpi)
        r2.addStretch()
        root.addLayout(r2)

        # Pages
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Trang:"))
        self._pages = QComboBox()
        self._pages.addItems([
            "Tất cả trang",
            "Trang hiện tại",
            "Nhập dải trang (VD: 1-3, 5)",
        ])
        r3.addWidget(self._pages)
        r3.addStretch()
        root.addLayout(r3)

        self._range_input = QLineEdit()
        self._range_input.setPlaceholderText("VD: 1-3, 5, 7-9")
        self._range_input.setVisible(False)
        root.addWidget(self._range_input)
        self._pages.currentIndexChanged.connect(
            lambda i: self._range_input.setVisible(i == 2)
        )

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._page_count = page_count

    def params(self):
        fmt_map = {0: ("png", "PNG"), 1: ("jpg", "JPEG"), 2: ("webp", "WEBP")}
        ext, fmt = fmt_map[self._fmt.currentIndex()]
        dpi_map = {0: 72, 1: 96, 2: 150, 3: 200, 4: 300}
        dpi = dpi_map[self._dpi.currentIndex()]
        return {
            "ext": ext, "fmt": fmt, "dpi": dpi,
            "page_mode": self._pages.currentIndex(),
            "range_text": self._range_input.text().strip(),
        }


def _parse_range(text: str, max_page: int) -> list[int]:
    pages = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                pages.extend(range(int(a), int(b) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            pages.append(int(part))
    return sorted(set(p for p in pages if 1 <= p <= max_page))


@require_document(show_message=True)
def export_pages_to_images(window):
    fitz = _fitz()
    src  = window.current_path

    doc = fitz.open(src)
    total = doc.page_count
    doc.close()

    try:
        cur_page = window.viewer.get_current_page()
    except Exception:
        cur_page = 1

    dlg = _ExportImgDialog(total, window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    p = dlg.params()

    # Resolve page list
    if p["page_mode"] == 0:
        page_list = list(range(1, total + 1))
    elif p["page_mode"] == 1:
        page_list = [cur_page]
    else:
        page_list = _parse_range(p["range_text"], total)
        if not page_list:
            show_warning(window, "Dải trang không hợp lệ",
                         "Không xác định được trang cần xuất.")
            return

    # Chọn thư mục lưu
    out_dir = QFileDialog.getExistingDirectory(window, "Chọn thư mục lưu ảnh")
    if not out_dir:
        return

    base_name = os.path.splitext(os.path.basename(src))[0]
    scale     = p["dpi"] / 72.0

    window.status.showMessage("Đang xuất ảnh…", 0)
    try:
        doc  = fitz.open(src)
        done = 0
        for pg in page_list:
            page = doc[pg - 1]
            mat  = fitz.Matrix(scale, scale)
            pix  = page.get_pixmap(matrix=mat, alpha=(p["ext"] == "png"))
            suffix = f"_trang{pg:03d}.{p['ext']}"
            out_path = os.path.join(out_dir, base_name + suffix)
            pix.save(out_path)
            done += 1
            window.status.showMessage(f"Đang xuất trang {pg}… ({done}/{len(page_list)})", 0)
        doc.close()
        window.status.showMessage(
            f"Đã xuất {done} ảnh {p['fmt']} vào: {out_dir}", 6000
        )
        # Mở thư mục output
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", out_dir])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", out_dir])
    except Exception as e:
        window.status.showMessage("", 0)
        show_warning(window, "Lỗi xuất ảnh", str(e))
