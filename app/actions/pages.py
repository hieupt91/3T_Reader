import os

from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
    QListWidget, QAbstractItemView, QComboBox,
)
from packages.pdf_engine import get_pdf_engine
from app.actions._guard import require_document
from app.actions._pdf_save import make_staged_pdf_path, remove_path_quietly, replace_document_with_staged
from app.dialogs import show_info, show_warning
from app.actions.file import open_file


def _current_pdf_path(window) -> str | None:
    state = window._active_state() if hasattr(window, "_active_state") else None
    if state:
        return state.get("source_path") or state.get("display_path")
    return getattr(window, "current_path", None)


def _pick_save_path(window, suggested: str) -> str | None:
    path, _ = QFileDialog.getSaveFileName(
        window, "Lưu file PDF", suggested, "PDF Files (*.pdf)"
    )
    return path or None


def _reload(window, path: str):
    try:
        page = window.viewer.get_current_page()
    except Exception:
        page = 1
    window.current_path = path
    zoom = str(getattr(getattr(window, "zoom_spin", None), "value", lambda: 100)())
    window.viewer.load_pdf(path, page=max(1, page), zoom=zoom)
    if hasattr(window, "_active_state") and window._active_state() is not None:
        window._active_state()["source_path"] = path
        window._active_state()["display_path"] = path


# ─────────────────────────────────────────────────────────────────────────────
#  WATERMARK
# ─────────────────────────────────────────────────────────────────────────────

class _WatermarkDialog(QDialog):
    def __init__(self, parent=None, total_pages: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Thêm Watermark")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.text_input = QLineEdit("BẢN NHÁP")
        form.addRow("Nội dung:", self.text_input)

        self.angle_spin = QSpinBox()
        self.angle_spin.setRange(0, 360)
        self.angle_spin.setValue(45)
        self.angle_spin.setSuffix("°")
        form.addRow("Góc nghiêng:", self.angle_spin)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["Xám nhạt", "Xám đậm", "Đỏ nhạt", "Xanh nhạt"])
        form.addRow("Màu:", self.color_combo)

        self.pages_combo = QComboBox()
        self.pages_combo.addItems(["Tất cả trang", "Trang hiện tại"])
        form.addRow("Áp dụng:", self.pages_combo)

        self._total = total_pages
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self.text_input.text().strip()

    def angle(self) -> float:
        return float(self.angle_spin.value())

    def color(self) -> tuple:
        colors = {
            "Xám nhạt": (0.75, 0.75, 0.75),
            "Xám đậm":  (0.40, 0.40, 0.40),
            "Đỏ nhạt":  (0.85, 0.55, 0.55),
            "Xanh nhạt":(0.55, 0.65, 0.85),
        }
        return colors.get(self.color_combo.currentText(), (0.70, 0.70, 0.70))

    def apply_to_pages(self, current_page: int) -> list[int] | None:
        if self.pages_combo.currentText() == "Trang hiện tại":
            return [current_page]
        return None  # None = all pages


@require_document(show_message=True)
def watermark_document(window):
    path = _current_pdf_path(window)
    if not path:
        return
    try:
        total = get_pdf_engine().page_count(path)
    except Exception:
        total = 1
    try:
        current = window.viewer.get_current_page()
    except Exception:
        current = 1

    dlg = _WatermarkDialog(window, total_pages=total)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    wm_text = dlg.text()
    if not wm_text:
        show_warning(window, "Thiếu nội dung", "Nhập nội dung watermark.")
        return

    out_path = _pick_save_path(window, os.path.splitext(path)[0] + "_watermark.pdf")
    if not out_path:
        return

    try:
        get_pdf_engine().watermark_pdf(
            path, out_path,
            text=wm_text,
            color=dlg.color(),
            angle=dlg.angle(),
            apply_to_pages=dlg.apply_to_pages(current),
        )
    except Exception as e:
        show_warning(window, "Lỗi watermark", str(e))
        return

    if QMessageBox.question(
        window, "Mở file mới?",
        f"Đã tạo:\n{out_path}\n\nMở file này không?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    ) == QMessageBox.StandardButton.Yes:
        open_file(window, out_path)
    else:
        window.status.showMessage(f"Đã lưu watermark: {os.path.basename(out_path)}", 4000)


# ─────────────────────────────────────────────────────────────────────────────
#  XÓA / XOAY TRANG
# ─────────────────────────────────────────────────────────────────────────────

class _PageRangeDialog(QDialog):
    def __init__(self, parent=None, total_pages: int = 1, title: str = "Chọn trang", current_page: int = 1):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Tổng số trang: {total_pages}"))

        form = QFormLayout()
        self.from_spin = QSpinBox()
        self.from_spin.setRange(1, total_pages)
        self.from_spin.setValue(current_page)
        form.addRow("Từ trang:", self.from_spin)

        self.to_spin = QSpinBox()
        self.to_spin.setRange(1, total_pages)
        self.to_spin.setValue(current_page)
        form.addRow("Đến trang:", self.to_spin)

        layout.addLayout(form)

        layout.addWidget(QLabel("(Để cùng số = chỉ 1 trang)"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def page_range(self) -> tuple[int, int]:
        a = self.from_spin.value()
        b = self.to_spin.value()
        return (min(a, b), max(a, b))


@require_document(show_message=True)
def delete_pages_action(window):
    path = _current_pdf_path(window)
    if not path:
        return
    try:
        total = get_pdf_engine().page_count(path)
    except Exception:
        total = 1
    try:
        current = window.viewer.get_current_page()
    except Exception:
        current = 1

    if total <= 1:
        show_warning(window, "Không thể xóa", "PDF chỉ có 1 trang, không thể xóa.")
        return

    dlg = _PageRangeDialog(window, total_pages=total,
                            title="Xóa trang", current_page=current)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    start, end = dlg.page_range()
    pages_to_del = list(range(start, end + 1))

    if len(pages_to_del) >= total:
        show_warning(window, "Không thể xóa", "Không thể xóa tất cả các trang.")
        return

    confirm = QMessageBox.question(
        window, "Xác nhận xóa",
        f"Xóa trang {start}–{end} ({len(pages_to_del)} trang)?\nThao tác này không thể hoàn tác.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    tmp = make_staged_pdf_path(path)
    new_page = min(start, total - len(pages_to_del))
    try:
        get_pdf_engine().delete_pages(path, tmp, pages_to_del)
        replace_document_with_staged(window, tmp, target_path=path, page=max(1, new_page))
    except Exception as e:
        remove_path_quietly(tmp)
        show_warning(window, "Lỗi xóa trang", str(e))
        return

    if hasattr(window, "_active_state") and window._active_state():
        window._active_state()["source_path"] = path
    window.status.showMessage(f"Đã xóa trang {start}–{end}", 4000)


@require_document(show_message=True)
def rotate_pages_action(window):
    path = _current_pdf_path(window)
    if not path:
        return
    try:
        total = get_pdf_engine().page_count(path)
    except Exception:
        total = 1
    try:
        current = window.viewer.get_current_page()
    except Exception:
        current = 1

    dlg = QDialog(window)
    dlg.setWindowTitle("Xoay trang")
    dlg.setMinimumWidth(280)
    layout = QVBoxLayout(dlg)

    form = QFormLayout()
    page_spin = QSpinBox()
    page_spin.setRange(1, total)
    page_spin.setValue(current)
    form.addRow("Trang:", page_spin)

    angle_combo = QComboBox()
    angle_combo.addItems(["90° (thuận chiều kim đồng hồ)", "180°", "270° (ngược chiều kim đồng hồ)"])
    form.addRow("Góc xoay:", angle_combo)

    layout.addLayout(form)

    apply_all = QPushButton("Xoay TẤT CẢ trang")
    layout.addWidget(apply_all)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    _all_pages = [False]
    apply_all.clicked.connect(lambda: _all_pages.__setitem__(0, True) or dlg.accept())

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    angle_map = {0: 90, 1: 180, 2: 270}
    deg = angle_map[angle_combo.currentIndex()]

    if _all_pages[0]:
        rotations = {pn: deg for pn in range(1, total + 1)}
    else:
        rotations = {page_spin.value(): deg}

    # --- Bắt đầu: Zero-reload Lazy Rotation ---
    page_target = 0 if _all_pages[0] else page_spin.value()
    js_code = f"""
        (function() {{
            let angle = {deg};
            let pageNum = {page_target};
            
            // Xoay bằng CSS Transform để mượt nhất và không kích hoạt render lại canvas của PDF.js
            function applyCSSRotation(targetPage, rot) {{
                let pageDiv = document.querySelector(`.page[data-page-number="${{targetPage}}"]`);
                if (pageDiv) {{
                    let currentRot = parseInt(pageDiv.getAttribute('data-css-rotation') || '0');
                    let newRot = (currentRot + rot) % 360;
                    pageDiv.setAttribute('data-css-rotation', newRot);
                    pageDiv.style.transition = 'transform 0.25s ease';
                    pageDiv.style.transform = `rotate(${{newRot}}deg)`;
                }}
                
                let thumbDiv = document.querySelector(`.thumbnail[data-page-number="${{targetPage}}"]`);
                if (thumbDiv) {{
                    let currentRot = parseInt(thumbDiv.getAttribute('data-css-rotation') || '0');
                    let newRot = (currentRot + rot) % 360;
                    thumbDiv.setAttribute('data-css-rotation', newRot);
                    
                    let thumbImg = thumbDiv.querySelector('.thumbnailImage') || thumbDiv.querySelector('canvas') || thumbDiv;
                    thumbImg.style.transition = 'transform 0.25s ease';
                    thumbImg.style.transform = `rotate(${{newRot}}deg)`;
                }}
            }}

            if (pageNum === 0) {{
                // Xoay tất cả
                let allPages = document.querySelectorAll('.page');
                allPages.forEach(p => {{
                    let pn = p.getAttribute('data-page-number');
                    if (pn) applyCSSRotation(parseInt(pn), angle);
                }});
            }} else {{
                // Xoay 1 trang
                applyCSSRotation(pageNum, angle);
            }}
        }})();
    """
    try:
        window.viewer.page().runJavaScript(js_code)
    except Exception:
        pass

    try:
        if hasattr(window, "sidebar") and window.sidebar.isVisible():
            from packages.qt_compat.QtGui import QTransform, QIcon
            from packages.qt_compat.QtCore import Qt
            size = window.sidebar.list.iconSize()
            for pn, rdeg in rotations.items():
                item = window.sidebar.list.item(pn - 1)
                if item:
                    pixmap = item.icon().pixmap(size)
                    if not pixmap.isNull():
                        transform = QTransform().rotate(rdeg)
                        rotated = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                        item.setIcon(QIcon(rotated))
                        window.sidebar._loaded_pages.discard(pn)
    except Exception:
        pass

    def _burn_rotation_in_background():
        import shutil
        import tempfile
        tmp = make_staged_pdf_path(path)
        try:
            get_pdf_engine().rotate_pages(path, tmp, rotations)
            shutil.move(tmp, path)
        except Exception as e:
            remove_path_quietly(tmp)
            try:
                with open(os.path.join(tempfile.gettempdir(), "3t_error_log.txt"), "a") as f:
                    f.write(f"Background rotate error: {e}\n")
            except Exception:
                pass

    import threading
    threading.Thread(target=_burn_rotation_in_background, daemon=True).start()
    # --- Kết thúc: Zero-reload Lazy Rotation ---

    if hasattr(window, "_active_state") and window._active_state():
        window._active_state()["source_path"] = path
    window.status.showMessage(f"Đã xoay {len(rotations)} trang {deg}°", 4000)


# ─────────────────────────────────────────────────────────────────────────────
#  GỘP PDF
# ─────────────────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def merge_pdfs_action(window):
    path = _current_pdf_path(window)
    if not path:
        return

    other_paths, _ = QFileDialog.getOpenFileNames(
        window, "Chọn các file PDF để gộp vào cuối", "", "PDF Files (*.pdf)"
    )
    if not other_paths:
        return

    out_path = _pick_save_path(
        window,
        os.path.splitext(path)[0] + "_gop.pdf"
    )
    if not out_path:
        return

    all_paths = [path] + list(other_paths)
    try:
        get_pdf_engine().merge_pdfs(all_paths, out_path)
    except Exception as e:
        show_warning(window, "Lỗi gộp PDF", str(e))
        return

    total_files = len(all_paths)
    if QMessageBox.question(
        window, "Mở file đã gộp?",
        f"Đã gộp {total_files} file thành:\n{os.path.basename(out_path)}\n\nMở không?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    ) == QMessageBox.StandardButton.Yes:
        open_file(window, out_path)
    else:
        window.status.showMessage(f"Đã gộp {total_files} PDF → {os.path.basename(out_path)}", 5000)


# ─────────────────────────────────────────────────────────────────────────────
#  TÁCH PDF
# ─────────────────────────────────────────────────────────────────────────────

class _SplitDialog(QDialog):
    def __init__(self, parent=None, total_pages: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Tách PDF")
        self.setMinimumWidth(360)
        self._total = total_pages
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Tổng số trang: {total_pages}"))
        layout.addWidget(QLabel("Nhập các phạm vi trang, mỗi dòng một phạm vi.\nVí dụ:\n  1-3\n  4-6\n  7"))

        self.ranges_edit = QListWidget()
        self.ranges_edit.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.ranges_edit)

        row = QHBoxLayout()
        self.from_spin = QSpinBox()
        self.from_spin.setRange(1, total_pages)
        self.from_spin.setValue(1)
        self.to_spin = QSpinBox()
        self.to_spin.setRange(1, total_pages)
        self.to_spin.setValue(total_pages)
        add_btn = QPushButton("Thêm phạm vi")
        add_btn.clicked.connect(self._add_range)
        del_btn = QPushButton("Xóa")
        del_btn.clicked.connect(self._del_range)
        row.addWidget(QLabel("Từ:"))
        row.addWidget(self.from_spin)
        row.addWidget(QLabel("Đến:"))
        row.addWidget(self.to_spin)
        row.addWidget(add_btn)
        row.addWidget(del_btn)
        layout.addLayout(row)

        # Preset buttons
        preset_row = QHBoxLayout()
        btn_each = QPushButton("Mỗi trang 1 file")
        btn_each.clicked.connect(self._preset_each)
        btn_half = QPushButton("Chia đôi")
        btn_half.clicked.connect(self._preset_half)
        preset_row.addWidget(btn_each)
        preset_row.addWidget(btn_half)
        layout.addLayout(preset_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_range(self):
        a = self.from_spin.value()
        b = self.to_spin.value()
        if a > b:
            a, b = b, a
        self.ranges_edit.addItem(f"{a}-{b}")

    def _del_range(self):
        for item in self.ranges_edit.selectedItems():
            self.ranges_edit.takeItem(self.ranges_edit.row(item))

    def _preset_each(self):
        self.ranges_edit.clear()
        for i in range(1, self._total + 1):
            self.ranges_edit.addItem(f"{i}-{i}")

    def _preset_half(self):
        self.ranges_edit.clear()
        mid = self._total // 2
        if mid > 0:
            self.ranges_edit.addItem(f"1-{mid}")
            self.ranges_edit.addItem(f"{mid+1}-{self._total}")

    def page_ranges(self) -> list[tuple[int, int]]:
        result = []
        for i in range(self.ranges_edit.count()):
            text = self.ranges_edit.item(i).text()
            if "-" in text:
                parts = text.split("-", 1)
                try:
                    result.append((int(parts[0]), int(parts[1])))
                except ValueError:
                    pass
            else:
                try:
                    n = int(text)
                    result.append((n, n))
                except ValueError:
                    pass
        return result


@require_document(show_message=True)
def split_pdf_action(window):
    path = _current_pdf_path(window)
    if not path:
        return
    try:
        total = get_pdf_engine().page_count(path)
    except Exception:
        total = 1

    dlg = _SplitDialog(window, total_pages=total)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    ranges = dlg.page_ranges()
    if not ranges:
        show_warning(window, "Chưa chọn phạm vi", "Thêm ít nhất 1 phạm vi trang.")
        return

    out_dir = QFileDialog.getExistingDirectory(
        window, "Chọn thư mục lưu các file đã tách"
    )
    if not out_dir:
        return

    try:
        out_paths = get_pdf_engine().split_pdf(path, out_dir, ranges)
    except Exception as e:
        show_warning(window, "Lỗi tách PDF", str(e))
        return

    show_info(
        window,
        "Tách PDF thành công",
        f"Đã tạo {len(out_paths)} file tại:\n{out_dir}"
    )
    window.status.showMessage(f"Đã tách thành {len(out_paths)} file PDF", 5000)

def extract_single_page(window, page_num: int):
    path = _current_pdf_path(window)
    if not path:
        return
    import os
    import pikepdf
    from packages.qt_compat.QtWidgets import QFileDialog
    
    default_name = f"{os.path.splitext(os.path.basename(path))[0]}_trang_{page_num}.pdf"
    out_path, _ = QFileDialog.getSaveFileName(
        window, f"Lưu trang {page_num}", default_name, "PDF Files (*.pdf)"
    )
    if not out_path:
        return
        
    try:
        with pikepdf.open(path) as pdf:
            dst = pikepdf.Pdf.new()
            dst.pages.append(pdf.pages[page_num - 1])
            dst.save(out_path)
            
        show_info(window, "Thành công", f"Đã trích xuất trang {page_num} ra:\n{os.path.basename(out_path)}")
        window.status.showMessage(f"Đã trích xuất trang {page_num} ra {os.path.basename(out_path)}", 4000)
    except Exception as e:
        show_warning(window, "Lỗi trích xuất", str(e))

def insert_blank_page(window, target_page_num: int):
    path = _current_pdf_path(window)
    if not path:
        return
        
    try:
        import pikepdf
        from app.actions.annotate import _flush_annotations_before_heavy_op, _save_pikepdf_reload
        if not _flush_annotations_before_heavy_op(window, path, "chen trang trang"):
            return
            
        with pikepdf.open(path) as pdf:
            # We want to insert AFTER the target_page_num.
            # In pikepdf, index is 0-based.
            index_to_insert = target_page_num
            
            # Find the size of the current page to match it
            current_page = pdf.pages[target_page_num - 1]
            box = current_page.mediabox
            width = float(box[2] - box[0])
            height = float(box[3] - box[1])
            
            pdf.add_blank_page(page_size=(width, height), page_index=index_to_insert)
            
            _save_pikepdf_reload(window, pdf, keep_page=True)
            
        window.status.showMessage(f"Đã chèn trang trắng sau trang {target_page_num}", 4000)
    except Exception as e:
        show_warning(window, "Lỗi chèn trang", str(e))
