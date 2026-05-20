import os
import shutil
import tempfile
import uuid

from packages.qt_compat.QtCore import QObject, QEventLoop, pyqtSignal, pyqtSlot
from packages.qt_compat.QtWebChannel import QWebChannel
from packages.qt_compat.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.actions.file import open_file
from app.actions._guard import require_document
from app.dialogs import show_warning
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


def _reset_edit_state(window):
    state = getattr(window, "_pdf_edit_state", None)
    if not state:
        return
    for path_key in ("base_snapshot", "working_file"):
        path = state.get(path_key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    window._pdf_edit_state = None


def _ensure_edit_state(window):
    current = window.current_path
    if not current:
        return None

    state = getattr(window, "_pdf_edit_state", None)

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
        "ops": [],
        "next_id": 1,
    }
    window._pdf_edit_state = state
    return state


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


def _navigate_viewer(window, page_no: int):
    """Điều hướng PDF viewer đến trang chỉ định qua JavaScript."""
    try:
        from app.actions.sign import _get_web_view
        wv = _get_web_view(window)
        if wv:
            wv.page().runJavaScript(
                f"(function(){{var app=window.PDFViewerApplication;"
                f"if(app&&app.pdfViewer){{app.pdfViewer.currentPageNumber={int(page_no)};}}}})()"
            )
    except Exception:
        pass


def _render_edit_state(window, state, status_message: str, focus_page: int | None = None):
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

    current_page = focus_page
    if current_page is None:
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

    # Điều hướng đến trang đã chèn sau khi viewer load xong (delay nhỏ)
    if focus_page is not None:
        from packages.qt_compat.QtCore import QTimer
        QTimer.singleShot(800, lambda: _navigate_viewer(window, focus_page))

    op_count = len(ops)
    undo_hint = f" (Ctrl+Z để hoàn tác, {op_count} thao tác)" if op_count > 0 else ""
    window.status.showMessage(f"{status_message}{undo_hint}", 4000)
    return working_file


def _adjust_placement(window, initial_placement: dict, title: str = "Xác nhận vị trí") -> dict | None:
    """Hiển thị overlay kéo/co dãn để người dùng tinh chỉnh vị trí TRƯỚC khi rebuild.
    Returns: placement dict cuối cùng, hoặc None nếu huỷ."""
    from app.actions.sign import (
        _get_web_view, _setup_webchannel, _teardown_webchannel,
        _set_signature_preview, SignaturePreviewAdjustBridge,
    )

    web_view = _get_web_view(window)
    if web_view is None:
        return initial_placement

    placement = dict(initial_placement)

    confirm_dlg = _ObjectPlacementDialog(
        window,
        title=title,
        note=(
            "Kéo khung xanh để di chuyển\n"
            "Kéo góc phải-dưới để thay đổi kích thước\n"
            "Nhấn OK để xác nhận vị trí"
        ),
    )

    bridge = SignaturePreviewAdjustBridge(confirm_dlg)
    _setup_webchannel(web_view, confirm_dlg, "sigPreviewBridge", bridge)

    def _on_adjusted(page_no, left, bottom, right, top):
        nonlocal placement
        placement = {
            "page_number": max(1, int(page_no)),
            "box": (left, bottom, right, top),
        }
        _set_signature_preview(window, placement)

    bridge.adjusted.connect(_on_adjusted)
    _set_signature_preview(window, placement)

    try:
        loop = QEventLoop(confirm_dlg)
        confirm_dlg.finished.connect(
            lambda _code: loop.quit() if loop.isRunning() else None
        )
        confirm_dlg.show()
        confirm_dlg.raise_()
        confirm_dlg.activateWindow()
        loop.exec()

        if confirm_dlg.result() != QDialog.DialogCode.Accepted:
            return None
        return placement
    finally:
        _set_signature_preview(window, None)
        _teardown_webchannel(web_view)


@require_document(show_message=True)
def undo_last_edit(window):
    """Hoàn tác thao tác chèn cuối cùng."""
    state = getattr(window, "_pdf_edit_state", None)
    if not state or not state.get("ops"):
        show_warning(window, "Không có gì để hoàn tác", "Chưa có thao tác chèn nào để hoàn tác.")
        return

    removed = state["ops"].pop()
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

    def __init__(self, parent=None, *, title: str = "Chèn đối tượng", note: str = ""):
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


def create_new_pdf(window):
    output_path = _pick_save_pdf_path(window, "tai_lieu_moi.pdf")
    if not output_path:
        return

    get_pdf_engine().create_blank_pdf(output_path, A4_WIDTH_PT, A4_HEIGHT_PT)

    open_file(window, output_path)
    window.status.showMessage("Đã tạo PDF mới", 3000)


@require_document(show_message=True)
def insert_text_to_pdf(window):
    from app.pdf_inline_editor import run_inline_text

    result = run_inline_text(window)
    if not result:
        return

    page_number = result["page_number"]
    left, bottom, right, top = result["box"]

    # Đảm bảo vùng tối thiểu
    if abs(right - left) < 20:
        right = left + 180
    if abs(top - bottom) < 12:
        top = bottom + 44

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id":         state["next_id"],
        "type":       "text",
        "page_number": page_number,
        "box":        (left, bottom, right, top),
        "text":       result["text"],
        "font_size":  result.get("font_size", 14),
        "font_color": result.get("color_tuple", (0.0, 0.0, 0.0)),
    }
    state["next_id"] += 1
    state["ops"].append(op)

    _render_edit_state(window, state, "Đã chèn văn bản", focus_page=page_number)


@require_document(show_message=True)
def insert_image_to_pdf(window):
    from app.pdf_inline_editor import run_inline_image

    image_path, _ = QFileDialog.getOpenFileName(
        window,
        "Chọn ảnh",
        "",
        "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
    )
    if not image_path:
        return

    result = run_inline_image(window, image_path)
    if not result:
        return

    page_number = result["page_number"]
    box = result["box"]
    left, bottom, right, top = box

    # Đảm bảo vùng tối thiểu
    if abs(right - left) < 20:
        right = left + 150
    if abs(top - bottom) < 20:
        top = bottom + 120
        box = (left, bottom, right, top)

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id":          state["next_id"],
        "type":        "image",
        "page_number": page_number,
        "box":         box,
        "image_path":  image_path,
    }
    state["next_id"] += 1
    state["ops"].append(op)

    _render_edit_state(window, state, "Đã chèn ảnh", focus_page=page_number)



@require_document(show_message=True)
def save_edits(window):
    """Lưu các thay đổi (text/ảnh đã chèn) vào file gốc."""
    state = getattr(window, "_pdf_edit_state", None)
    if not state:
        # Không có edit state — lưu thông thường
        try:
            window.viewer.save_pdf()
        except Exception:
            pass
        return

    working = state.get("working_file")
    base = state.get("base_snapshot")
    original = state.get("original_path")

    if not working or not base or not os.path.exists(base):
        show_warning(window, "Không lưu được", "Không tìm thấy file làm việc.")
        return

    # Rebuild lần cuối vào working file
    try:
        get_pdf_engine().rebuild_pdf_with_ops(base, working, state.get("ops", []))
    except Exception as e:
        show_warning(window, "Lỗi khi dựng file", str(e))
        return

    # Xác định đường dẫn lưu
    save_path = original
    if not save_path or not os.path.exists(os.path.dirname(save_path) or "."):
        save_path = _pick_save_pdf_path(window, "document.pdf")
    if not save_path:
        return

    try:
        shutil.copy2(working, save_path)
    except Exception as e:
        show_warning(window, "Lỗi ghi file", str(e))
        return

    # Reset edit state, tải lại từ file đã lưu
    window._pdf_edit_state = None
    _reload_viewer(window, save_path)
    window.status.showMessage(
        f"Đã lưu: {os.path.basename(save_path)}", 5000
    )


@require_document(show_message=True)
def save_edits_as(window):
    """Lưu bản chỉnh sửa thành file mới (Save As)."""
    state = getattr(window, "_pdf_edit_state", None)
    src = state.get("working_file") if state else window.current_path
    if not src:
        return

    save_path = _pick_save_pdf_path(window, "document_copy.pdf")
    if not save_path:
        return

    if state:
        base = state.get("base_snapshot", "")
        try:
            get_pdf_engine().rebuild_pdf_with_ops(base, src, state.get("ops", []))
        except Exception as e:
            show_warning(window, "Lỗi khi dựng file", str(e))
            return

    try:
        shutil.copy2(src, save_path)
    except Exception as e:
        show_warning(window, "Lỗi ghi file", str(e))
        return

    window.status.showMessage(f"Đã lưu bản sao: {os.path.basename(save_path)}", 4000)


@require_document(show_message=True)
def delete_inserted_object(window):
    """Xóa một text/ảnh đã chèn — click vào đối tượng muốn xóa."""
    state = _ensure_edit_state(window)
    if not state or not state.get("ops"):
        show_warning(window, "Chưa có đối tượng", "Chưa có text/ảnh nào được chèn để xóa.")
        return

    if hasattr(window, "status"):
        window.status.showMessage("Click vào text/ảnh muốn xóa... (Esc để hủy)", 0)

    picked = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not picked:
        return

    target_op = _find_op_at_pick(state, picked)
    if not target_op:
        show_warning(window, "Không tìm thấy", "Không xác định được đối tượng tại vị trí đó.")
        return

    op_type = "văn bản" if target_op.get("type") == "text" else "ảnh"
    state["ops"].remove(target_op)

    if not state["ops"]:
        base = state.get("base_snapshot")
        working = state.get("working_file")
        if base and os.path.exists(base) and working:
            shutil.copy2(base, working)
            _reload_viewer(window, working)
        window.status.showMessage(f"Đã xóa {op_type} — tài liệu về trạng thái gốc", 3000)
    else:
        _render_edit_state(window, state, f"Đã xóa {op_type}")


@require_document(show_message=True)
def redact_area(window):
    """Che/tẩy vùng nội dung bằng hộp màu trắng."""
    if hasattr(window, "status"):
        window.status.showMessage("Kéo để chọn vùng cần che... (Esc để hủy)", 0)

    placement = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not placement:
        return

    page_number = int(placement["page_number"])
    left, bottom, right, top = placement["box"]

    if abs(right - left) < 4 or abs(top - bottom) < 4:
        show_warning(window, "Vùng quá nhỏ", "Hãy kéo để chọn vùng rộng hơn.")
        return

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id": state["next_id"],
        "type": "rect",
        "page_number": page_number,
        "box": (left, bottom, right, top),
        "fill_color": (1.0, 1.0, 1.0),
        "stroke_color": (1.0, 1.0, 1.0),
    }
    state["next_id"] += 1
    state["ops"].append(op)
    _render_edit_state(window, state, "Đã che vùng nội dung")


@require_document(show_message=True)
def draw_on_pdf(window):
    """Vẽ tự do lên vùng PDF đã chọn."""
    from app.signature_pad import DrawOnPdfDialog

    if hasattr(window, "status"):
        window.status.showMessage("Kéo để chọn vùng muốn vẽ trên PDF... (Esc để hủy)", 0)

    placement = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not placement:
        return

    page_number = int(placement["page_number"])
    left, bottom, right, top = placement["box"]

    # Tính kích thước canvas theo tỉ lệ vùng đã chọn
    w_pt = max(right - left, 20.0)
    h_pt = max(top - bottom, 20.0)
    aspect = w_pt / h_pt
    canvas_w = 560
    canvas_h = max(80, int(canvas_w / aspect))
    if canvas_h > 480:
        canvas_h = 480
        canvas_w = int(canvas_h * aspect)

    dlg = DrawOnPdfDialog(window, canvas_w=canvas_w, canvas_h=canvas_h)
    if dlg.exec() != dlg.DialogCode.Accepted:
        return

    pixmap = dlg.get_pixmap()
    if pixmap is None:
        return

    # Lưu ra file PNG tạm (ARGB — giữ trong suốt)
    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    img_path = os.path.join(edit_dir, f"draw_{uuid.uuid4().hex[:8]}.png")
    pixmap.save(img_path, "PNG")

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id": state["next_id"],
        "type": "image",
        "page_number": page_number,
        "box": (left, bottom, right, top),
        "image_path": img_path,
    }
    state["next_id"] += 1
    state["ops"].append(op)
    _render_edit_state(window, state, "Đã vẽ lên PDF")


@require_document(show_message=True)
def select_inserted_object(window):

    state = _ensure_edit_state(window)
    if not state or not state.get("ops"):
        show_warning(window, "Chưa có đối tượng", "Chưa có text/ảnh nào được chèn để chỉnh sửa.")
        return

    show_warning(
        window,
        "Chọn đối tượng",
        "Bước 1: Bấm vào text/ảnh muốn chỉnh.\n"
        "Bước 2: Kéo vùng mới để di chuyển/đổi kích thước.",
    )

    picked_object = _pick_pdf_area(window)
    if not picked_object:
        return

    target_op = _find_op_at_pick(state, picked_object)
    if not target_op:
        show_warning(window, "Không tìm thấy", "Không xác định được đối tượng tại vị trí đã chọn.")
        return

    new_area = _pick_pdf_area(window)
    if not new_area:
        return

    l, b, r, t = new_area["box"]
    if abs(r - l) < 6 and abs(t - b) < 6:
        w = target_op["box"][2] - target_op["box"][0]
        h = target_op["box"][3] - target_op["box"][1]
        r = l + max(20, w)
        t = b + max(20, h)

    target_op["page_number"] = int(new_area["page_number"])
    target_op["box"] = (l, b, r, t)

    _render_edit_state(window, state, "Đã cập nhật vị trí/kích thước đối tượng")
