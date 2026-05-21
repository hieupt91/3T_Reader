import os
import shutil
import tempfile
import uuid

from packages.qt_compat.QtCore import QObject, QEventLoop, pyqtSignal, pyqtSlot
from packages.qt_compat.QtGui import QImage
from packages.qt_compat.QtWebChannel import QWebChannel
from packages.qt_compat.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from app.actions.file import open_file
from app.actions._guard import require_document
from app.dialogs import show_info, show_warning
from packages.pdf_engine import get_pdf_engine

A4_WIDTH_PT = 595
A4_HEIGHT_PT = 842

AREA_PICK_SCRIPT = r"""
(function () {
    if (window.__readerPdfAreaPickInstalled) {
        return;
    }
    window.__readerPdfAreaPickInstalled = true;

    function attachBridge() {
        if (typeof QWebChannel === 'undefined') {
            var script = document.createElement('script');
            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
            script.onload = attachBridge;
            document.head.appendChild(script);
            return;
        }

        new QWebChannel(qt.webChannelTransport, function (channel) {
            const bridge = channel.objects.areaPickBridge;
            if (!bridge) {
                return;
            }

            let dragState = null;
            let overlay = null;

            function clearOverlay() {
                if (overlay && overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                overlay = null;
            }

            function cancel() {
                document.removeEventListener('mousedown', onMouseDown, true);
                document.removeEventListener('mousemove', onMouseMove, true);
                document.removeEventListener('mouseup', onMouseUp, true);
                window.removeEventListener('keydown', onKeyDown, true);
                clearOverlay();
                try { bridge.cancelPick(); } catch (_err) {}
            }

            function onMouseDown(event) {
                const page = event.target.closest('.page');
                if (!page || !page.dataset || !page.dataset.pageNumber) {
                    return;
                }
                const pdfViewer = window.PDFViewerApplication && PDFViewerApplication.pdfViewer;
                if (!pdfViewer) {
                    return;
                }
                const pageNumber = parseInt(page.dataset.pageNumber, 10);
                const pageView = pdfViewer.getPageView
                    ? pdfViewer.getPageView(pageNumber - 1)
                    : (pdfViewer._pages && pdfViewer._pages[pageNumber - 1]);
                if (!pageView || !pageView.viewport) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const rect = page.getBoundingClientRect();
                const startX = event.clientX - rect.left;
                const startY = event.clientY - rect.top;

                dragState = {
                    page,
                    pageView,
                    pageNumber,
                    rect,
                    startX,
                    startY,
                    curX: startX,
                    curY: startY,
                };

                if (!overlay) {
                    overlay = document.createElement('div');
                    overlay.style.position = 'absolute';
                    overlay.style.border = '2px dashed #0B84F3';
                    overlay.style.background = 'rgba(11, 132, 243, 0.15)';
                    overlay.style.pointerEvents = 'none';
                    overlay.style.zIndex = '40';
                    overlay.style.boxSizing = 'border-box';
                    page.appendChild(overlay);
                } else if (overlay.parentNode !== page) {
                    if (overlay.parentNode) {
                        overlay.parentNode.removeChild(overlay);
                    }
                    page.appendChild(overlay);
                }
            }

            function onMouseMove(event) {
                if (!dragState || !overlay) {
                    return;
                }
                const x = event.clientX - dragState.rect.left;
                const y = event.clientY - dragState.rect.top;
                dragState.curX = x;
                dragState.curY = y;

                const left = Math.min(dragState.startX, x);
                const top = Math.min(dragState.startY, y);
                const width = Math.max(1, Math.abs(x - dragState.startX));
                const height = Math.max(1, Math.abs(y - dragState.startY));

                overlay.style.left = `${left}px`;
                overlay.style.top = `${top}px`;
                overlay.style.width = `${width}px`;
                overlay.style.height = `${height}px`;
            }

            function onMouseUp(event) {
                if (!dragState) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const x2 = event.clientX - dragState.rect.left;
                const y2 = event.clientY - dragState.rect.top;
                const x1 = dragState.startX;
                const y1 = dragState.startY;

                const minX = Math.min(x1, x2);
                const minY = Math.min(y1, y2);
                const maxX = Math.max(x1, x2);
                const maxY = Math.max(y1, y2);

                const p1 = dragState.pageView.viewport.convertToPdfPoint(minX, minY);
                const p2 = dragState.pageView.viewport.convertToPdfPoint(maxX, maxY);

                const left = Math.min(p1[0], p2[0]);
                const right = Math.max(p1[0], p2[0]);
                const bottom = Math.min(p1[1], p2[1]);
                const top = Math.max(p1[1], p2[1]);

                document.removeEventListener('mousedown', onMouseDown, true);
                document.removeEventListener('mousemove', onMouseMove, true);
                document.removeEventListener('mouseup', onMouseUp, true);
                window.removeEventListener('keydown', onKeyDown, true);
                clearOverlay();
                const pickedPageNumber = dragState.pageNumber;
                dragState = null;

                try {
                    bridge.reportArea(
                        pickedPageNumber,
                        left,
                        bottom,
                        right,
                        top
                    );
                } catch (_err) {}
            }

            function onKeyDown(event) {
                if (event.key === 'Escape') {
                    cancel();
                }
            }

            document.addEventListener('mousedown', onMouseDown, true);
            document.addEventListener('mousemove', onMouseMove, true);
            document.addEventListener('mouseup', onMouseUp, true);
            window.addEventListener('keydown', onKeyDown, true);
        });
    }

    attachBridge();
})();
"""


class AreaPickBridge(QObject):
    picked = pyqtSignal(int, float, float, float, float)
    cancelled = pyqtSignal()

    @pyqtSlot(int, float, float, float, float)
    def reportArea(self, page_number, left, bottom, right, top):
        self.picked.emit(page_number, left, bottom, right, top)

    @pyqtSlot()
    def cancelPick(self):
        self.cancelled.emit()


def _pick_pdf_area(window):
    from app.actions.sign import _get_web_view, _setup_webchannel, _teardown_webchannel
    web_view = _get_web_view(window)
    if web_view is None:
        return None

    bridge = AreaPickBridge(window)
    _setup_webchannel(web_view, window, "areaPickBridge", bridge)

    result = {}
    loop = QEventLoop(window)

    def _finish(page_number, left, bottom, right, top):
        result.update(
            {
                "page_number": max(1, int(page_number)),
                "box": (left, bottom, right, top),
            }
        )
        if loop.isRunning():
            loop.quit()

    def _cancel():
        result.clear()
        if loop.isRunning():
            loop.quit()

    bridge.picked.connect(_finish)
    bridge.cancelled.connect(_cancel)

    try:
        web_view.page().runJavaScript(AREA_PICK_SCRIPT)
        loop.exec()
    finally:
        _teardown_webchannel(web_view)

    return result or None


def _begin_edit_mode(window, mode_key: str, status_text: str):
    handler = getattr(window, "begin_edit_mode", None)
    if callable(handler):
        handler(mode_key, status_text)
    else:
        window.status.showMessage(status_text, 5000)


def _end_edit_mode(window, status_text: str | None = None):
    handler = getattr(window, "end_edit_mode", None)
    if callable(handler):
        handler(status_text)
    elif status_text:
        window.status.showMessage(status_text, 3500)


def _edit_state_store(window):
    active_state = window._active_state() if hasattr(window, "_active_state") else None
    if active_state is not None:
        active_state.setdefault("edit_state", None)
        return active_state
    if hasattr(window, "_global_state"):
        window._global_state.setdefault("edit_state", None)
        return window._global_state
    return None


def _reset_edit_state(window):
    store = _edit_state_store(window)
    if store is None:
        return
    state = store.get("edit_state")
    if not state:
        return
    for path_key in ("base_snapshot", "working_file"):
        path = state.get(path_key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    staged_dir = state.get("staged_assets_dir")
    if staged_dir and os.path.isdir(staged_dir):
        try:
            shutil.rmtree(staged_dir, ignore_errors=True)
        except OSError:
            pass
    store["edit_state"] = None


def _ensure_edit_state(window):
    current = window.current_path
    if not current:
        return None

    store = _edit_state_store(window)
    if store is None:
        return None
    state = store.get("edit_state")

    # Nếu đang edit state và file gốc khớp → tái sử dụng
    if state and state.get("original_path") == current:
        return state
    # Nếu đang edit và viewer đang hiển thị working file → tái sử dụng
    if state and state.get("working_file") == current:
        return state

    _reset_edit_state(window)

    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    session_id = uuid.uuid4().hex[:8]
    base_snapshot = os.path.join(edit_dir, f"base_{session_id}.pdf")
    working_file = os.path.join(edit_dir, f"work_{session_id}.pdf")

    shutil.copy2(current, base_snapshot)
    shutil.copy2(current, working_file)

    state = {
        "original_path": current,
        "base_snapshot": base_snapshot,
        "working_file": working_file,
        "staged_assets_dir": os.path.join(edit_dir, f"assets_{session_id}"),
        "ops": [],
        "redo_ops": [],
        "next_id": 1,
    }
    store["edit_state"] = state
    return state


def _stage_image_for_edit(state: dict, image_path: str) -> str:
    if not image_path or not os.path.exists(image_path):
        return image_path
    staged_dir = state.get("staged_assets_dir") or tempfile.gettempdir()
    os.makedirs(staged_dir, exist_ok=True)
    staged_base = os.path.join(staged_dir, uuid.uuid4().hex)

    # Normalize to PNG so both PDF engines can embed the image reliably.
    normalized_path = f"{staged_base}.png"
    qimage = QImage(image_path)
    if not qimage.isNull() and qimage.save(normalized_path, "PNG"):
        return normalized_path

    ext = os.path.splitext(image_path)[1] or ".png"
    staged_path = f"{staged_base}{ext}"
    shutil.copy2(image_path, staged_path)
    return staged_path


def _set_selected_object(window, op: dict | None):
    handler = getattr(window, "show_selected_object_in_inspector", None)
    if callable(handler):
        handler(op)


def _has_visible_text_content(text: str) -> bool:
    return bool((text or "").strip())


def _reload_viewer(window, pdf_path: str, page: int | None = None):
    """Reload PDF in the current viewer without opening a new tab."""
    if page is None:
        try:
            page = window.viewer.get_current_page()
        except Exception:
            page = 1
    page = max(1, page)

    window.current_path = pdf_path
    window.viewer.load_pdf(pdf_path, page=page, zoom="page-width")


def _render_edit_state(window, state, status_message: str):
    """Rebuild working file from base + all ops, then reload viewer in-place."""
    base_snapshot = state.get("base_snapshot")
    ops = state.get("ops") or []
    if not base_snapshot or not os.path.exists(base_snapshot):
        show_warning(window, "Không thể chỉnh sửa", "Thiếu bản gốc để dựng lại tài liệu.")
        return None

    working_file = state.get("working_file")
    if not working_file:
        show_warning(window, "Không thể chỉnh sửa", "Thiếu file làm việc.")
        return None

    # Lưu trang hiện tại để giữ vị trí sau khi reload
    current_page = None
    try:
        current_page = window.viewer.get_current_page()
    except Exception:
        pass

    try:
        get_pdf_engine().rebuild_pdf_with_ops(base_snapshot, working_file, ops)
    except Exception as e:
        show_warning(window, "Không lưu được tệp", str(e))
        return None

    _reload_viewer(window, working_file, page=current_page)

    op_count = len(ops)
    undo_hint = f" (Ctrl+Z để hoàn tác, {op_count} thao tác)" if op_count > 0 else ""
    window.status.showMessage(f"{status_message}{undo_hint}", 4000)
    return working_file


def _finalize_saved_document(window, target_path: str):
    current_page = 1
    try:
        current_page = window.viewer.get_current_page()
    except Exception:
        pass

    state = window._active_state() if hasattr(window, "_active_state") else None
    if state is not None:
        state["source_path"] = target_path
        state["display_path"] = target_path
        state["temp_path"] = None

    _reset_edit_state(window)
    window.current_path = target_path
    window.viewer.load_pdf(target_path, page=max(1, current_page), zoom="page-width", pagemode="thumbs")
    window.status.showMessage(f"Đã lưu: {os.path.basename(target_path)}", 4000)


def _save_copy(window, source_path: str, suggested_name: str):
    target_path = _pick_save_pdf_path(window, suggested_name)
    if not target_path:
        return None
    shutil.copy2(source_path, target_path)
    return target_path


@require_document(show_message=True)
def save_document(window):
    store = _edit_state_store(window)
    state = store.get("edit_state") if store else None
    if state and os.path.exists(state.get("working_file", "")):
        target_path = window.get_display_path() if hasattr(window, "get_display_path") else window.current_path
        if not target_path:
            show_warning(window, "Không thể lưu", "Không xác định được đường dẫn tệp đích.")
            return
        shutil.copy2(state["working_file"], target_path)
        _finalize_saved_document(window, target_path)
        return

    show_info(window, "Không có thay đổi", "Tài liệu hiện tại chưa có thay đổi để lưu.")


@require_document(show_message=True)
def save_document_as(window):
    store = _edit_state_store(window)
    state = store.get("edit_state") if store else None
    display_path = window.get_display_path() if hasattr(window, "get_display_path") else window.current_path
    suggested_name = os.path.basename(display_path or "tai_lieu.pdf")

    if state and os.path.exists(state.get("working_file", "")):
        target_path = _save_copy(window, state["working_file"], suggested_name)
        if not target_path:
            return
        _finalize_saved_document(window, target_path)
        return

    target_path = _save_copy(window, window.current_path, suggested_name)
    if not target_path:
        return
    window.status.showMessage(f"Đã lưu thành: {os.path.basename(target_path)}", 4000)


@require_document(show_message=True)
def undo_last_edit(window):
    """Hoàn tác thao tác chèn cuối cùng."""
    store = _edit_state_store(window)
    state = store.get("edit_state") if store else None
    if not state or not state.get("ops"):
        show_warning(window, "Không có gì để hoàn tác", "Chưa có thao tác chèn nào để hoàn tác.")
        return

    removed = state["ops"].pop()
    state.setdefault("redo_ops", []).append(removed)
    op_type = "văn bản" if removed.get("type") == "text" else "ảnh"

    if not state["ops"]:
        # Không còn ops → quay về bản gốc
        original = state.get("original_path")
        base = state.get("base_snapshot")
        working = state.get("working_file")

        # Copy lại base về working để viewer hiển thị bản gốc
        if base and os.path.exists(base) and working:
            shutil.copy2(base, working)
            _reload_viewer(window, working)
        elif original and os.path.exists(original):
            _reload_viewer(window, original)

        window.status.showMessage(f"Đã hoàn tác chèn {op_type} — về trạng thái ban đầu", 3000)
    else:
        _render_edit_state(window, state, f"Đã hoàn tác chèn {op_type}")


@require_document(show_message=True)
def redo_last_edit(window):
    store = _edit_state_store(window)
    state = store.get("edit_state") if store else None
    redo_ops = state.get("redo_ops") if state else None
    if not state or not redo_ops:
        show_warning(window, "Không có gì để làm lại", "Chưa có thao tác nào để làm lại.")
        return

    restored = redo_ops.pop()
    state["ops"].append(restored)
    op_type = "văn bản" if restored.get("type") == "text" else "ảnh"
    _render_edit_state(window, state, f"Đã làm lại chèn {op_type}")



def _find_op_at_pick(state, pick):
    page_number = int(pick.get("page_number", 0))
    left, bottom, right, top = pick.get("box", (0, 0, 0, 0))
    cx = (left + right) / 2.0
    cy = (bottom + top) / 2.0

    candidates = [op for op in state.get("ops", []) if op.get("page_number") == page_number]
    if not candidates:
        return None

    # Prefer last inserted op containing click center.
    for op in reversed(candidates):
        l, b, r, t = op.get("box", (0, 0, 0, 0))
        if l <= cx <= r and b <= cy <= t:
            return op

    # Fallback: nearest center.
    def dist2(op):
        l, b, r, t = op.get("box", (0, 0, 0, 0))
        ox = (l + r) / 2.0
        oy = (b + t) / 2.0
        return (ox - cx) ** 2 + (oy - cy) ** 2

    return min(candidates, key=dist2)


def _pick_save_pdf_path(window, default_name: str) -> str | None:
    path, _ = QFileDialog.getSaveFileName(
        window,
        "Lưu tệp PDF",
        default_name,
        "PDF Files (*.pdf)",
    )
    if not path:
        return None
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    return path


class _ObjectPlacementDialog(QDialog):
    """Simple confirm dialog for object placement preview (image, text)."""

    def __init__(self, parent=None, *, title: str = "Chèn đối tượng", note: str = "", initial_rotation: int = 0):
        from packages.qt_compat.QtCore import Qt

        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(320)

        root = QVBoxLayout(self)

        if note:
            label = QLabel(note)
            label.setWordWrap(True)
            root.addWidget(label)

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        rotation_index = {0: 0, 90: 1, 180: 2, 270: 3}.get(int(initial_rotation or 0) % 360, 0)
        self.rotation_combo.setCurrentIndex(rotation_index)

        form = QFormLayout()
        form.addRow("Xoay", self.rotation_combo)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.adjustSize()
        self._position_near_parent(parent)

    def _position_near_parent(self, parent):
        if parent is None:
            return
        geo = parent.frameGeometry()
        x = geo.right() - self.width() - 16
        y = geo.top() + 72
        self.move(max(0, x), max(0, y))

    def rotation_value(self) -> int:
        return [0, 90, 180, 270][self.rotation_combo.currentIndex()]


class _TextPlacementDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_text: str = "",
        initial_font_size: int = 12,
        initial_rotation: int = 0,
        initial_bold: bool = False,
        initial_underline: bool = False,
    ):
        from packages.qt_compat.QtCore import Qt

        super().__init__(parent)
        self.setWindowTitle("Đặt text")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)

        note = QLabel("Gõ nội dung, kéo khung trên PDF để đặt vị trí/kích thước, rồi bấm OK để chèn.")
        note.setWordWrap(True)
        root.addWidget(note)

        form = QFormLayout()

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Nhập nội dung cần chèn")
        self.text_edit.setMinimumHeight(110)
        self.text_edit.setPlainText(initial_text)
        form.addRow("Nội dung", self.text_edit)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 96)
        self.font_size_spin.setValue(max(6, min(96, int(initial_font_size or 12))))
        self.font_size_spin.setSuffix(" pt")
        form.addRow("Cỡ chữ", self.font_size_spin)

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        self.rotation_combo.setCurrentIndex({0: 0, 90: 1, 180: 2, 270: 3}.get(int(initial_rotation or 0) % 360, 0))
        form.addRow("Xoay", self.rotation_combo)

        self.bold_check = QCheckBox("In đậm")
        self.bold_check.setChecked(bool(initial_bold))
        self.underline_check = QCheckBox("Gạch chân")
        self.underline_check.setChecked(bool(initial_underline))
        form.addRow("Kiểu chữ", self.bold_check)
        form.addRow("", self.underline_check)

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.adjustSize()
        self._position_near_parent(parent)

    def _position_near_parent(self, parent):
        if parent is None:
            return
        geo = parent.frameGeometry()
        x = geo.right() - self.width() - 16
        y = geo.top() + 72
        self.move(max(0, x), max(0, y))

    def text_value(self) -> str:
        return self.text_edit.toPlainText()

    def font_size_value(self) -> int:
        return int(self.font_size_spin.value())

    def rotation_value(self) -> int:
        return [0, 90, 180, 270][self.rotation_combo.currentIndex()]

    def bold_value(self) -> bool:
        return self.bold_check.isChecked()

    def underline_value(self) -> bool:
        return self.underline_check.isChecked()


def _confirm_preview_placement(window, placement: dict, *, title: str, note: str, label: str, dialog: QDialog):
    from app.actions.sign import (
        SignaturePreviewAdjustBridge,
        _get_web_view,
        _set_object_preview,
        _setup_webchannel,
        _teardown_webchannel,
    )

    web_view = _get_web_view(window)
    if web_view is None:
        show_warning(window, "Chưa sẵn sàng", "Trình xem PDF chưa sẵn sàng.")
        return None

    preview_bridge = SignaturePreviewAdjustBridge(dialog)
    _setup_webchannel(web_view, dialog, "sigPreviewBridge", preview_bridge)

    current_placement = dict(placement)

    def _apply_adjustment(page_number, left, bottom, right, top):
        nonlocal current_placement
        current_placement = {
            "page_number": max(1, int(page_number)),
            "box": (left, bottom, right, top),
        }
        _set_object_preview(window, current_placement, label=label)

    preview_bridge.adjusted.connect(_apply_adjustment)
    _set_object_preview(window, current_placement, label=label)

    try:
        loop = QEventLoop(dialog)
        dialog.finished.connect(lambda _code: loop.quit() if loop.isRunning() else None)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        loop.exec()
        if dialog.result() != QDialog.DialogCode.Accepted:
            return None
        return current_placement
    finally:
        _set_object_preview(window, None)
        _teardown_webchannel(web_view)


def create_new_pdf(window):
    output_path = _pick_save_pdf_path(window, "tai_lieu_moi.pdf")
    if not output_path:
        return

    get_pdf_engine().create_blank_pdf(output_path, A4_WIDTH_PT, A4_HEIGHT_PT)

    open_file(window, output_path)
    window.status.showMessage("Đã tạo PDF mới", 3000)



