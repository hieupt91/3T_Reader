"""Phase 2 document operations: watermark, password, compress, export-to-image."""
from __future__ import annotations

import io
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


def _watermark_page_bytes(w: float, h: float, text: str, size: int,
                           color: tuple, angle: float, opacity: float) -> bytes:
    """Tạo 1 trang PDF chứa watermark text bằng reportlab."""
    from reportlab.pdfgen import canvas as rlcanvas
    buf = io.BytesIO()
    c = rlcanvas.Canvas(buf, pagesize=(w, h))
    r, g, b = color
    c.setFillColorRGB(r, g, b, alpha=opacity)
    c.setFont("Helvetica", int(size))
    c.saveState()
    c.translate(w / 2, h / 2)
    c.rotate(angle)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    buf.seek(0)
    return buf.read()


@require_document(show_message=True)
def add_watermark(window):
    dlg = _WatermarkDialog(window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    p = dlg.params()
    if not p["text"]:
        return

    src = window.current_path
    out = _tmp_pdf()

    try:
        import pikepdf

        cur_page = 0
        try:
            cur_page = max(0, window.viewer.get_current_page() - 1)
        except Exception:
            pass

        with pikepdf.open(src) as pdf:
            total = len(pdf.pages)
            target_pages = range(total) if p["all_pages"] else [cur_page]

            for i in target_pages:
                page = pdf.pages[i]
                mbox = page.mediabox
                w = float(mbox[2]) - float(mbox[0])
                h = float(mbox[3]) - float(mbox[1])

                wm_data = _watermark_page_bytes(
                    w, h, p["text"], p["size"],
                    p["color"], p["angle"], p["opacity"]
                )

                wm_pdf = pikepdf.open(io.BytesIO(wm_data))
                wm_page = wm_pdf.pages[0]

                # Nhúng watermark page như form XObject rồi vẽ lên trang gốc
                form = pdf.make_indirect(
                    pikepdf.Dictionary(
                        Type=pikepdf.Name("/XObject"),
                        Subtype=pikepdf.Name("/Form"),
                        BBox=pikepdf.Array([
                            pikepdf.Real(0), pikepdf.Real(0),
                            pikepdf.Real(w), pikepdf.Real(h)
                        ]),
                        Resources=wm_page.get("/Resources", pikepdf.Dictionary()),
                        **{"/Stream": wm_page.obj.get("/Contents", pikepdf.Stream(pdf, b""))}
                    )
                )

                # Lấy content stream của watermark page
                wm_contents = wm_page.obj.get("/Contents")
                if wm_contents is not None:
                    if isinstance(wm_contents, pikepdf.Array):
                        wm_stream_data = b""
                        for s in wm_contents:
                            wm_stream_data += s.read_bytes()
                    else:
                        wm_stream_data = wm_contents.read_bytes()
                else:
                    wm_stream_data = b""

                # Tạo form XObject hợp lệ
                form_xobj = pikepdf.Stream(pdf, wm_stream_data)
                form_xobj.stream_dict["/Type"] = pikepdf.Name("/XObject")
                form_xobj.stream_dict["/Subtype"] = pikepdf.Name("/Form")
                form_xobj.stream_dict["/BBox"] = pikepdf.Array([
                    pikepdf.Real(0), pikepdf.Real(0),
                    pikepdf.Real(w), pikepdf.Real(h)
                ])
                wm_res = wm_page.obj.get("/Resources")
                if wm_res is not None:
                    form_xobj.stream_dict["/Resources"] = wm_res

                form_ref = pdf.make_indirect(form_xobj)

                # Đưa XObject vào Resources của trang
                if "/Resources" not in page.obj:
                    page.obj["/Resources"] = pikepdf.Dictionary()
                res = page.obj["/Resources"]
                if "/XObject" not in res:
                    res["/XObject"] = pikepdf.Dictionary()
                xobj_name = f"/WM{i}"
                res["/XObject"][xobj_name] = form_ref

                # Thêm lệnh vẽ XObject vào cuối content stream
                draw_cmd = f"q {xobj_name} Do Q\n".encode()
                existing = page.obj.get("/Contents")
                if existing is None:
                    new_stream = pikepdf.Stream(pdf, draw_cmd)
                    page.obj["/Contents"] = pdf.make_indirect(new_stream)
                elif isinstance(existing, pikepdf.Array):
                    new_stream = pikepdf.Stream(pdf, draw_cmd)
                    existing.append(pdf.make_indirect(new_stream))
                else:
                    new_stream = pikepdf.Stream(pdf, draw_cmd)
                    page.obj["/Contents"] = pikepdf.Array([
                        existing, pdf.make_indirect(new_stream)
                    ])

                wm_pdf.close()

            pdf.save(out)

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

    pw  = dlg.password()
    src = window.current_path
    out = _tmp_pdf()

    try:
        import pikepdf
        with pikepdf.open(src) as doc:
            doc.save(
                out,
                encryption=pikepdf.Encryption(
                    owner=pw + "_owner",
                    user=pw,
                    R=6,
                )
            )
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

    try:
        import pikepdf

        # Thử mở không cần mật khẩu để kiểm tra xem file có được mã hóa không
        try:
            test_doc = pikepdf.open(src)
            test_doc.close()
            show_info(window, "Không có mật khẩu", "File PDF này chưa được đặt mật khẩu.")
            return
        except pikepdf.PasswordError:
            pass  # File có mật khẩu — tiếp tục

        pw, ok = QInputDialog.getText(
            window, "Nhập mật khẩu", "Mật khẩu hiện tại:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not pw:
            return

        out = _tmp_pdf()
        try:
            with pikepdf.open(src, password=pw) as doc:
                doc.save(out)
        except pikepdf.PasswordError:
            show_warning(window, "Sai mật khẩu", "Mật khẩu không đúng.")
            if os.path.exists(out):
                os.remove(out)
            return

        shutil.copy2(out, src)
        os.remove(out)
        _reload(window, src)
        window.status.showMessage("Đã xóa mật khẩu PDF", 4000)
    except Exception as e:
        show_warning(window, "Lỗi xóa mật khẩu", str(e))


# ─── Compress ────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def compress_pdf(window):
    src = window.current_path
    out = _tmp_pdf()

    try:
        import pikepdf
        orig_size = os.path.getsize(src)
        with pikepdf.open(src) as doc:
            doc.save(
                out,
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )

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
    import pypdfium2 as pdfium

    src = window.current_path

    doc   = pdfium.PdfDocument(src)
    total = len(doc)
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
    # scale: 1 point = 1/72 inch → scale = dpi / 72
    scale = p["dpi"] / 72.0

    window.status.showMessage("Đang xuất ảnh…", 0)
    try:
        doc  = pdfium.PdfDocument(src)
        done = 0
        for pg in page_list:
            page    = doc[pg - 1]
            bitmap  = page.render(scale=scale)
            pil_img = bitmap.to_pil()
            suffix   = f"_trang{pg:03d}.{p['ext']}"
            out_path = os.path.join(out_dir, base_name + suffix)
            pil_img.save(out_path)
            page.close()
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


# ── Export PDF to Text ────────────────────────────────────────────────────────

@require_document(show_message=True)
def export_pdf_to_text(window):
    """Trích xuất toàn bộ văn bản từ PDF ra file .txt."""
    import pypdfium2 as pdfium

    src = window.current_path
    base_name = os.path.splitext(os.path.basename(src))[0]

    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu file văn bản", f"{base_name}.txt", "Text Files (*.txt)"
    )
    if not out_path:
        return

    window.status.showMessage("Đang trích xuất văn bản…", 0)
    try:
        doc   = pdfium.PdfDocument(src)
        lines = []
        for i in range(len(doc)):
            page     = doc[i]
            textpage = page.get_textpage()
            text     = textpage.get_text_range().strip()
            textpage.close()
            page.close()
            if text:
                lines.append(f"=== Trang {i + 1} ===")
                lines.append(text)
                lines.append("")
        doc.close()

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        window.status.showMessage(f"Đã xuất văn bản: {os.path.basename(out_path)}", 5000)
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", out_path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", out_path])
    except Exception as e:
        window.status.showMessage("", 0)
        show_warning(window, "Lỗi trích xuất văn bản", str(e))


# ── Add Page Numbers ──────────────────────────────────────────────────────────

def _page_number_overlay_bytes(w: float, h: float, label: str,
                                font_size: int, margin: int,
                                position: str) -> bytes:
    """Tạo 1 trang PDF chứa số trang bằng reportlab."""
    from reportlab.pdfgen import canvas as rlcanvas
    buf = io.BytesIO()
    c = rlcanvas.Canvas(buf, pagesize=(w, h))
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.setFont("Helvetica", font_size)

    if "trên" in position:
        y = h - margin - font_size
    else:
        y = margin

    text_width = c.stringWidth(label, "Helvetica", font_size)
    if "Phải" in position:
        x = w - margin - text_width
    elif "Trái" in position:
        x = float(margin)
    else:
        x = (w - text_width) / 2.0

    c.drawString(x, y, label)
    c.save()
    buf.seek(0)
    return buf.read()


@require_document(show_message=True)
def add_page_numbers(window):
    """Thêm số trang vào cuối mỗi trang PDF."""
    position, ok = QInputDialog.getItem(
        window, "Vị trí số trang", "Chọn vị trí:",
        ["Giữa — dưới trang", "Phải — dưới trang", "Trái — dưới trang",
         "Giữa — trên trang", "Phải — trên trang"],
        0, False
    )
    if not ok:
        return

    start_num, ok = QInputDialog.getInt(
        window, "Số trang bắt đầu", "Bắt đầu từ số:", 1, 1, 9999
    )
    if not ok:
        return

    src = window.current_path
    tmp = _tmp_pdf()
    window.status.showMessage("Đang thêm số trang…", 0)
    try:
        import pikepdf

        font_size = 10
        margin    = 20

        with pikepdf.open(src) as pdf:
            for i, page in enumerate(pdf.pages):
                num   = start_num + i
                label = str(num)

                mbox = page.mediabox
                w = float(mbox[2]) - float(mbox[0])
                h = float(mbox[3]) - float(mbox[1])

                overlay_data = _page_number_overlay_bytes(
                    w, h, label, font_size, margin, position
                )

                ol_pdf  = pikepdf.open(io.BytesIO(overlay_data))
                ol_page = ol_pdf.pages[0]

                # Lấy content stream của overlay
                ol_contents = ol_page.obj.get("/Contents")
                if ol_contents is not None:
                    if isinstance(ol_contents, pikepdf.Array):
                        ol_stream_data = b""
                        for s in ol_contents:
                            ol_stream_data += s.read_bytes()
                    else:
                        ol_stream_data = ol_contents.read_bytes()
                else:
                    ol_stream_data = b""

                # Tạo form XObject từ overlay page
                form_xobj = pikepdf.Stream(pdf, ol_stream_data)
                form_xobj.stream_dict["/Type"]    = pikepdf.Name("/XObject")
                form_xobj.stream_dict["/Subtype"] = pikepdf.Name("/Form")
                form_xobj.stream_dict["/BBox"]    = pikepdf.Array([
                    pikepdf.Real(0), pikepdf.Real(0),
                    pikepdf.Real(w), pikepdf.Real(h)
                ])
                ol_res = ol_page.obj.get("/Resources")
                if ol_res is not None:
                    form_xobj.stream_dict["/Resources"] = ol_res

                form_ref = pdf.make_indirect(form_xobj)

                # Tambahkan XObject ke Resources halaman
                if "/Resources" not in page.obj:
                    page.obj["/Resources"] = pikepdf.Dictionary()
                res = page.obj["/Resources"]
                if "/XObject" not in res:
                    res["/XObject"] = pikepdf.Dictionary()
                xobj_name = f"/PN{i}"
                res["/XObject"][xobj_name] = form_ref

                # Thêm lệnh vẽ vào cuối content stream
                draw_cmd   = f"q {xobj_name} Do Q\n".encode()
                new_stream = pikepdf.Stream(pdf, draw_cmd)
                existing   = page.obj.get("/Contents")
                if existing is None:
                    page.obj["/Contents"] = pdf.make_indirect(new_stream)
                elif isinstance(existing, pikepdf.Array):
                    existing.append(pdf.make_indirect(new_stream))
                else:
                    page.obj["/Contents"] = pikepdf.Array([
                        existing, pdf.make_indirect(new_stream)
                    ])

                ol_pdf.close()

            pdf.save(tmp)

        shutil.copy2(tmp, src)
        os.remove(tmp)
        _reload(window, src)
        window.status.showMessage("Đã thêm số trang vào tất cả các trang", 4000)
    except Exception as e:
        window.status.showMessage("", 0)
        show_warning(window, "Lỗi thêm số trang", str(e))
        if os.path.exists(tmp):
            os.remove(tmp)
