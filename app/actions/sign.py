import asyncio
import json
import os
import traceback
from datetime import datetime
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from PyQt6.QtCore import QObject, QEventLoop, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel

from core.pkcs11 import (
    detect_pkcs11_lib,
    get_last_pkcs11_error,
    get_token_signer_info,
    sign_pdf,
)
from app.actions._guard import require_document
from app.dialogs import show_warning, show_info


def _get_web_view(window):
    """Shared: safely retrieve QWebEngineView from window."""
    getter = getattr(window, "_get_webview", None)
    return getter() if callable(getter) else None


def _setup_webchannel(web_view, parent, name, bridge):
    """Shared: register a bridge object on a new QWebChannel."""
    channel = QWebChannel(parent)
    channel.registerObject(name, bridge)
    web_view.page().setWebChannel(channel)
    return channel


def _teardown_webchannel(web_view):
    """Shared: detach QWebChannel from the web view."""
    if web_view is not None:
        web_view.page().setWebChannel(None)


MM_TO_PT = 72.0 / 25.4
DEFAULT_SIGNATURE_WIDTH_PT = 600.0
DEFAULT_SIGNATURE_HEIGHT_PT = 120.0


class SignaturePickBridge(QObject):
    picked = pyqtSignal(int, float, float, float, float)
    cancelled = pyqtSignal()

    @pyqtSlot(int, float, float, float, float)
    def reportPick(self, page_number, pdf_x, pdf_y, page_width, page_height):
        self.picked.emit(page_number, pdf_x, pdf_y, page_width, page_height)

    @pyqtSlot()
    def cancelPick(self):
        self.cancelled.emit()


class SignaturePreviewAdjustBridge(QObject):
    adjusted = pyqtSignal(int, float, float, float, float)

    @pyqtSlot(int, float, float, float, float)
    def reportAdjusted(self, page_number, left, bottom, right, top):
        self.adjusted.emit(page_number, left, bottom, right, top)


SIGNATURE_PICK_SCRIPT = r"""
(function () {
    if (window.__readerPdfSignaturePickInstalled) {
        return;
    }
    window.__readerPdfSignaturePickInstalled = true;

    function attachBridge() {
        if (typeof QWebChannel === 'undefined') {
            var script = document.createElement('script');
            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
            script.onload = attachBridge;
            document.head.appendChild(script);
            return;
        }

        new QWebChannel(qt.webChannelTransport, function (channel) {
            const bridge = channel.objects.sigPickBridge;
            if (!bridge) {
                return;
            }

            const cancel = function () {
                try {
                    bridge.cancelPick();
                } catch (err) {}
            };

            const handler = function (event) {
                const page = event.target.closest('.page');
                if (!page || !page.dataset || !page.dataset.pageNumber) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const pageNumber = parseInt(page.dataset.pageNumber, 10);
                const pdfViewer = window.PDFViewerApplication && PDFViewerApplication.pdfViewer;
                if (!pdfViewer) {
                    return;
                }

                const pageView = pdfViewer.getPageView ? pdfViewer.getPageView(pageNumber - 1) : (pdfViewer._pages && pdfViewer._pages[pageNumber - 1]);
                if (!pageView || !pageView.viewport || !pageView.pdfPage) {
                    return;
                }

                const rect = page.getBoundingClientRect();
                const localX = event.clientX - rect.left;
                const localY = event.clientY - rect.top;
                const pdfPoint = pageView.viewport.convertToPdfPoint(localX, localY);
                const baseViewport = pageView.pdfPage.getViewport({ scale: 1 });

                document.removeEventListener('click', handler, true);
                window.removeEventListener('keydown', keyHandler, true);

                bridge.reportPick(
                    pageNumber,
                    pdfPoint[0],
                    pdfPoint[1],
                    baseViewport.width,
                    baseViewport.height
                );
            };

            const keyHandler = function (event) {
                if (event.key === 'Escape') {
                    document.removeEventListener('click', handler, true);
                    window.removeEventListener('keydown', keyHandler, true);
                    cancel();
                }
            };

            document.addEventListener('click', handler, true);
            window.addEventListener('keydown', keyHandler, true);
        });
    }

    attachBridge();
})();
"""


def _set_signature_preview(window, placement: dict | None):
    web_view = _get_web_view(window)
    if web_view is None:
        return

    payload = placement or {"clear": True}
    payload_json = json.dumps(payload)
    script = f"""
(function(payload) {{
    if (!window.PDFViewerApplication || !PDFViewerApplication.pdfViewer) {{
        return;
    }}

    const viewer = PDFViewerApplication.pdfViewer;
    if (!window.__readerPdfSignaturePreviewState) {{
        window.__readerPdfSignaturePreviewState = {{
            overlay: null,
            handle: null,
            pageView: null,
            pageNumber: null,
            dragging: false,
            dragMode: null,
            startX: 0,
            startY: 0,
            origLeft: 0,
            origTop: 0,
            origWidth: 0,
            origHeight: 0
        }};
    }}
    const state = window.__readerPdfSignaturePreviewState;

    function ensureBridge() {{
        if (window.__readerPdfSigPreviewBridge) {{
            return;
        }}
        if (typeof QWebChannel === 'undefined') {{
            const scriptTag = document.createElement('script');
            scriptTag.src = 'qrc:///qtwebchannel/qwebchannel.js';
            scriptTag.onload = ensureBridge;
            document.head.appendChild(scriptTag);
            return;
        }}
        if (!(window.qt && qt.webChannelTransport)) {{
            return;
        }}
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            window.__readerPdfSigPreviewBridge = channel.objects.sigPreviewBridge || null;
        }});
    }}

    ensureBridge();

    function clearPreview() {{
        if (state.overlay && state.overlay.parentNode) {{
            state.overlay.parentNode.removeChild(state.overlay);
        }}
        if (state.pageView && state.pageView.div) {{
            state.pageView.div.style.cursor = '';
        }}
        state.overlay = null;
        state.handle = null;
        state.pageView = null;
        state.pageNumber = null;
        state.dragging = false;
        state.dragMode = null;
    }}

    function clampRect(left, top, width, height, pageDiv) {{
        const minSize = 20;
        width = Math.max(minSize, width);
        height = Math.max(minSize, height);
        left = Math.max(0, Math.min(left, Math.max(0, pageDiv.clientWidth - width)));
        top = Math.max(0, Math.min(top, Math.max(0, pageDiv.clientHeight - height)));
        return {{ left, top, width, height }};
    }}

    function applyRect(left, top, width, height) {{
        if (!state.overlay || !state.pageView) {{
            return;
        }}
        const rect = clampRect(left, top, width, height, state.pageView.div);
        state.overlay.style.left = `${{rect.left}}px`;
        state.overlay.style.top = `${{rect.top}}px`;
        state.overlay.style.width = `${{Math.max(1, rect.width)}}px`;
        state.overlay.style.height = `${{Math.max(1, rect.height)}}px`;
    }}

    function reportAdjustedBox() {{
        if (!state.overlay || !state.pageView) {{
            return;
        }}
        const left = parseFloat(state.overlay.style.left) || 0;
        const top = parseFloat(state.overlay.style.top) || 0;
        const width = parseFloat(state.overlay.style.width) || 1;
        const height = parseFloat(state.overlay.style.height) || 1;
        const right = left + width;
        const bottomV = top + height;

        const p1 = state.pageView.viewport.convertToPdfPoint(left, top);
        const p2 = state.pageView.viewport.convertToPdfPoint(right, bottomV);

        const pdfLeft = Math.min(p1[0], p2[0]);
        const pdfRight = Math.max(p1[0], p2[0]);
        const pdfBottom = Math.min(p1[1], p2[1]);
        const pdfTop = Math.max(p1[1], p2[1]);

        const bridge = window.__readerPdfSigPreviewBridge;
        if (bridge && bridge.reportAdjusted) {{
            try {{
                bridge.reportAdjusted(state.pageNumber, pdfLeft, pdfBottom, pdfRight, pdfTop);
            }} catch (_err) {{}}
        }}
    }}

    function startDrag(event, mode) {{
        if (!state.overlay) {{
            return;
        }}
        event.preventDefault();
        event.stopPropagation();

        state.dragging = true;
        state.dragMode = mode;
        state.startX = event.clientX;
        state.startY = event.clientY;
        state.origLeft = parseFloat(state.overlay.style.left) || 0;
        state.origTop = parseFloat(state.overlay.style.top) || 0;
        state.origWidth = parseFloat(state.overlay.style.width) || 1;
        state.origHeight = parseFloat(state.overlay.style.height) || 1;

        const onMove = function(ev) {{
            if (!state.dragging || !state.pageView) {{
                return;
            }}
            const dx = ev.clientX - state.startX;
            const dy = ev.clientY - state.startY;

            if (state.dragMode === 'move') {{
                applyRect(state.origLeft + dx, state.origTop + dy, state.origWidth, state.origHeight);
            }} else if (state.dragMode === 'resize') {{
                applyRect(state.origLeft, state.origTop, state.origWidth + dx, state.origHeight + dy);
            }}
        }};

        const onUp = function() {{
            if (!state.dragging) {{
                return;
            }}
            state.dragging = false;
            state.dragMode = null;
            document.removeEventListener('mousemove', onMove, true);
            document.removeEventListener('mouseup', onUp, true);
            reportAdjustedBox();
        }};

        document.addEventListener('mousemove', onMove, true);
        document.addEventListener('mouseup', onUp, true);
    }}

    if (!payload || payload.clear) {{
        clearPreview();
        return;
    }}

    const pageNumber = payload.page_number;
    const box = payload.box;
    if (!pageNumber || !box || box.length !== 4) {{
        clearPreview();
        return;
    }}

    const pageView = viewer.getPageView
        ? viewer.getPageView(pageNumber - 1)
        : (viewer._pages && viewer._pages[pageNumber - 1]);
    if (!pageView || !pageView.viewport || !pageView.div) {{
        clearPreview();
        return;
    }}

    const rect = pageView.viewport.convertToViewportRectangle([box[0], box[1], box[2], box[3]]);
    const left = Math.min(rect[0], rect[2]);
    const top = Math.min(rect[1], rect[3]);
    const width = Math.abs(rect[2] - rect[0]);
    const height = Math.abs(rect[3] - rect[1]);

    let overlay = state.overlay;
    if (!overlay) {{
        overlay = document.createElement('div');
        overlay.style.position = 'absolute';
        overlay.style.pointerEvents = 'auto';
        overlay.style.zIndex = '40';
        overlay.style.border = '2px dashed #0B84F3';
        overlay.style.background = 'rgba(11, 132, 243, 0.15)';
        overlay.style.boxSizing = 'border-box';
        overlay.style.cursor = 'move';

        const badge = document.createElement('div');
        badge.textContent = 'Preview chữ ký';
        badge.style.position = 'absolute';
        badge.style.left = '0';
        badge.style.top = '-20px';
        badge.style.padding = '1px 6px';
        badge.style.fontSize = '11px';
        badge.style.color = '#ffffff';
        badge.style.background = '#0B84F3';
        badge.style.borderRadius = '10px';
        badge.style.pointerEvents = 'none';
        overlay.appendChild(badge);

        const handle = document.createElement('div');
        handle.style.position = 'absolute';
        handle.style.width = '12px';
        handle.style.height = '12px';
        handle.style.right = '-7px';
        handle.style.bottom = '-7px';
        handle.style.background = '#0B84F3';
        handle.style.border = '1px solid #ffffff';
        handle.style.borderRadius = '3px';
        handle.style.cursor = 'nwse-resize';
        overlay.appendChild(handle);

        state.overlay = overlay;
        state.handle = handle;

        overlay.addEventListener('mousedown', function(ev) {{
            if (ev.target === state.handle) {{
                return;
            }}
            startDrag(ev, 'move');
        }}, true);

        handle.addEventListener('mousedown', function(ev) {{
            startDrag(ev, 'resize');
        }}, true);
    }}

    if (overlay.parentNode !== pageView.div) {{
        if (overlay.parentNode) {{
            overlay.parentNode.removeChild(overlay);
        }}
        pageView.div.appendChild(overlay);
    }}

    state.pageView = pageView;
    state.pageNumber = pageNumber;

    if (!state.dragging) {{
        applyRect(left, top, width, height);
    }}
}})({payload_json});
"""
    web_view.page().runJavaScript(script)
def _set_object_preview(window, placement: dict | None, *, label: str = "Preview"):
    """
    Wrapper của _set_signature_preview dùng cho chèn ảnh/văn bản.
    Hiển thị khung kéo thả trên PDF với label tùy chỉnh.
    """
    web_view = _get_web_view(window)
    if web_view is None:
        return

    if not placement:
        _set_signature_preview(window, None)
        return

    _set_signature_preview(window, placement)

    if label and label != "Preview chữ ký":
        script = f"""
(function() {{
    const state = window.__readerPdfSignaturePreviewState;
    if (!state || !state.overlay) return;
    const badge = state.overlay.querySelector('div');
    if (badge) badge.textContent = {repr(label)};
}})();
"""
        web_view.page().runJavaScript(script)

class SignaturePlacementDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        page_count: int = 1,
        current_page: int = 1,
        initial_placement: dict | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Chọn vị trí ký")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(320)

        root = QVBoxLayout(self)

        note = QLabel(
            "Chọn vị trí/kích thước nhanh hoặc kéo trực tiếp khung preview trên PDF."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        form = QFormLayout()

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(max(1, page_count))
        self.page_spin.setValue(min(max(1, current_page), max(1, page_count)))
        form.addRow("Trang ký", self.page_spin)

        self.x_spin = self._make_mm_spin(20.0)
        self.y_spin = self._make_mm_spin(20.0)
        self.width_spin = self._make_mm_spin(150.0)
        self.height_spin = self._make_mm_spin(35.0)

        self.size_preset = QComboBox()
        self.size_preset.addItem("Nhỏ (120 x 30 mm)")
        self.size_preset.addItem("Vừa (150 x 35 mm)")
        self.size_preset.addItem("Lớn (180 x 45 mm)")
        self.size_preset.currentIndexChanged.connect(self._apply_size_preset)
        self.size_preset.setCurrentIndex(1)
        form.addRow("Kích thước nhanh", self.size_preset)

        drag_hint = QLabel("Kéo trực tiếp khung preview trên PDF để di chuyển và đổi kích thước.")
        drag_hint.setWordWrap(True)
        form.addRow(drag_hint)

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if initial_placement:
            self._load_initial_placement(initial_placement)
        else:
            self._set_default_position()

        self.adjustSize()
        self._position_for_preview(parent)

    def _make_mm_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(1)
        spin.setRange(0.0, 9999.0)
        spin.setSingleStep(5.0)
        spin.setSuffix(" mm")
        spin.setValue(value)
        return spin

    def _set_default_position(self):
        self.x_spin.setValue(10.0)
        self.y_spin.setValue(20.0)

    def _apply_size_preset(self, index: int):
        size_map = {
            0: (120.0, 30.0),
            1: (150.0, 35.0),
            2: (180.0, 45.0),
        }
        width_mm, height_mm = size_map.get(index, (150.0, 35.0))
        self.width_spin.setValue(width_mm)
        self.height_spin.setValue(height_mm)

    def _position_for_preview(self, parent):
        if parent is None:
            return

        geo = parent.frameGeometry()
        x = geo.right() - self.width() - 16
        y = geo.top() + 72
        self.move(max(0, x), max(0, y))

    def _load_initial_placement(self, placement: dict):
        page_number = int(placement.get("page_number", self.page_spin.value()))
        box = placement.get("box")
        if not box or len(box) != 4:
            self._set_default_position()
            return

        left, bottom, right, top = box
        width = max(1.0, right - left)
        height = max(1.0, top - bottom)

        self.page_spin.setValue(min(max(1, page_number), self.page_spin.maximum()))
        self.x_spin.setValue(left / MM_TO_PT)
        self.y_spin.setValue(bottom / MM_TO_PT)
        self.width_spin.setValue(width / MM_TO_PT)
        self.height_spin.setValue(height / MM_TO_PT)

    def placement(self):
        x = self.x_spin.value() * MM_TO_PT
        y = self.y_spin.value() * MM_TO_PT
        width = self.width_spin.value() * MM_TO_PT
        height = self.height_spin.value() * MM_TO_PT
        return {
            "page_number": self.page_spin.value(),
            "box": (x, y, x + width, y + height),
        }


class SignaturePickPrompt(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn vị trí ký")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)

        root = QVBoxLayout(self)

        title = QLabel("Nhấp trực tiếp vào vị trí muốn đặt chữ ký trên PDF.")
        title.setWordWrap(True)
        root.addWidget(title)

        note = QLabel(
            "Chữ ký sẽ được đặt quanh điểm bạn bấm. Nhấn Esc hoặc Đóng để hủy."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        cancel_button = QPushButton("Đóng")
        cancel_button.clicked.connect(self.reject)
        root.addWidget(cancel_button)


class SignatureIdentityDialog(QDialog):
    def __init__(self, parent=None, *, default_signer_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Thong tin chu ky")
        self.setModal(True)

        root = QVBoxLayout(self)

        form = QFormLayout()
        self.signer_name_input = QLineEdit()
        self.signer_name_input.setPlaceholderText("Nhap ten nguoi ky")
        if default_signer_name:
            self.signer_name_input.setText(default_signer_name)
        self.signer_name_input.textChanged.connect(self._update_preview)
        form.addRow("Nguoi ky", self.signer_name_input)
        root.addLayout(form)

        preview_title = QLabel("Xem truoc")
        root.addWidget(preview_title)

        self.preview = QLabel()
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview.setStyleSheet(
            "background:#f7f7f7; border:1px solid #b6b6b6; border-radius:6px;"
            "padding:10px; font-family:'Consolas';"
        )
        self.preview.setMinimumHeight(88)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._update_preview()

    def _update_preview(self):
        signer_name = self.signer_name_input.text().strip() or "Khong ro"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.preview.setText(
            "DA KY SO\n"
            f"Nguoi ky: {signer_name}\n"
            f"Timestamp: {ts}"
        )

    def signer_name(self) -> str:
        return self.signer_name_input.text().strip() or "Khong ro"


def _clamp_box(page_width: float, page_height: float, center_x: float, center_y: float):
    box_width = min(DEFAULT_SIGNATURE_WIDTH_PT, max(200.0, page_width * 0.55))
    box_height = min(DEFAULT_SIGNATURE_HEIGHT_PT, max(70.0, page_height * 0.25))
    left = center_x - (box_width / 2.0)
    bottom = center_y - (box_height / 2.0)

    left = max(0.0, min(left, max(0.0, page_width - box_width)))
    bottom = max(0.0, min(bottom, max(0.0, page_height - box_height)))

    return (left, bottom, left + box_width, bottom + box_height)


def _pick_signature_placement(window):
    web_view = _get_web_view(window)
    if web_view is None:
        return None

    prompt = SignaturePickPrompt(window)
    bridge = SignaturePickBridge(prompt)
    channel = _setup_webchannel(web_view, prompt, "sigPickBridge", bridge)
    prompt._sig_pick_bridge = bridge
    prompt._sig_pick_channel = channel

    loop = QEventLoop(prompt)
    result = {}

    def _finish_pick(page_number, pdf_x, pdf_y, page_width, page_height):
        picked_box = _clamp_box(page_width, page_height, pdf_x, pdf_y)
        result.update(
            {
                "page_number": page_number,
                "box": picked_box,
                "page_width": page_width,
                "page_height": page_height,
            }
        )
        prompt.close()
        if loop.isRunning():
            loop.quit()

    def _cancel_pick():
        result.clear()
        prompt.close()
        if loop.isRunning():
            loop.quit()

    bridge.picked.connect(_finish_pick)
    bridge.cancelled.connect(_cancel_pick)
    prompt.finished.connect(lambda _code: loop.quit() if loop.isRunning() else None)
    prompt.show()
    prompt.raise_()
    prompt.activateWindow()

    try:
        web_view.page().runJavaScript(SIGNATURE_PICK_SCRIPT)
        loop.exec()
    finally:
        _teardown_webchannel(web_view)
        prompt.deleteLater()

    if not result:
        return None
    return result


def check_token(window):
    lib = detect_pkcs11_lib()
    if lib:
        signer_info = get_token_signer_info()
        signer_name = signer_info.get("name") if signer_info else ""
        signer_line = f"\nNgười ký: {signer_name}" if signer_name else ""
        show_info(
            window,
            "Thiết bị ký số",
            f"Đã tìm thấy USB ký số.\n\nTrình điều khiển: {os.path.basename(lib)}{signer_line}",
        )
    else:
        details = get_last_pkcs11_error()
        detail_line = f"\n\nChi tiết: {details}" if details else ""
        show_warning(
            window,
            "Không tìm thấy thiết bị ký số",
            "Chưa cắm USB ký số hoặc trình điều khiển chưa được cài đặt."
            + detail_line,
        )


@require_document(show_message=True)
def sign_document(window):

    placement = _pick_signature_placement(window)

    page_count = 1
    current_page = 1
    if window.viewer:
        try:
            page_count = max(1, window.viewer.get_page_count())
            current_page = max(1, window.viewer.get_current_page())
        except Exception:
            page_count = 1
            current_page = 1

    placement_dialog = SignaturePlacementDialog(
        window,
        page_count=page_count,
        current_page=placement["page_number"] if placement else current_page,
        initial_placement=placement,
    )

    web_view = _get_web_view(window)
    preview_channel = None
    preview_bridge = None
    if web_view is not None:
        preview_bridge = SignaturePreviewAdjustBridge(placement_dialog)
        preview_channel = _setup_webchannel(web_view, placement_dialog, "sigPreviewBridge", preview_bridge)
        placement_dialog._sig_preview_bridge = preview_bridge
        placement_dialog._sig_preview_channel = preview_channel

        def _apply_preview_adjustment(page_number, left, bottom, right, top):
            width = max(1.0, right - left)
            height = max(1.0, top - bottom)
            page_number = max(1, int(page_number))

            for spin in (
                placement_dialog.page_spin,
                placement_dialog.x_spin,
                placement_dialog.y_spin,
                placement_dialog.width_spin,
                placement_dialog.height_spin,
            ):
                spin.blockSignals(True)

            try:
                placement_dialog.page_spin.setValue(
                    min(page_number, placement_dialog.page_spin.maximum())
                )
                placement_dialog.x_spin.setValue(left / MM_TO_PT)
                placement_dialog.y_spin.setValue(bottom / MM_TO_PT)
                placement_dialog.width_spin.setValue(width / MM_TO_PT)
                placement_dialog.height_spin.setValue(height / MM_TO_PT)
            finally:
                for spin in (
                    placement_dialog.page_spin,
                    placement_dialog.x_spin,
                    placement_dialog.y_spin,
                    placement_dialog.width_spin,
                    placement_dialog.height_spin,
                ):
                    spin.blockSignals(False)

            _refresh_preview()

        preview_bridge.adjusted.connect(_apply_preview_adjustment)

    def _refresh_preview(*_args):
        _set_signature_preview(window, placement_dialog.placement())

    placement_dialog.page_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.x_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.y_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.width_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.height_spin.valueChanged.connect(_refresh_preview)

    _refresh_preview()
    try:
        loop = QEventLoop(placement_dialog)
        placement_dialog.finished.connect(
            lambda _code: loop.quit() if loop.isRunning() else None
        )
        placement_dialog.show()
        placement_dialog.raise_()
        placement_dialog.activateWindow()
        loop.exec()

        if placement_dialog.result() != QDialog.DialogCode.Accepted:
            return
        placement = placement_dialog.placement()
    finally:
        _set_signature_preview(window, None)
        _teardown_webchannel(web_view)

    signer_info = get_token_signer_info()
    default_signer_name = signer_info.get("name") if signer_info else ""

    identity_dialog = SignatureIdentityDialog(
        window,
        default_signer_name=default_signer_name,
    )
    if identity_dialog.exec() != QDialog.DialogCode.Accepted:
        return
    signer_name = identity_dialog.signer_name()

    base, ext = os.path.splitext(window.current_path)
    default_output = f"{base}_signed{ext}"

    output_path, _ = QFileDialog.getSaveFileName(
        window,
        "Lưu file đã ký",
        default_output,
        "PDF Files (*.pdf)"
    )
    if not output_path:
        return

    pin, ok = QInputDialog.getText(
        window, "Nhập mã PIN", "PIN của USB ký số:",
        QLineEdit.EchoMode.Password
    )
    if not ok or not pin:
        return

    if signer_name == "Khong ro":
        signer_info_with_pin = get_token_signer_info(pin)
        if signer_info_with_pin and signer_info_with_pin.get("name"):
            signer_name = signer_info_with_pin["name"]

    try:
        asyncio.run(
            sign_pdf(
                window.current_path,
                output_path,
                pin,
                signer_name=signer_name,
                page_number=placement["page_number"],
                box=placement["box"],
            )
        )

        with open(output_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            os.remove(output_path)
            raise RuntimeError(
                "File ký xong không hợp lệ (thiếu %PDF header).\n"
                "Vui lòng thử lại."
            )

        reply = QMessageBox.question(
            window,
            "Ký số thành công",
            f"Ký số thành công!\n\nFile lưu tại:\n{output_path}\n\nMở file đã ký ngay?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            window.current_path = output_path
            window.viewer.load_pdf(output_path)

    except Exception as exc:
        exc_type_name = type(exc).__name__

        if exc_type_name == "PinIncorrect" or "PinIncorrect" in str(type(exc)):
            QMessageBox.warning(
                window,
                "Sai mã PIN",
                "Mã PIN bạn nhập không đúng.\n\n"
                "Vui lòng kiểm tra lại mã PIN và thử lại.\n"
                "⚠️ Lưu ý: Nhập sai PIN nhiều lần có thể khóa USB Token.",
            )
        elif exc_type_name == "PinLocked" or "PinLocked" in str(type(exc)):
            QMessageBox.critical(
                window,
                "USB Token đã bị khóa",
                "USB Token đã bị khóa do nhập sai PIN quá nhiều lần.\n\n"
                "Vui lòng liên hệ nhà cung cấp chữ ký số để mở khóa.",
            )
        else:
            traceback.print_exc()
            msg = QMessageBox(window)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Lỗi ký số")
            msg.setText("Ký số thất bại!")
            msg.setDetailedText(traceback.format_exc())
            msg.exec()