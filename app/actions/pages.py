import os
import shutil
import tempfile

from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
    QListWidget, QAbstractItemView, QComboBox,
)
from packages.pdf_engine import get_pdf_engine
from app.actions._guard import require_document
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
    window.viewer.load_pdf(path, page=max(1, page), zoom="page-width")
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

    tmp = path + ".del_tmp.pdf"
    try:
        get_pdf_engine().delete_pages(path, tmp, pages_to_del)
        shutil.move(tmp, path)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        show_warning(window, "Lỗi xóa trang", str(e))
        return

    new_page = min(start, total - len(pages_to_del))
    window.current_path = path
    window.viewer.load_pdf(path, page=max(1, new_page), zoom="page-width")
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

    tmp = path + ".rot_tmp.pdf"
    try:
        get_pdf_engine().rotate_pages(path, tmp, rotations)
        shutil.move(tmp, path)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        show_warning(window, "Lỗi xoay trang", str(e))
        return

    window.current_path = path
    window.viewer.load_pdf(path, page=max(1, page_spin.value()), zoom="page-width")
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
