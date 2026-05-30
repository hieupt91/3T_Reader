import asyncio
import json
import os
import traceback
from datetime import datetime
from packages.qt_compat.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QStyle,
)
from packages.qt_compat.QtCore import QObject, QEventLoop, Qt, QTimer, pyqtSignal, pyqtSlot
from packages.qt_compat.QtWebChannel import QWebChannel

from packages.signing import get_signing_provider
from packages.signing.shared import sign_pdf_with_pkcs12, validate_signed_pdf_status
from app.actions._guard import require_document
from app.dialogs import show_warning, show_info
from app.signature_templates import find_signature_template, list_signature_templates


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
    if web_view is None:
        return
    try:
        web_view.page().setWebChannel(None)
    except RuntimeError:
        pass


def _refresh_document_view(window, output_path: str, *, page_number: int = 1):
    """Update the active document paths and reopen the rendered PDF on the next tick."""
    try:
        state = window._state_or_global() if hasattr(window, "_state_or_global") else None
    except Exception:
        state = None

    if state is not None:
        state["source_path"] = output_path
        state["display_path"] = output_path

    try:
        window.current_path = output_path
    except Exception:
        pass

    def _load():
        viewer = getattr(window, "viewer", None)
        if not viewer:
            return
        try:
            viewer.load_pdf(
                output_path,
                page=max(1, int(page_number or 1)),
                zoom="page-width",
            )
        except Exception:
            traceback.print_exc()
            show_warning(window, "Lỗi mở file đã ký", "Không thể hiển thị file vừa ký.")

    QTimer.singleShot(0, _load)


def _format_signature_report(report: dict, path: str | None = None) -> str:
    lines = []
    if path:
        lines.append(f"File: {path}")
    lines.append(f"Kết luận: {report.get('overall_status') or report.get('message') or 'Không rõ'}")
    lines.append(f"Tính toàn vẹn: {'Đạt' if report.get('integrity_ok') else 'Không đạt'}")
    lines.append(f"Chuỗi tin cậy: {'Đã xác minh' if report.get('trusted') else 'Chưa xác minh'}")
    if report.get("subject_name"):
        lines.append(f"Chủ thể: {report.get('subject_name')}")
    if report.get("issuer_name"):
        lines.append(f"Nhà cung cấp: {report.get('issuer_name')}")
    if report.get("serial_hex"):
        lines.append(f"Serial: {report.get('serial_hex')}")
    if report.get("valid_from") or report.get("valid_to"):
        lines.append(
            f"Hiệu lực: {report.get('valid_from') or 'Khong ro'} - {report.get('valid_to') or 'Khong ro'}"
        )
    if report.get("certificate_status"):
        lines.append(f"Trạng thái chứng thư: {report.get('certificate_status')}")
    signing_time = report.get("signing_time")
    if signing_time:
        lines.append(f"Thời điểm ký: {signing_time}")
    signing_time_ok = report.get("signing_time_ok")
    if signing_time_ok is True:
        lines.append("Thời điểm ký nằm trong thời hạn hiệu lực.")
    elif signing_time_ok is False:
        lines.append("Thời điểm ký nằm ngoài thời hạn hiệu lực.")
    return "\n".join(lines)


def _show_signature_report(window, title: str, report: dict, *, path: str | None = None):
    msg = QMessageBox(window)
    msg.setWindowTitle(title)
    msg.setIcon(QMessageBox.Icon.Information if report.get("ok") else QMessageBox.Icon.Warning)
    msg.setText(report.get("overall_status") or report.get("message") or "Không rõ kết quả.")
    msg.setDetailedText(_format_signature_report(report, path))
    msg.exec()


MM_TO_PT = 72.0 / 25.4
DEFAULT_SIGNATURE_WIDTH_PT = 600.0
DEFAULT_SIGNATURE_HEIGHT_PT = 160.0


class SignaturePickBridge(QObject):
    picked = pyqtSignal(int, float, float, float, float)
    area_picked = pyqtSignal(int, float, float, float, float, float, float)
    cancelled = pyqtSignal()

    @pyqtSlot(int, float, float, float, float)
    def reportPick(self, page_number, pdf_x, pdf_y, page_width, page_height):
        self.picked.emit(page_number, pdf_x, pdf_y, page_width, page_height)

    @pyqtSlot(int, float, float, float, float, float, float)
    def reportArea(self, page_number, left, bottom, right, top, page_width, page_height):
        self.area_picked.emit(page_number, left, bottom, right, top, page_width, page_height)

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
    if (window.__readerPdfSignaturePickCleanup) {
        try { window.__readerPdfSignaturePickCleanup(); } catch (_err) {}
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

            let selection = null;

            function cleanupSelection() {
                document.removeEventListener('mousedown', mouseDownHandler, true);
                document.removeEventListener('mousemove', mouseMoveHandler, true);
                document.removeEventListener('mouseup', mouseUpHandler, true);
                window.removeEventListener('keydown', keyHandler, true);
                if (selection && selection.box && selection.box.parentNode) {
                    selection.box.parentNode.removeChild(selection.box);
                }
                selection = null;
                window.__readerPdfSignaturePickCleanup = null;
            }

            window.__readerPdfSignaturePickCleanup = cleanupSelection;

            const keyHandler = function (event) {
                if (event.key === 'Escape') {
                    cleanupSelection();
                    bridge.cancelPick();
                }
            };

            function makeSelectionBox(page) {
                const box = document.createElement('div');
                box.style.position = 'absolute';
                box.style.zIndex = '10000';
                box.style.pointerEvents = 'none';
                box.style.background = 'rgba(11, 132, 243, 0.3)';
                box.style.boxSizing = 'border-box';
                page.appendChild(box);
                return box;
            }

            function applySelectionBox() {
                if (!selection || !selection.box) return;
                const left = Math.min(selection.startX, selection.currentX);
                const top = Math.min(selection.startY, selection.currentY);
                const width = Math.abs(selection.currentX - selection.startX);
                const height = Math.abs(selection.currentY - selection.startY);
                selection.box.style.left = `${left}px`;
                selection.box.style.top = `${top}px`;
                selection.box.style.width = `${Math.max(1, width)}px`;
                selection.box.style.height = `${Math.max(1, height)}px`;
            }

            const mouseDownHandler = function(event) {
                const page = event.target.closest('.page');
                if (!page || !page.dataset || !page.dataset.pageNumber) {
                    return;
                }
                const pageNumber = parseInt(page.dataset.pageNumber, 10);
                const pdfViewer = window.PDFViewerApplication && PDFViewerApplication.pdfViewer;
                const pageView = pdfViewer && (pdfViewer.getPageView
                    ? pdfViewer.getPageView(pageNumber - 1)
                    : (pdfViewer._pages && pdfViewer._pages[pageNumber - 1]));
                if (!pageView || !pageView.viewport || !pageView.pdfPage) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const rect = page.getBoundingClientRect();
                const localX = Math.max(0, Math.min(event.clientX - rect.left, page.clientWidth));
                const localY = Math.max(0, Math.min(event.clientY - rect.top, page.clientHeight));
                selection = {
                    page,
                    pageNumber,
                    pageView,
                    startX: localX,
                    startY: localY,
                    currentX: localX,
                    currentY: localY,
                    box: makeSelectionBox(page),
                    dragging: true
                };
                applySelectionBox();
            };

            const mouseMoveHandler = function(event) {
                if (!selection || !selection.dragging) return;
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const rect = selection.page.getBoundingClientRect();
                selection.currentX = Math.max(0, Math.min(event.clientX - rect.left, selection.page.clientWidth));
                selection.currentY = Math.max(0, Math.min(event.clientY - rect.top, selection.page.clientHeight));
                applySelectionBox();
            };

            const mouseUpHandler = function(event) {
                if (!selection || !selection.dragging) return;
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                selection.dragging = false;
                
                const leftPx = Math.min(selection.startX, selection.currentX);
                const topPx = Math.min(selection.startY, selection.currentY);
                const rightPx = Math.max(selection.startX, selection.currentX);
                const bottomPx = Math.max(selection.startY, selection.currentY);
                
                const dx = rightPx - leftPx;
                const dy = bottomPx - topPx;
                
                const baseViewport = selection.pageView.pdfPage.getViewport({ scale: 1 });
                const pageNumber = selection.pageNumber;
                
                if (dx < 5 && dy < 5) {
                    // Treat as click
                    const pdfPoint = selection.pageView.viewport.convertToPdfPoint(selection.startX, selection.startY);
                    cleanupSelection();
                    bridge.reportPick(
                        pageNumber,
                        pdfPoint[0],
                        pdfPoint[1],
                        baseViewport.width,
                        baseViewport.height
                    );
                } else {
                    // Area drag
                    const p1 = selection.pageView.viewport.convertToPdfPoint(leftPx, topPx);
                    const p2 = selection.pageView.viewport.convertToPdfPoint(rightPx, bottomPx);
                    
                    cleanupSelection();
                    bridge.reportArea(
                        pageNumber,
                        Math.min(p1[0], p2[0]),
                        Math.min(p1[1], p2[1]),
                        Math.max(p1[0], p2[0]),
                        Math.max(p1[1], p2[1]),
                        baseViewport.width,
                        baseViewport.height
                    );
                }
            };

            document.addEventListener('mousedown', mouseDownHandler, true);
            document.addEventListener('mousemove', mouseMoveHandler, true);
            document.addEventListener('mouseup', mouseUpHandler, true);
            window.addEventListener('keydown', keyHandler, true);
        });
    }

    if (document.readyState === 'complete') {
        attachBridge();
    } else {
        window.addEventListener('load', attachBridge);
    }
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
            ev.preventDefault();
            ev.stopPropagation();
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

        const onUp = function(ev) {{
            ev.preventDefault();
            ev.stopPropagation();
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
        overlay.style.border = 'none';
        overlay.style.background = 'rgba(11, 132, 243, 0.22)';
        overlay.style.boxSizing = 'border-box';
        overlay.style.cursor = 'move';
        overlay.style.userSelect = 'none';
        overlay.style.touchAction = 'none';

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


def _set_signature_field_marks(window, placements: list[dict]) -> None:
    """Show already selected signature fields as fixed overlays while adding more fields."""
    web_view = _get_web_view(window)
    if web_view is None:
        return

    payload = json.dumps(placements or [])
    script = f"""
(function(items) {{
    if (!window.PDFViewerApplication || !PDFViewerApplication.pdfViewer) {{
        return;
    }}
    const viewer = PDFViewerApplication.pdfViewer;
    const markerClass = 'reader-pdf-sigfield-marker';

    document.querySelectorAll('.' + markerClass).forEach(function(el) {{
        el.remove();
    }});

    items.forEach(function(item, index) {{
        const pageNumber = item.page_number;
        const box = item.box;
        if (!pageNumber || !box || box.length !== 4) {{
            return;
        }}
        const pageView = viewer.getPageView
            ? viewer.getPageView(pageNumber - 1)
            : (viewer._pages && viewer._pages[pageNumber - 1]);
        if (!pageView || !pageView.viewport || !pageView.div) {{
            return;
        }}

        const rect = pageView.viewport.convertToViewportRectangle([box[0], box[1], box[2], box[3]]);
        const left = Math.min(rect[0], rect[2]);
        const top = Math.min(rect[1], rect[3]);
        const width = Math.abs(rect[2] - rect[0]);
        const height = Math.abs(rect[3] - rect[1]);

        const marker = document.createElement('div');
        marker.className = markerClass;
        marker.style.position = 'absolute';
        marker.style.left = `${{left}}px`;
        marker.style.top = `${{top}}px`;
        marker.style.width = `${{Math.max(1, width)}}px`;
        marker.style.height = `${{Math.max(1, height)}}px`;
        marker.style.zIndex = '39';
        marker.style.boxSizing = 'border-box';
        marker.style.border = '2px solid #16a34a';
        marker.style.background = 'rgba(22, 163, 74, 0.16)';
        marker.style.pointerEvents = 'none';
        marker.style.borderRadius = '2px';

        const badge = document.createElement('div');
        badge.textContent = item.display_name || item.field_name || `Ô ký ${{index + 1}}`;
        badge.style.position = 'absolute';
        badge.style.left = '0';
        badge.style.top = '-20px';
        badge.style.maxWidth = '220px';
        badge.style.overflow = 'hidden';
        badge.style.textOverflow = 'ellipsis';
        badge.style.whiteSpace = 'nowrap';
        badge.style.padding = '1px 6px';
        badge.style.fontSize = '11px';
        badge.style.fontWeight = '700';
        badge.style.color = '#ffffff';
        badge.style.background = '#16a34a';
        badge.style.borderRadius = '10px';
        marker.appendChild(badge);

        pageView.div.appendChild(marker);
    }});
}})({payload});
"""
    web_view.page().runJavaScript(script)


def _clear_signature_field_marks(window) -> None:
    web_view = _get_web_view(window)
    if web_view is None:
        return
    web_view.page().runJavaScript(
        "document.querySelectorAll('.reader-pdf-sigfield-marker').forEach(function(el){el.remove();});"
    )


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
        self.height_spin = self._make_mm_spin(50.0)

        self.size_preset = QComboBox()
        self.size_preset.addItem("Nhỏ (130 x 45 mm)")
        self.size_preset.addItem("Vừa (150 x 50 mm)")
        self.size_preset.addItem("Lớn (180 x 60 mm)")
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
            0: (130.0, 45.0),
            1: (150.0, 50.0),
            2: (180.0, 60.0),
        }
        width_mm, height_mm = size_map.get(index, (150.0, 50.0))
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

        title = QLabel("Giữ chuột và kéo trực tiếp trên PDF để vẽ vùng chữ ký.")
        title.setWordWrap(True)
        root.addWidget(title)

        note = QLabel(
            "Khung xanh sẽ chạy theo chuột. Có thể bấm một điểm để dùng kích thước mặc định. Nhấn Esc hoặc Đóng để hủy."
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


def _token_text(token, attr: str) -> str:
    value = getattr(token, attr, "")
    return str(value or "").strip()


def _token_display_name(token) -> str:
    parts = [
        _token_text(token, "signer_name"),
        _token_text(token, "token_label"),
        _token_text(token, "serial"),
        _token_text(token, "driver"),
    ]
    return next((part for part in parts if part), "USB token")


def _token_detail_lines(token) -> list[str]:
    rows = [
        ("Người ký", _token_text(token, "signer_name")),
        ("Mã số thuế", _token_text(token, "tax_code")),
        ("Nhà cung cấp", _token_text(token, "issuer_name")),
        ("Token", _token_text(token, "token_label")),
        ("Serial", _token_text(token, "serial")),
        ("Serial chứng thư", _token_text(token, "cert_serial")),
        ("Nhà sản xuất", _token_text(token, "manufacturer")),
        ("Model", _token_text(token, "model")),
        ("Driver", _token_text(token, "driver")),
        ("Đường dẫn", _token_text(token, "driver_path")),
    ]
    return [f"{label}: {value}" for label, value in rows if value]


def _tokens_summary(tokens: list) -> str:
    sections = []
    for index, token in enumerate(tokens, start=1):
        details = "\n".join(_token_detail_lines(token))
        sections.append(f"USB {index}: {_token_display_name(token)}" + (f"\n{details}" if details else ""))
    return "\n\n".join(sections)


class TokenSelectDialog(QDialog):
    def __init__(self, parent=None, *, tokens: list, title: str = "Chọn USB ký số"):
        super().__init__(parent)
        self._tokens = list(tokens)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(760, 340)

        root = QVBoxLayout(self)

        intro = QLabel(f"Tìm thấy {len(self._tokens)} thiết bị/chứng thư ký số. Chọn USB token cần dùng.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.table = QTableWidget(len(self._tokens), 5, self)
        self.table.setHorizontalHeaderLabels(["Người ký", "MST", "Token/Serial", "Issuer", "Driver"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, token in enumerate(self._tokens):
            token_label = _token_text(token, "token_label")
            serial = _token_text(token, "serial")
            token_serial = " / ".join(part for part in (token_label, serial) if part)
            values = [
                _token_text(token, "signer_name") or "Chưa đọc được chứng thư",
                _token_text(token, "tax_code"),
                token_serial or _token_display_name(token),
                _token_text(token, "issuer_name") or _token_text(token, "manufacturer") or _token_text(token, "model"),
                _token_text(token, "driver"),
            ]
            tooltip = "\n".join(_token_detail_lines(token))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if tooltip:
                    item.setToolTip(tooltip)
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()
        if self._tokens:
            self.table.selectRow(0)
        self.table.doubleClicked.connect(self.accept)
        root.addWidget(self.table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Dùng USB này")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_token(self):
        if not self._tokens:
            return None
        row = self.table.currentRow()
        if row < 0:
            row = 0
        return self._tokens[row]


def _list_signing_tokens(provider, pin: str | None = None) -> list:
    list_tokens = getattr(provider, "list_tokens", None)
    if callable(list_tokens):
        return list(list_tokens(pin))
    token = provider.get_token_info(pin)
    return [token] if token else []


def _select_token_in_provider(provider, token) -> None:
    select_token = getattr(provider, "select_token", None)
    if callable(select_token):
        select_token(token)


def _choose_signing_token(
    window,
    provider,
    *,
    title: str = "Chọn USB ký số",
    required: bool = True,
    auto_single: bool = True,
):
    tokens = _list_signing_tokens(provider)
    if not tokens:
        details = provider.get_last_error()
        detail_line = f"\n\nChi tiết:\n{details}" if details else ""
        if required:
            show_warning(
                window,
                "Không tìm thấy thiết bị ký số",
                "Chưa phát hiện USB token/chứng thư ký số nào.\n"
                "Vui lòng cắm USB token, cài middleware của nhà cung cấp, rồi thử lại."
                + detail_line,
            )
        return None

    if auto_single and len(tokens) == 1:
        token = tokens[0]
        _select_token_in_provider(provider, token)
        return token

    dialog = TokenSelectDialog(window, tokens=tokens, title=title)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None

    token = dialog.selected_token()
    _select_token_in_provider(provider, token)
    return token


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

    def _finish_area(page_number, left, bottom, right, top, page_width, page_height):
        result.update(
            {
                "page_number": page_number,
                "box": (left, bottom, right, top),
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
    bridge.area_picked.connect(_finish_area)
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
    provider = get_signing_provider()
    tokens = _list_signing_tokens(provider)
    if not tokens:
        details = provider.get_last_error()
        detail_line = f"\n\nChi tiết: {details}" if details else ""
        show_warning(
            window,
            "Không tìm thấy thiết bị ký số",
            "Chưa cắm USB ký số hoặc trình điều khiển chưa được cài đặt."
            + detail_line,
        )
        return

    _select_token_in_provider(provider, tokens[0])
    plural_line = (
        f"Đã tự động nhận diện {len(tokens)} USB/chứng thư ký số."
        if len(tokens) > 1
        else "Đã tự động nhận diện USB ký số."
    )
    show_info(
        window,
        "Thiết bị ký số",
        f"{plural_line}\n\n{_tokens_summary(tokens)}",
    )


@require_document(show_message=True)
def create_signature_field(window):
    """Create one or more reusable empty signature fields on the current PDF."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields
    import tempfile
    import shutil
    import re
    import unicodedata

    def _safe_signature_field_name(value: str, fallback: str) -> str:
        raw = (value or "").strip() or fallback
        ascii_name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
        ascii_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", ascii_name).strip("_")
        return (ascii_name or fallback)[:96]

    placements: list[dict] = []
    base_name = _safe_signature_field_name(
        os.path.splitext(os.path.basename(window.current_path))[0],
        "Document",
    )

    while True:
        placement = _pick_signature_placement(window)
        if not placement:
            break

        default_name = f"Signature_{base_name}_{len(placements) + 1}"
        field_name, ok = QInputDialog.getText(
            window,
            "Tạo ô ký số",
            "Tên ô ký số:",
            QLineEdit.EchoMode.Normal,
            default_name,
        )
        if not ok:
            break

        display_name = (field_name or "").strip()
        field_name = _safe_signature_field_name(display_name, default_name)
        if not field_name:
            show_warning(window, "Thiếu tên ô ký", "Vui lòng nhập tên ô ký số.")
            continue

        placements.append(
            {
                "field_name": field_name,
                "display_name": display_name or field_name,
                "box": placement["box"],
                "page_number": placement["page_number"],
            }
        )
        _set_signature_field_marks(window, placements)

        reply = QMessageBox.question(
            window,
            "Thêm ô ký",
            "Đã ghi nhận ô ký tạm.\n\nBạn có muốn đặt thêm ô ký khác trên tài liệu này không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            break

    if not placements:
        _clear_signature_field_marks(window)
        return

    try:
        output_path = os.path.join(tempfile.gettempdir(), f"3t_sigfields_{os.getpid()}.pdf")
        with open(window.current_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f, strict=False)
            used_names: set[str] = {
                str(name)
                for name, _value, _ref in fields.enumerate_sig_fields(writer)
                if name
            }

            def _unique_field_name(base: str) -> str:
                candidate = base
                idx = 2
                while candidate in used_names:
                    candidate = f"{base}_{idx}"
                    idx += 1
                used_names.add(candidate)
                return candidate

            for item in placements:
                field_name = _unique_field_name(item["field_name"])
                fields.append_signature_field(
                    writer,
                    sig_field_spec=fields.SigFieldSpec(
                        sig_field_name=field_name,
                        box=item["box"],
                        on_page=max(0, item["page_number"] - 1),
                    ),
                )
            with open(output_path, "wb") as out:
                writer.write(out)

        shutil.copy2(output_path, window.current_path)
        try:
            os.remove(output_path)
        except OSError:
            pass

        _refresh_document_view(window, window.current_path, page_number=placements[-1]["page_number"])
        _clear_signature_field_marks(window)
        window.status.showMessage(f"Đã tạo {len(placements)} ô ký số trên file đang mở", 3000)
    except Exception:
        _clear_signature_field_marks(window)
        traceback.print_exc()
        msg = QMessageBox(window)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Lỗi tạo ô ký số")
        msg.setText("Không thể tạo ô ký số.")
        msg.setDetailedText(traceback.format_exc())
        msg.exec()


@require_document(show_message=True)
def sign_with_pfx(window):
    """Sign current PDF using a local PKCS#12 / PFX certificate file."""
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

        preview_bridge.adjusted.connect(_apply_preview_adjustment)

    def _navigate_to_page(page_no: int):
        wv = _get_web_view(window)
        if wv:
            wv.page().runJavaScript(
                f"(function(){{var app=window.PDFViewerApplication;"
                f"if(app&&app.pdfViewer){{app.pdfViewer.currentPageNumber={int(page_no)};}}}})()"
            )

    last_preview_page = {"value": None}

    def _refresh_preview(*_args):
        pl = placement_dialog.placement()
        _set_signature_preview(window, pl)
        page_no = int(pl["page_number"])
        if last_preview_page["value"] != page_no:
            last_preview_page["value"] = page_no
            _navigate_to_page(page_no)

    placement_dialog.page_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.x_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.y_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.width_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.height_spin.valueChanged.connect(_refresh_preview)

    _refresh_preview()
    accepted_placement = False
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
        accepted_placement = True
    finally:
        if not accepted_placement:
            _set_signature_preview(window, None)
        _teardown_webchannel(web_view)

    pfx_path, _ = QFileDialog.getOpenFileName(
        window,
        "Chọn file chứng thư ký số",
        "",
        "PKCS#12 Files (*.p12 *.pfx);;All Files (*)",
    )
    if not pfx_path:
        _set_signature_preview(window, None)
        return

    pin, ok = QInputDialog.getText(
        window,
        "Nhập mật khẩu chứng thư",
        "Mật khẩu file PFX/P12:",
        QLineEdit.EchoMode.Password,
    )
    if not ok:
        _set_signature_preview(window, None)
        return

    identity_dialog = SignatureIdentityDialog(
        window,
        default_signer_name=os.path.splitext(os.path.basename(pfx_path))[0],
    )
    if identity_dialog.exec() != QDialog.DialogCode.Accepted:
        _set_signature_preview(window, None)
        return
    signer_name = identity_dialog.signer_name()

    default_output = f"{os.path.splitext(window.current_path)[0]}_pfx_signed.pdf"
    output_path, _ = QFileDialog.getSaveFileName(
        window,
        "Lưu file đã ký",
        default_output,
        "PDF Files (*.pdf)",
    )
    if not output_path:
        _set_signature_preview(window, None)
        return

    try:
        asyncio.run(
            sign_pdf_with_pkcs12(
                pfx_path,
                pin,
                window.current_path,
                output_path,
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

        validation = validate_signed_pdf_status(output_path)
        validation_line = str(validation.get("message") or "")

        reply = QMessageBox.question(
            window,
            "Ký từ file chứng thư thành công",
            "Ký từ file chứng thư thành công!\n\n"
            f"Trạng thái: {validation_line}\n\n"
            f"File lưu tại:\n{output_path}\n\n"
            "Mở file đã ký ngay?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            _refresh_document_view(window, output_path, page_number=placement["page_number"])

    except Exception:
        traceback.print_exc()
        msg = QMessageBox(window)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Lỗi ký từ file chứng thư")
        msg.setText("Ký từ file chứng thư thất bại!")
        msg.setDetailedText(traceback.format_exc())
        msg.exec()
    finally:
        _set_signature_preview(window, None)


@require_document(show_message=True)
def sign_document(window):
    signing_provider = get_signing_provider()
    signer_info = _choose_signing_token(
        window,
        signing_provider,
        title="Chọn USB ký số để ký tài liệu",
        required=True,
    )
    if not signer_info:
        return

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

        preview_bridge.adjusted.connect(_apply_preview_adjustment)

    def _navigate_to_page(page_no: int):
        """Cuộn PDF viewer đến trang chỉ định."""
        wv = _get_web_view(window)
        if wv:
            wv.page().runJavaScript(
                f"(function(){{var app=window.PDFViewerApplication;"
                f"if(app&&app.pdfViewer){{app.pdfViewer.currentPageNumber={int(page_no)};}}}})()"
            )

    def _refresh_preview(*_args):
        pl = placement_dialog.placement()
        _set_signature_preview(window, pl)
        _navigate_to_page(pl["page_number"])

    placement_dialog.page_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.x_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.y_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.width_spin.valueChanged.connect(_refresh_preview)
    placement_dialog.height_spin.valueChanged.connect(_refresh_preview)

    _refresh_preview()
    accepted_placement = False
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
        accepted_placement = True
    finally:
        if not accepted_placement:
            _set_signature_preview(window, None)
        _teardown_webchannel(web_view)

    default_signer_name = signer_info.signer_name if signer_info else ""

    identity_dialog = SignatureIdentityDialog(
        window,
        default_signer_name=default_signer_name,
    )
    if identity_dialog.exec() != QDialog.DialogCode.Accepted:
        _set_signature_preview(window, None)
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
        _set_signature_preview(window, None)
        return

    pin, ok = QInputDialog.getText(
        window, "Nhập mã PIN", "PIN của USB ký số:",
        QLineEdit.EchoMode.Password
    )
    if not ok or not pin:
        _set_signature_preview(window, None)
        return

    if signer_name == "Khong ro":
        signer_info_with_pin = signing_provider.get_token_info(pin)
        if signer_info_with_pin and signer_info_with_pin.signer_name:
            signer_name = signer_info_with_pin.signer_name

    try:
        asyncio.run(
            signing_provider.sign_pdf(
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

        validation = validate_signed_pdf_status(output_path)
        validation_line = str(validation.get("message") or "")

        reply = QMessageBox.question(
            window,
            "Ký số thành công",
            "Ký số thành công!\n\n"
            f"Trạng thái: {validation_line}\n\n"
            f"File lưu tại:\n{output_path}\n\n"
            "Mở file đã ký ngay?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            _refresh_document_view(window, output_path, page_number=placement["page_number"])

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
    finally:
        _set_signature_preview(window, None)


def _format_signature_report_vn(report: dict, path: str | None = None) -> str:
    lines: list[str] = []
    if path:
        lines.append(f"File: {path}")
    lines.append(f"Kết luận: {report.get('overall_status') or report.get('message') or 'Không rõ'}")
    lines.append(f"Tính toàn vẹn: {'Đạt' if report.get('integrity_ok') else 'Không đạt'}")
    lines.append(f"Chuỗi tin cậy: {'Đã xác minh' if report.get('trusted') else 'Chưa xác minh'}")
    if report.get("subject_name"):
        lines.append(f"Chủ thể: {report.get('subject_name')}")
    if report.get("issuer_name"):
        lines.append(f"Nhà cung cấp: {report.get('issuer_name')}")
    if report.get("serial_hex"):
        lines.append(f"Serial: {report.get('serial_hex')}")
    if report.get("valid_from") or report.get("valid_to"):
        lines.append(
            f"Hiệu lực: {report.get('valid_from') or 'Không rõ'} - {report.get('valid_to') or 'Không rõ'}"
        )
    if report.get("certificate_status"):
        lines.append(f"Trạng thái chứng thư: {report.get('certificate_status')}")
    signing_time = report.get("signing_time")
    if signing_time:
        lines.append(f"Thời điểm ký: {signing_time}")
    signing_time_ok = report.get("signing_time_ok")
    if signing_time_ok is True:
        lines.append("Thời điểm ký nằm trong thời hạn hiệu lực.")
    elif signing_time_ok is False:
        lines.append("Thời điểm ký nằm ngoài thời hạn hiệu lực.")
    if report.get("validation_error"):
        lines.append(f"Lỗi kiểm tra: {report.get('validation_error')}")
    if not report.get("integrity_ok"):
        lines.append("Lưu ý: Nếu chỉ chèn ảnh hoặc text thì đây không phải chữ ký số hợp lệ.")
    return "\n".join(lines)


def _show_signature_report_vn(window, title: str, report: dict, *, path: str | None = None):
    msg = QMessageBox(window)
    msg.setWindowTitle(title)
    msg.setIcon(QMessageBox.Icon.Information if report.get("ok") else QMessageBox.Icon.Warning)
    msg.setText(report.get("overall_status") or report.get("message") or "Không rõ kết quả.")
    msg.setDetailedText(_format_signature_report_vn(report, path))
    msg.exec()


def verify_signed_document(window):
    """Check PDF signature validity and show a detailed report."""
    default_path = getattr(window, "current_path", "") or ""
    start_path = default_path if os.path.isfile(default_path) else ""
    if default_path and os.path.exists(default_path):
        report = validate_signed_pdf_status(default_path)
        _show_signature_report_vn(window, "Kiểm tra chữ ký số", report, path=default_path)
        return
    path, _ = QFileDialog.getOpenFileName(
        window,
        "Chọn file PDF cần kiểm tra chữ ký",
        start_path,
        "PDF Files (*.pdf);;All Files (*)",
    )
    if not path:
        return

    report = validate_signed_pdf_status(path)
    _show_signature_report_vn(window, "Kiểm tra chữ ký số", report, path=path)


@require_document(show_message=True)
def sign_handwritten(window):
    """Draw or import a signature image and place it on the current PDF."""
    import fitz
    import shutil
    import tempfile
    import uuid
    import os as _os

    from app.signature_pad import SignaturePadDialog

    source, ok = QInputDialog.getItem(
        window,
        "Chọn kiểu ký",
        "Nguồn chữ ký:",
        ["Vẽ tay", "Nhập mã mẫu", "Chọn từ danh sách", "Chọn ảnh chữ ký", "Chọn con dấu PNG"],
        0,
        False,
    )
    if not ok:
        return

    sig_img_path = ""
    if source == "Vẽ tay":
        pad = SignaturePadDialog(window)
        if pad.exec() != QDialog.DialogCode.Accepted:
            return
        pixmap = pad.get_pixmap()
        if not pixmap:
            return

        tmp_dir = _os.path.join(tempfile.gettempdir(), "reader_pdf_sig")
        _os.makedirs(tmp_dir, exist_ok=True)
        sig_img_path = _os.path.join(tmp_dir, f"sig_{uuid.uuid4().hex[:8]}.png")
        pixmap.save(sig_img_path, "PNG")
    elif source == "Nhập mã mẫu":
        templates = list_signature_templates()
        if not templates:
            show_warning(window, "Chưa có mẫu", "Chưa có mẫu chữ ký nào được lưu.")
            return
        code, ok = QInputDialog.getText(
            window,
            "Nhập mã mẫu chữ ký",
            "Mã mẫu:",
        )
        if not ok or not code.strip():
            return
        chosen_item = find_signature_template(code.strip())
        if not chosen_item:
            show_warning(
                window,
                "Không tìm thấy mẫu",
                "Không có mẫu nào khớp mã bạn nhập.\n\n"
                "Bạn có thể chọn từ danh sách để xem các mã đang có.",
            )
            return
        sig_img_path = chosen_item["path"]
    elif source == "Chọn từ danh sách":
        templates = list_signature_templates()
        if not templates:
            show_warning(window, "Chưa có mẫu", "Chưa có mẫu chữ ký nào được lưu.")
            return
        labels = [item["label"] for item in templates]
        chosen, ok = QInputDialog.getItem(
            window,
            "Chọn mẫu chữ ký",
            "Mẫu đã lưu:",
            labels,
            0,
            False,
        )
        if not ok:
            return
        chosen_item = next((item for item in templates if item["label"] == chosen), None)
        if not chosen_item:
            return
        sig_img_path = chosen_item["path"]
    else:
        image_path, _ = QFileDialog.getOpenFileName(
            window,
            "Chọn ảnh chữ ký / con dấu",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if not image_path:
            return

        tmp_dir = _os.path.join(tempfile.gettempdir(), "reader_pdf_sig")
        _os.makedirs(tmp_dir, exist_ok=True)
        ext = _os.path.splitext(image_path)[1].lower() or ".png"
        sig_img_path = _os.path.join(tmp_dir, f"sig_{uuid.uuid4().hex[:8]}{ext}")
        try:
            shutil.copy2(image_path, sig_img_path)
        except OSError:
            sig_img_path = image_path

    placement = _pick_signature_placement(window)
    # Nếu huỷ click chọn vị trí thì placement=None, dùng vị trí mặc định
    # (không bắt buộc phải click — có thể chọn qua spinbox)

    page_count, current_page = 1, 1
    if window.viewer:
        try:
            page_count = max(1, window.viewer.get_page_count())
            current_page = max(1, window.viewer.get_current_page())
        except Exception:
            pass

    initial_page = current_page
    if placement and "page_number" in placement:
        initial_page = int(placement["page_number"])

    placement_dialog = SignaturePlacementDialog(
        window,
        page_count=page_count,
        current_page=initial_page,
        initial_placement=placement,
    )

    web_view = _get_web_view(window)
    preview_bridge = None
    if web_view is not None:
        preview_bridge = SignaturePreviewAdjustBridge(placement_dialog)
        _setup_webchannel(web_view, placement_dialog, "sigPreviewBridge", preview_bridge)

        def _apply_adj(page_number, left, bottom, right, top):
            width = max(1.0, right - left)
            height = max(1.0, top - bottom)
            for spin in (placement_dialog.page_spin, placement_dialog.x_spin,
                         placement_dialog.y_spin, placement_dialog.width_spin,
                         placement_dialog.height_spin):
                spin.blockSignals(True)
            try:
                placement_dialog.page_spin.setValue(
                    min(int(page_number), placement_dialog.page_spin.maximum()))
                placement_dialog.x_spin.setValue(left / MM_TO_PT)
                placement_dialog.y_spin.setValue(bottom / MM_TO_PT)
                placement_dialog.width_spin.setValue(width / MM_TO_PT)
                placement_dialog.height_spin.setValue(height / MM_TO_PT)
            finally:
                for spin in (placement_dialog.page_spin, placement_dialog.x_spin,
                             placement_dialog.y_spin, placement_dialog.width_spin,
                             placement_dialog.height_spin):
                    spin.blockSignals(False)

        preview_bridge.adjusted.connect(_apply_adj)

    def _nav_page(page_no: int):
        wv2 = _get_web_view(window)
        if wv2:
            wv2.page().runJavaScript(
                f"(function(){{var app=window.PDFViewerApplication;"
                f"if(app&&app.pdfViewer){{app.pdfViewer.currentPageNumber={int(page_no)};}}}})()"
            )

    def _refresh_prev(*_):
        pl = placement_dialog.placement()
        _set_signature_preview(window, pl)
        _nav_page(pl["page_number"])

    for spin in (placement_dialog.page_spin, placement_dialog.x_spin,
                 placement_dialog.y_spin, placement_dialog.width_spin,
                 placement_dialog.height_spin):
        spin.valueChanged.connect(_refresh_prev)

    _refresh_prev()
    loop = QEventLoop(placement_dialog)
    placement_dialog.finished.connect(
        lambda _code: loop.quit() if loop.isRunning() else None)
    placement_dialog.show()
    placement_dialog.raise_()
    placement_dialog.activateWindow()
    try:
        loop.exec()
        if placement_dialog.result() != QDialog.DialogCode.Accepted:
            return
        placement = placement_dialog.placement()
    finally:
        _set_signature_preview(window, None)
        _teardown_webchannel(web_view)

    if not placement or "box" not in placement or "page_number" not in placement:
        return

    page_no = placement["page_number"]
    box = placement["box"]

    try:
        doc = fitz.open(window.current_path)
        page = doc[page_no - 1]
        page_h = page.rect.height
        left, bottom, right, top_pt = box
        rect = fitz.Rect(left, page_h - top_pt, right, page_h - bottom)
        page.insert_image(rect, filename=sig_img_path, keep_proportion=True)

        tmp_dir2 = _os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
        _os.makedirs(tmp_dir2, exist_ok=True)
        out_path = _os.path.join(tmp_dir2, f"signature_edit_{uuid.uuid4().hex[:8]}.pdf")
        doc.save(out_path)
        doc.close()

        shutil.copy2(out_path, window.current_path)
        try:
            _os.remove(out_path)
        except OSError:
            pass

        _refresh_document_view(window, window.current_path, page_number=page_no)
        if hasattr(window, "status"):
            window.status.showMessage("Đã đặt chữ ký tay lên PDF", 3000)
    except Exception as exc:
        import traceback
        show_warning(window, "Lỗi chèn chữ ký", traceback.format_exc())
def verify_signed_document(window):
    """Check the currently opened PDF signature validity."""
    default_path = getattr(window, "current_path", "") or ""
    if not default_path or not os.path.exists(default_path):
        show_warning(window, "Chưa có tệp", "Vui lòng mở file PDF trước khi kiểm tra chữ ký.")
        return

    report = validate_signed_pdf_status(default_path)
    _show_signature_report_vn(window, "Kiểm tra chữ ký số", report, path=default_path)


class SignatureStatusDialog(QDialog):
    def __init__(self, parent, report: dict, *, path: str | None = None):
        super().__init__(parent)
        self._report = report
        self._path = path
        self.setWindowTitle("Chữ ký số")
        self.setModal(True)
        self.setMinimumWidth(380)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        top = QHBoxLayout()
        icon_label = QLabel()
        icon_kind = (
            QStyle.StandardPixmap.SP_DialogApplyButton
            if report.get("ok")
            else QStyle.StandardPixmap.SP_MessageBoxWarning
        )
        icon_label.setPixmap(self.style().standardIcon(icon_kind).pixmap(36, 36))
        top.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        title_wrap = QVBoxLayout()
        title = QLabel("Hợp lệ Chữ ký" if report.get("ok") else "Chữ ký không hợp lệ")
        title.setStyleSheet(
            "font-size: 17px; font-weight: 700; color: %s;"
            % ("#168038" if report.get("ok") else "#c23b22")
        )
        title_wrap.addWidget(title)

        signer = str(report.get("subject_name") or "Không rõ")
        signer_label = QLabel(signer)
        signer_label.setWordWrap(True)
        signer_label.setStyleSheet("font-size: 12px; color: #2b2b2b;")
        title_wrap.addWidget(signer_label)

        signed_time = report.get("signing_time")
        if signed_time:
            time_label = QLabel(f"Đã ký {signed_time}")
            time_label.setStyleSheet("font-size: 11px; color: #666666;")
            title_wrap.addWidget(time_label)

        top.addLayout(title_wrap)
        root.addLayout(top)

        summary = QLabel(report.get("overall_status") or report.get("message") or "Không rõ")
        summary.setWordWrap(True)
        summary.setStyleSheet(
            "background:#f5f7fb; border:1px solid #d9e0ea; border-radius:8px; "
            "padding:8px 10px; color:#223; font-size:11px;"
        )
        root.addWidget(summary)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setSpacing(6)

        identity_value = QLabel("Hợp lệ" if report.get("trusted") else "Chưa xác minh")
        modify_value = QLabel("Không" if report.get("integrity_ok") else "Có")
        cert_value = QLabel(str(report.get("certificate_status") or "Không rõ"))
        issuer_value = QLabel(str(report.get("issuer_name") or "Không rõ"))

        for widget in (identity_value, modify_value, cert_value, issuer_value):
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form.addRow("Danh tính người ký", identity_value)
        form.addRow("Đã sửa đổi tài liệu", modify_value)
        form.addRow("Trạng thái chứng thư", cert_value)
        form.addRow("Nhà cung cấp", issuer_value)
        root.addLayout(form)

        validation_error = str(report.get("validation_error") or "").strip()
        if validation_error:
            error_label = QLabel(
                ("Thông tin kiểm tra: " if report.get("ok") else "Lỗi kiểm tra: ")
                + validation_error
            )
            error_label.setWordWrap(True)
            error_label.setStyleSheet(
                "color:#b07a00; font-size:11px;" if report.get("ok") else "color:#b03030; font-size:11px;"
            )
            root.addWidget(error_label)

        policy_warning = str(report.get("policy_warning") or "").strip()
        if policy_warning:
            warning_label = QLabel(f"Cảnh báo chính sách: {policy_warning}")
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet("color:#b07a00; font-size:11px;")
            root.addWidget(warning_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._detail_btn = QPushButton("Thuộc tính")
        buttons.addButton(self._detail_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._detail_btn.clicked.connect(self._show_details)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _show_details(self):
        _show_signature_report_vn(self, "Chi tiết chữ ký số", self._report, path=self._path)


def verify_signed_document(window):
    """Check the currently opened PDF signature validity."""
    default_path = getattr(window, "current_path", "") or ""
    if not default_path or not os.path.exists(default_path):
        show_warning(window, "Chưa có tệp", "Vui lòng mở file PDF trước khi kiểm tra chữ ký.")
        return

    report = validate_signed_pdf_status(default_path)
    dlg = SignatureStatusDialog(window, report, path=default_path)
    dlg.exec()
