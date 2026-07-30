"""Phase 2 document operations: watermark, password, compress, export-to-image."""
from __future__ import annotations

import io
import os

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QSpinBox, QSlider,
    QComboBox, QCheckBox, QFileDialog, QInputDialog,
    QColorDialog, QMessageBox, QProgressDialog, QApplication,
)
from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtGui import QColor

from app.actions._guard import require_document
from app.actions._pdf_save import (
    make_staged_pdf_path,
    pdf_write_slot,
    remove_path_quietly,
    replace_file_with_retry,
    replace_document_with_staged,
)
from app.dialogs import show_warning, show_info


# ─── helpers ─────────────────────────────────────────────────────────────────

def _tmp_pdf():
    current_target = getattr(_tmp_pdf, "_current_target_path", None)
    if not current_target:
        raise RuntimeError("Temporary PDF target path is not configured.")
    return make_staged_pdf_path(current_target)


def _set_tmp_target(path: str):
    _tmp_pdf._current_target_path = path


def _document_read_and_target_paths(window) -> tuple[str | None, str | None]:
    read_path = getattr(window, "current_path", None)
    target_path = window.get_display_path() if hasattr(window, "get_display_path") else None
    return read_path, target_path or read_path


def _resolve_reportlab_font(bold: bool = False) -> str:
    fallback = "Helvetica-Bold" if bold else "Helvetica"
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from packages.platform.fonts import get_vietnamese_font_path

        font_path = get_vietnamese_font_path(bold=bold)
        if not font_path:
            return fallback

        font_name = "ThreeTUnicodeBold" if bold else "ThreeTUnicode"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception:
        return fallback


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
    c.setFont(_resolve_reportlab_font(True), int(size))
    c.saveState()
    c.translate(w / 2, h / 2)
    c.rotate(angle)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    buf.seek(0)
    return buf.read()


_WATERMARK_MARKER_KEY = "/_3TWatermarkCount"


def _mark_watermark_added(page) -> None:
    """Tag a page so `_remove_last_overlay_draw` can confidently identify
    overlays added by this app and not strip arbitrary native PDF content."""
    try:
        existing = page.obj.get(_WATERMARK_MARKER_KEY)
        current = int(existing) if existing is not None else 0
    except Exception:
        current = 0
    try:
        page.obj[_WATERMARK_MARKER_KEY] = current + 1
    except Exception:
        pass


def _remove_last_overlay_draw(pdf, page) -> bool:
    import pikepdf

    # Only strip overlays we recorded ourselves — otherwise we risk eating the
    # final legitimate `q ... /XObject Do Q` block of an unrelated PDF.
    marker_value = page.obj.get(_WATERMARK_MARKER_KEY)
    try:
        remaining_marker = int(marker_value) if marker_value is not None else 0
    except Exception:
        remaining_marker = 0
    if remaining_marker <= 0:
        return False

    contents = page.obj.get("/Contents")
    if contents is None:
        return False

    stripped_overlay = False
    if isinstance(contents, pikepdf.Array):
        if len(contents) > 1:
            del contents[-1]
            stripped_overlay = True
        elif len(contents) == 1:
            content_obj = contents[0]
        else:
            return False
    else:
        content_obj = contents

    if not stripped_overlay:
        try:
            raw = bytes(content_obj)
        except Exception:
            return False
        if not raw:
            return False

        stripped = raw.rstrip()
        start = stripped.rfind(b"\nq")
        if start < 0 and stripped.startswith(b"q"):
            start = 0
        tail = stripped[start:] if start >= 0 else b""
        if start >= 0 and b" Do" in tail and tail.endswith(b"Q"):
            new_stream = pikepdf.Stream(pdf, raw[:start].rstrip() + b"\n")
            if isinstance(contents, pikepdf.Array):
                contents[0] = new_stream
            else:
                page.obj["/Contents"] = new_stream
            stripped_overlay = True

    if not stripped_overlay:
        return False

    if remaining_marker > 1:
        page.obj[_WATERMARK_MARKER_KEY] = remaining_marker - 1
    else:
        try:
            del page.obj[_WATERMARK_MARKER_KEY]
        except Exception:
            pass
    return True


@require_document(show_message=True)
def add_watermark(window):
    dlg = _WatermarkDialog(window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    p = dlg.params()
    if not p["text"]:
        return

    read_path, target_path = _document_read_and_target_paths(window)
    if read_path and target_path and os.path.abspath(str(read_path)) != os.path.abspath(str(target_path)):
        show_warning(
            window,
            "Không thể thêm watermark trên file đang giải mã",
            "Hãy xóa mật khẩu hoặc mở lại file gốc trước khi thêm watermark để tránh ghi nhầm vào bản tạm.",
        )
        return
    src = target_path or read_path
    _set_tmp_target(src)
    out = _tmp_pdf()

    progress_dlg = None
    try:
        import pikepdf

        cur_page = 0
        try:
            cur_page = max(0, window.viewer.get_current_page() - 1)
        except Exception:
            pass

        with pdf_write_slot(src):
            with pikepdf.open(src) as pdf:
                total = len(pdf.pages)
                target_pages = list(range(total)) if p["all_pages"] else [cur_page]

                # Render watermark (reportlab) + overlay (pikepdf) từng trang chạy
                # đồng bộ trên UI thread - với file nhiều trang, không progress
                # feedback nào khiến app trông như bị đơ. Pump Qt events qua 1
                # QProgressDialog window-modal (chặn tương tác khác với cửa sổ
                # chính trong lúc chạy, giống các progress dialog khác trong app)
                # để UI vẫn phản hồi/vẽ lại được. Chỉ hiện khi >1 trang - trang
                # đơn giữ nguyên hành vi cũ (không có dialog nào xuất hiện).
                if len(target_pages) > 1:
                    progress_dlg = QProgressDialog(
                        "Đang thêm watermark...", "Hủy", 0, len(target_pages), window
                    )
                    progress_dlg.setWindowTitle("Watermark")
                    progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
                    progress_dlg.setMinimumDuration(400)

                for idx, i in enumerate(target_pages):
                    if progress_dlg is not None:
                        if progress_dlg.wasCanceled():
                            window.status.showMessage("Đã hủy thêm watermark.", 3000)
                            return
                        progress_dlg.setValue(idx)
                        QApplication.processEvents()

                    page = pdf.pages[i]
                    mbox = page.mediabox
                    w = float(mbox[2]) - float(mbox[0])
                    h = float(mbox[3]) - float(mbox[1])

                    wm_data = _watermark_page_bytes(
                        w, h, p["text"], p["size"],
                        p["color"], p["angle"], p["opacity"]
                    )

                    with pikepdf.open(io.BytesIO(wm_data)) as wm_pdf:
                        page.add_overlay(wm_pdf.pages[0])
                    _mark_watermark_added(page)

                pdf.save(out)

            replace_document_with_staged(window, out, target_path=src)
        scope = "tất cả trang" if p["all_pages"] else "trang hiện tại"
        window.status.showMessage(f"Đã thêm watermark '{p['text']}' vào {scope}", 4000)

    except Exception as e:
        show_warning(window, "Lỗi watermark", str(e))
        remove_path_quietly(out)
    finally:
        if progress_dlg is not None:
            progress_dlg.close()


@require_document(show_message=True)
def remove_watermark(window):
    """Remove the last overlay content stream, matching watermarks created by this app."""
    reply = QMessageBox.question(
        window,
        "Xóa watermark",
        "Tính năng này chỉ gỡ lớp overlay cuối cùng trên trang.\n\n"
        "Cách này phù hợp với watermark vừa được 3T Reader thêm vào. "
        "Nếu PDF gốc có lớp nội dung đặc biệt, hãy lưu bản sao trước khi tiếp tục.\n\n"
        "Tiếp tục xóa watermark?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    scope, ok = QInputDialog.getItem(
        window,
        "Phạm vi xóa watermark",
        "Áp dụng:",
        ["Tất cả trang", "Trang hiện tại"],
        0,
        False,
    )
    if not ok:
        return

    read_path, target_path = _document_read_and_target_paths(window)
    if read_path and target_path and os.path.abspath(str(read_path)) != os.path.abspath(str(target_path)):
        show_warning(
            window,
            "Không thể xóa watermark trên file đang giải mã",
            "Hãy xóa mật khẩu hoặc mở lại file gốc trước khi xóa watermark để tránh ghi nhầm vào bản tạm.",
        )
        return
    src = target_path or read_path
    _set_tmp_target(src)
    out = _tmp_pdf()

    try:
        import pikepdf

        cur_page = 0
        try:
            cur_page = max(0, window.viewer.get_current_page() - 1)
        except Exception:
            pass

        removed = 0
        with pdf_write_slot(src):
            with pikepdf.open(src) as pdf:
                total = len(pdf.pages)
                target_pages = range(total) if scope == "Tất cả trang" else [cur_page]

                for i in target_pages:
                    page = pdf.pages[i]
                    if _remove_last_overlay_draw(pdf, page):
                        removed += 1

                if removed <= 0:
                    show_warning(
                        window,
                        "Không tìm thấy lớp watermark",
                        "Không thấy lớp overlay có thể gỡ an toàn. "
                        "Watermark cũ hoặc watermark từ phần mềm khác có thể đã được trộn vào nội dung gốc.",
                    )
                    return

                pdf.save(out)

            if os.path.abspath(str(read_path)) != os.path.abspath(str(src)):
                replace_file_with_retry(out, src, window=window)
            else:
                replace_document_with_staged(window, out, target_path=src)
        window.status.showMessage(f"Đã xóa watermark trên {removed} trang", 4000)

    except Exception as e:
        show_warning(window, "Lỗi xóa watermark", str(e))
        remove_path_quietly(out)


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
    read_path, target_path = _document_read_and_target_paths(window)
    src = target_path or read_path
    
    import pikepdf
    try:
        test_doc = pikepdf.open(src)
        test_doc.close()
    except pikepdf.PasswordError:
        show_warning(window, "Đã có mật khẩu", "File này đã được đặt mật khẩu. Vui lòng xóa mật khẩu hiện tại trước khi đặt mật khẩu mới.")
        return
    except Exception as e:
        show_warning(window, "Lỗi kiểm tra tệp", str(e))
        return

    dlg = _PasswordDialog(window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    pw  = dlg.password()
    _set_tmp_target(src)
    out = _tmp_pdf()

    try:
        with pdf_write_slot(src):
            with pikepdf.open(read_path) as doc:
                doc.save(
                    out,
                    encryption=pikepdf.Encryption(
                        owner=pw + "_owner",
                        user=pw,
                        R=6,
                    )
                )
            if os.path.abspath(str(read_path)) != os.path.abspath(str(src)):
                replace_file_with_retry(out, src, window=window)
            else:
                # The file on disk becomes encrypted, but the viewer/thumbnails
                # cannot render an encrypted PDF. Keep a decrypted snapshot as the
                # viewing temp (same layout as opening an encrypted file).
                import shutil
                import tempfile
                import uuid

                from app.actions._pdf_save import (
                    current_viewer_page,
                    release_viewer_file_lock,
                    reload_document,
                )

                temp_dir = os.path.join(tempfile.gettempdir(), "3t_reader_decrypted")
                os.makedirs(temp_dir, exist_ok=True)
                view_temp = os.path.join(temp_dir, f"{uuid.uuid4().hex}.pdf")
                shutil.copy2(read_path, view_temp)

                page = current_viewer_page(window)
                release_viewer_file_lock(window)
                replace_file_with_retry(out, src, attempts=15, window=window)
                try:
                    from app.local_server import LocalPDFJSServer
                    LocalPDFJSServer.get().invalidate_pdf_cache(src)
                except Exception:
                    pass
                reload_document(
                    window,
                    view_temp,
                    page=page,
                    display_path=src,
                    temp_path=view_temp,
                )
        window.status.showMessage("Đã đặt mật khẩu PDF", 4000)
    except Exception as e:
        show_warning(window, "Lỗi đặt mật khẩu", str(e))
        remove_path_quietly(out)


@require_document(show_message=True)
def remove_pdf_password(window):
    src = window.get_display_path() or window.current_path

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

        _set_tmp_target(src)
        out = _tmp_pdf()
        with pdf_write_slot(src):
            try:
                with pikepdf.open(src, password=pw) as doc:
                    doc.save(out)
            except pikepdf.PasswordError:
                show_warning(window, "Sai mật khẩu", "Mật khẩu không đúng.")
                remove_path_quietly(out)
                return

            # TC34: viewer đang hiển thị bản temp giải mã (file gốc mã hóa) nên
            # không thể soft-reload sang path khác — sau khi release lock, webview
            # đang ở about:blank, reload_soft chạy JS trên trang trắng → màn hình
            # đen. Phải hard-load lại file đã giải mã (load_pdf + retry-if-blank).
            from app.actions._pdf_save import (
                current_viewer_page,
                release_viewer_file_lock,
                reload_document,
            )

            page = current_viewer_page(window)
            release_viewer_file_lock(window)
            replace_file_with_retry(out, src, attempts=15, window=window)
            try:
                from app.local_server import LocalPDFJSServer
                LocalPDFJSServer.get().invalidate_pdf_cache(src)
            except Exception:
                pass
            reload_document(
                window,
                src,
                page=page,
                display_path=src,
                temp_path=None,
            )
        window.status.showMessage("Đã xóa mật khẩu PDF", 4000)
    except Exception as e:
        show_warning(window, "Lỗi xóa mật khẩu", str(e))


# ─── Compress ────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def compress_pdf(window):
    read_path, target_path = _document_read_and_target_paths(window)
    if read_path and target_path and os.path.abspath(str(read_path)) != os.path.abspath(str(target_path)):
        show_warning(
            window,
            "Không thể nén file đang giải mã",
            "Hãy xóa mật khẩu hoặc mở lại file gốc trước khi nén PDF để tránh sai lệch trạng thái mã hóa.",
        )
        return

    src = target_path or read_path
    _set_tmp_target(src)
    out = _tmp_pdf()

    try:
        import pikepdf
        orig_size = os.path.getsize(src)
        with pdf_write_slot(src):
            with pikepdf.open(src) as doc:
                doc.save(
                    out,
                    compress_streams=True,
                    recompress_flate=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                )

            new_size = os.path.getsize(out)
            replace_document_with_staged(window, out, target_path=src)

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
        remove_path_quietly(out)


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

    read_path, target_path = _document_read_and_target_paths(window)
    if read_path and target_path and os.path.abspath(str(read_path)) != os.path.abspath(str(target_path)):
        show_warning(
            window,
            "Không thể xuất ảnh từ file đang giải mã",
            "Hãy xóa mật khẩu hoặc mở lại file gốc trước khi xuất ảnh để tránh ghi nhầm vào bản tạm.",
        )
        return
    src = target_path or read_path

    from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK
    with PDFIUM_LOCK:
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
    max_render_pixels = 24_000_000

    window.status.showMessage("Đang xuất ảnh…", 0)
    try:
        # TC35: nhiều trang → ghi thẳng từng ảnh vào một file ZIP (writestr),
        # không rải ảnh lẻ ra thư mục đích. Một trang → giữ hành vi cũ.
        make_zip = len(page_list) > 1
        zip_path = ""
        if make_zip:
            import zipfile
            zip_path = os.path.join(out_dir, f"{base_name}_images.zip")
            counter = 2
            while os.path.exists(zip_path):
                zip_path = os.path.join(out_dir, f"{base_name}_images_{counter}.zip")
                counter += 1

        done = 0
        result_path = ""
        zf = None
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(src)
            try:
                if make_zip:
                    import zipfile
                    zf = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)
                for pg in page_list:
                    page = doc[pg - 1]
                    try:
                        width = float(page.get_width())
                        height = float(page.get_height())
                        area = max(1.0, width * height)
                        capped_scale = min(scale, (max_render_pixels / area) ** 0.5)
                        bitmap  = page.render(scale=max(0.25, capped_scale))
                        pil_img = bitmap.to_pil()
                        img_name = f"{base_name}_trang{pg:03d}.{p['ext']}"
                        if zf is not None:
                            import io
                            buf = io.BytesIO()
                            pil_img.save(buf, format=p["fmt"])
                            zf.writestr(img_name, buf.getvalue())
                        else:
                            result_path = os.path.join(out_dir, img_name)
                            pil_img.save(result_path)
                    finally:
                        page.close()
                    done += 1
                    window.status.showMessage(f"Đang xuất trang {pg}… ({done}/{len(page_list)})", 0)
            finally:
                doc.close()
                if zf is not None:
                    zf.close()
        if make_zip:
            result_path = zip_path

        zip_note = f" (đã nén vào {os.path.basename(zip_path)})" if make_zip else ""
        window.status.showMessage(
            f"Đã xuất {done} ảnh {p['fmt']} vào: {out_dir}{zip_note}", 6000
        )
        import subprocess, sys
        if sys.platform == "darwin":
            if result_path:
                subprocess.Popen(["open", "-R", result_path])
            else:
                subprocess.Popen(["open", out_dir])
        elif sys.platform == "win32":
            if result_path:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(result_path)])
            else:
                subprocess.Popen(["explorer", out_dir])
    except Exception as e:
        window.status.showMessage("", 0)
        show_warning(window, "Lỗi xuất ảnh", str(e))


# ── Export PDF to Text ────────────────────────────────────────────────────────

@require_document(show_message=True)
def export_pdf_to_text(window):
    """Trích xuất toàn bộ văn bản từ PDF ra file .txt."""
    import pypdfium2 as pdfium

    read_path, target_path = _document_read_and_target_paths(window)
    if read_path and target_path and os.path.abspath(str(read_path)) != os.path.abspath(str(target_path)):
        show_warning(
            window,
            "Không thể xuất văn bản từ file đang giải mã",
            "Hãy xóa mật khẩu hoặc mở lại file gốc trước khi xuất văn bản để tránh ghi nhầm vào bản tạm.",
        )
        return
    src = target_path or read_path
    base_name = os.path.splitext(os.path.basename(src))[0]

    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu file văn bản", f"{base_name}.txt", "Text Files (*.txt)"
    )
    if not out_path:
        return

    window.status.showMessage("Đang trích xuất văn bản…", 0)
    try:
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK
        lines = []
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(src)
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
    import io
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


_PAGENUM_MARKER_KEY = "/_3TPageNumMarker"

def _mark_pagenum_added(page) -> None:
    try:
        existing = page.obj.get(_PAGENUM_MARKER_KEY)
        current = int(existing) if existing is not None else 0
    except Exception:
        current = 0
    try:
        page.obj[_PAGENUM_MARKER_KEY] = current + 1
    except Exception:
        pass


def _remove_pagenums(pdf, page) -> bool:
    import pikepdf

    marker_value = page.obj.get(_PAGENUM_MARKER_KEY)
    try:
        remaining_marker = int(marker_value) if marker_value is not None else 0
    except Exception:
        remaining_marker = 0
    if remaining_marker <= 0:
        return False

    contents = page.obj.get("/Contents")
    if contents is None:
        return False

    stripped_overlay = False
    if isinstance(contents, pikepdf.Array):
        if len(contents) > 1:
            del contents[-1]
            stripped_overlay = True
        elif len(contents) == 1:
            content_obj = contents[0]
        else:
            return False
    else:
        content_obj = contents

    if not stripped_overlay:
        try:
            raw = bytes(content_obj)
        except Exception:
            return False
        if not raw:
            return False

        stripped = raw.rstrip()
        start = stripped.rfind(b"\nq")
        if start < 0 and stripped.startswith(b"q"):
            start = 0
        tail = stripped[start:] if start >= 0 else b""
        if start >= 0 and b" Do" in tail and tail.endswith(b"Q"):
            new_stream = pikepdf.Stream(pdf, raw[:start].rstrip() + b"\n")
            if isinstance(contents, pikepdf.Array):
                contents[0] = new_stream
            else:
                page.obj["/Contents"] = new_stream
            stripped_overlay = True

    if not stripped_overlay:
        return False

    if remaining_marker > 1:
        page.obj[_PAGENUM_MARKER_KEY] = remaining_marker - 1
    else:
        try:
            del page.obj[_PAGENUM_MARKER_KEY]
        except Exception:
            pass
    return True


@require_document(show_message=True)
def add_page_numbers(window):
    """Thêm số trang vào cuối mỗi trang PDF."""
    from app.actions.pages import _auto_commit_edit_state
    if not _auto_commit_edit_state(window):
        return

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

    read_path, target_path = _document_read_and_target_paths(window)
    display_src = target_path or read_path or ""
    if os.path.splitext(str(display_src))[1].lower() != ".pdf":
        show_warning(window, "Khong the danh so trang", "Chi ho tro danh so trang cho tai lieu PDF.")
        return
    src = target_path or read_path
    _set_tmp_target(src)
    tmp = _tmp_pdf()
    window.status.showMessage("Đang thêm số trang…", 0)
    try:
        import pikepdf
        import io

        font_size = 10
        margin    = 20

        with pdf_write_slot(src):
            with pikepdf.open(src) as pdf:
                for i, page in enumerate(pdf.pages):
                    num   = start_num + i
                    label = str(num)

                    mbox = page.mediabox
                    w = float(mbox[2]) - float(mbox[0])
                    h = float(mbox[3]) - float(mbox[1])

                    # Remove existing page numbers before adding new ones
                    while _remove_pagenums(pdf, page):
                        pass

                    overlay_data = _page_number_overlay_bytes(
                        w, h, label, font_size, margin, position
                    )

                    with pikepdf.open(io.BytesIO(overlay_data)) as ol_pdf:
                        page.add_overlay(ol_pdf.pages[0])
                    _mark_pagenum_added(page)

                pdf.save(tmp)

            replace_document_with_staged(window, tmp, target_path=src, soft_reload=True)
        window.status.showMessage("Đã thêm số trang vào tất cả các trang", 4000)
    except Exception as e:
        window.status.showMessage("", 0)
        show_warning(window, "Lỗi thêm số trang", str(e))
        remove_path_quietly(tmp)


@require_document(show_message=True)
def remove_page_numbers(window):
    """Xóa các số trang đã được thêm vào."""
    from app.actions.pages import _auto_commit_edit_state
    if not _auto_commit_edit_state(window):
        return

    read_path, target_path = _document_read_and_target_paths(window)
    display_src = target_path or read_path or ""
    if os.path.splitext(str(display_src))[1].lower() != ".pdf":
        show_warning(window, "Khong the xoa so trang", "Chi ho tro xoa so trang cho tai lieu PDF.")
        return
    src = target_path or read_path
    _set_tmp_target(src)
    tmp = _tmp_pdf()
    window.status.showMessage("Đang xóa số trang…", 0)
    try:
        import pikepdf
        deleted = False
        with pdf_write_slot(src):
            with pikepdf.open(src) as pdf:
                for page in pdf.pages:
                    while _remove_pagenums(pdf, page):
                        deleted = True
                pdf.save(tmp)

            if deleted:
                replace_document_with_staged(window, tmp, target_path=src, soft_reload=True)
                window.status.showMessage("Đã xóa số trang thành công", 4000)
            else:
                remove_path_quietly(tmp)
                window.status.showMessage("Không tìm thấy số trang nào để xóa", 4000)
    except Exception as e:
        window.status.showMessage("", 0)
        show_warning(window, "Lỗi xóa số trang", str(e))
        remove_path_quietly(tmp)
