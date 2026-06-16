import base64
import json
import os
# USB PIN CACHE
_cached_usb_pin = ""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
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
from packages.qt_compat.QtCore import QObject, QEventLoop, Qt, QThread, QTimer, pyqtSignal, pyqtSlot

from packages.signing import get_signing_provider
from packages.signing.shared import sign_pdf_with_pkcs12, validate_signed_pdf_status
from app.actions._guard import require_document
from app.actions._pdf_save import make_staged_pdf_path, replace_document_with_staged
from app.dialogs import show_warning, show_info
from app.signature_templates import find_signature_template, list_signature_templates


def _get_web_view(window):
    """Shared: safely retrieve QWebEngineView from window."""
    getter = getattr(window, "_get_webview", None)
    return getter() if callable(getter) else None


def _setup_webchannel(web_view, parent, name, bridge):
    """Shared: update the stable viewer QWebChannel proxy target."""
    from app.webchannel import register_webchannel_object

    return register_webchannel_object(web_view, parent, name, bridge)


def _teardown_webchannel(web_view):
    """Shared: detach QWebChannel from the web view."""
    if web_view is None:
        return
    try:
        from app.webchannel import unregister_webchannel_object

        unregister_webchannel_object(web_view)
    except RuntimeError:
        pass


def _cleanup_signature_preview(window, web_view=None):
    """Remove temporary signature preview UI and detach its WebChannel bridge."""
    _set_signature_preview(window, None)
    if web_view is None:
        web_view = _get_web_view(window)
    _teardown_webchannel(web_view)


def _confirm_signature_selection(window) -> bool:
    reply = QMessageBox.question(
        window,
        "Xác nhận vị trí ký",
        "Bạn có đồng ý ký văn bản này tại vị trí đã chọn không?\n\n"
        "Chọn No nếu muốn kéo lại vùng ký.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes


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
            zoom = str(getattr(getattr(window, "zoom_spin", None), "value", lambda: 100)())
            viewer.load_pdf(
                output_path,
                page=max(1, int(page_number or 1)),
                zoom=zoom,
            )
        except Exception:
            traceback.print_exc()
            show_warning(window, "Lỗi mở file đã ký", "Không thể hiển thị file vừa ký.")

    QTimer.singleShot(0, _load)


class _SigningWorker(QObject):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str, str, str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self._fn()
        except Exception as exc:
            self.failed.emit(type(exc).__name__, str(exc), traceback.format_exc())
        else:
            self.succeeded.emit()


def _run_signing_task(window, fn, *, status_message: str) -> tuple[bool, tuple[str, str, str] | None]:
    existing = getattr(window, "_signing_thread", None)
    if existing is not None and existing.isRunning():
        show_warning(window, "Đang ký số", "Vui lòng chờ thao tác ký hiện tại hoàn tất.")
        return False, ("SigningBusy", "Đang có thao tác ký đang chạy.", "")

    pause_token_monitor = getattr(window, "_pause_token_monitor", None)
    resume_token_monitor = getattr(window, "_resume_token_monitor", None)
    if callable(pause_token_monitor):
        pause_token_monitor()

    worker = _SigningWorker(fn)
    thread = QThread(window)
    worker.moveToThread(thread)

    loop = QEventLoop(window)
    result: dict[str, object] = {"ok": False, "error": None}

    def _finish_success():
        result["ok"] = True
        if loop.isRunning():
            loop.quit()

    def _finish_error(exc_type: str, exc_message: str, tb_text: str):
        result["ok"] = False
        result["error"] = (exc_type, exc_message, tb_text)
        if loop.isRunning():
            loop.quit()

    worker.succeeded.connect(_finish_success)
    worker.failed.connect(_finish_error)
    worker.succeeded.connect(thread.quit)
    worker.failed.connect(thread.quit)
    worker.succeeded.connect(worker.deleteLater)
    worker.failed.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda: setattr(window, "_signing_thread", None))
    thread.started.connect(worker.run)

    window._signing_thread = thread
    try:
        if hasattr(window, "status"):
            window.status.showMessage(status_message, 0)
        thread.start()
        loop.exec()
    finally:
        if hasattr(window, "status"):
            window.status.clearMessage()
        if callable(resume_token_monitor):
            resume_token_monitor()

    return bool(result["ok"]), result["error"]


def _run_usb_signing_task(window, fn, *, status_message: str) -> tuple[bool, tuple[str, str, str] | None]:
    """Run USB signing in the main process without a Qt worker thread.

    The PKCS#11 work itself already happens in a subprocess. Keeping the parent
    on the GUI thread avoids native Qt/Shiboken crashes observed while tearing
    down background thread objects immediately after the USB worker exits.
    """
    pause_token_monitor = getattr(window, "_pause_token_monitor", None)
    resume_token_monitor = getattr(window, "_resume_token_monitor", None)
    if callable(pause_token_monitor):
        pause_token_monitor()

    try:
        if hasattr(window, "status"):
            window.status.showMessage(status_message, 0)
        fn()
        return True, None
    except Exception as exc:
        return False, (type(exc).__name__, str(exc), traceback.format_exc())
    finally:
        if hasattr(window, "status"):
            window.status.clearMessage()
        if callable(resume_token_monitor):
            resume_token_monitor()


def _token_info_payload(token_info) -> dict[str, object]:
    if token_info is None:
        return {}
    return {
        "driver": getattr(token_info, "driver", ""),
        "signer_name": getattr(token_info, "signer_name", ""),
        "tax_code": getattr(token_info, "tax_code", ""),
        "driver_path": getattr(token_info, "driver_path", ""),
        "token_index": getattr(token_info, "token_index", 0),
        "token_label": getattr(token_info, "token_label", ""),
        "serial": getattr(token_info, "serial", ""),
        "manufacturer": getattr(token_info, "manufacturer", ""),
        "model": getattr(token_info, "model", ""),
        "issuer_name": getattr(token_info, "issuer_name", ""),
        "cert_serial": getattr(token_info, "cert_serial", ""),
    }



def _get_tsa_url() -> str | None:
    try:
        cfg_path = os.path.expanduser("~/.3t_reader/signing_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            tsa_mode = cfg.get("tsa_mode")
            saved_url = cfg.get("tsa_url", "")
            if not tsa_mode:
                if saved_url == f"{VPS_LICENSE_BASE_URL}/api/v1/tsa":
                    tsa_mode = "server"
                elif saved_url:
                    tsa_mode = "custom"
                else:
                    tsa_mode = "system"
            
            if tsa_mode == "system":
                return None
            elif tsa_mode == "server":
                return f"{VPS_LICENSE_BASE_URL}/api/v1/tsa"
            else:
                return saved_url or None
    except Exception:
        return None


def _get_ltv_setting() -> bool:
    try:
        cfg_path = os.path.expanduser("~/.3t_reader/signing_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return bool(cfg.get("enable_ltv", False))
    except Exception:
        return False

def _run_usb_signing_subprocess(
    token_info,
    input_path: str,
    output_path: str,
    pin: str,
    *,
    signer_name: str,
    page_number: int,
    box: tuple[float, float, float, float],
    field_name: str | None = None,
    reason: str | None = None,
    location: str | None = None,
    contact_info: str | None = None,
    tsa_url: str | None = None,
    enable_ltv: bool = False,
) -> None:
    payload = {
        "token": _token_info_payload(token_info),
        "input_path": input_path,
        "output_path": output_path,
        "pin": pin,
        "signer_name": signer_name,
        "page_number": page_number,
        "box": list(box),
        "field_name": field_name or "",
        "reason": reason or "",
        "location": location or "",
        "contact_info": contact_info or "",
        "tsa_url": tsa_url or "",
        "enable_ltv": enable_ltv,
    }

    payload_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
    payload_path = payload_file.name
    try:
        json.dump(payload, payload_file, ensure_ascii=False)
        payload_file.close()

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--usb-sign-worker", payload_path]
        else:
            cmd = [
                sys.executable,
                "-m",
                "packages.signing.usb_worker",
                payload_path,
            ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        )

        stdout = (result.stdout or "").strip().splitlines()
        if not stdout:
            raise RuntimeError(
                "USB signing worker did not return a result.\n"
                f"Return code: {result.returncode}\n"
                f"stderr: {(result.stderr or '').strip()}"
            )

        try:
            data = json.loads(stdout[-1])
        except Exception as exc:
            raise RuntimeError(
                "USB signing worker returned invalid output.\n"
                f"Return code: {result.returncode}\n"
                f"stdout: {(result.stdout or '').strip()}\n"
                f"stderr: {(result.stderr or '').strip()}"
            ) from exc

        if not data.get("ok"):
            error_type = str(data.get("error_type") or "RuntimeError")
            error_message = str(data.get("error_message") or "USB signing failed.")
            tb_text = str(data.get("traceback") or "")
            raise RuntimeError(f"{error_type}: {error_message}\n{tb_text}".strip())

        if result.returncode != 0:
            raise RuntimeError(
                "USB signing worker exited with a non-zero code despite reporting success.\n"
                f"Return code: {result.returncode}\n"
                f"stderr: {(result.stderr or '').strip()}"
            )
    finally:
        try:
            payload_file.close()
        except Exception:
            pass
        try:
            if os.path.exists(payload_path):
                os.remove(payload_path)
        except OSError:
            pass


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


def _build_stamp_preview_html(
    signer_display_name: str,
    *,
    tax_code: str = "",
    signed_at: str = "",
    issuer_name: str = "",
    token_serial: str = "",
    cert_serial: str = "",
) -> str:
    """Build HTML preview matching the digital stamp from build_vietnamese_stamp_style."""
    from html import escape as _esc

    safe_name = str(signer_display_name or "").strip() or "Không rõ"
    display_tax = tax_code or ""
    issuer = str(issuer_name or "").strip() or "Không rõ"
    serial = _compact_signature_preview_value(token_serial or cert_serial or "")
    lines = [
        "ĐÃ KÝ SỐ",
        f"Người ký: {safe_name}",
    ]
    if issuer and issuer != "Không rõ":
        lines.append(f"Đơn vị CA: {issuer}")
    if display_tax:
        lines.append(f"MST/CCCD: {display_tax}")
    lines.append(f"Thời điểm: {signed_at or 'Không rõ'}")
    if serial:
        lines.append(f"Serial: {serial}")
    lines.append("Trạng thái: Hợp lệ; tài liệu chưa bị sửa")

    img_path = ""
    img_mode = "left"
    try:
        cfg_path = os.path.expanduser("~/.3t_reader/signing_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            active_id = cfg.get("active_profile_id", "")
            profiles = cfg.get("profiles", [])
            for p in profiles:
                if p.get("id") == active_id:
                    img_path = p.get("path", "")
                    img_mode = p.get("mode", "left")
                    break
            else:
                img_path = cfg.get("signature_image_path", "")
                img_mode = cfg.get("signature_image_mode", "left")
    except Exception as e:
        print("CFG ERR:", e)
        pass
    
    b64_img = ""
    if img_path and os.path.exists(img_path):
        try:
            with open(img_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print("IMG ERR:", e)
            pass
    else:
        print("IMG PATH NOT FOUND:", img_path)

    html_lines = []
    for i, line in enumerate(lines):
        esc = _esc(line)
        if i == 0:
            html_lines.append(f'<div style="font-weight:700;color:#052e51;margin-bottom:2px">{esc}</div>')
        elif line.startswith("Trạng thái:") or line.startswith("Tr"):
            html_lines.append(f'<div style="color:#166534">{esc}</div>')
        elif ":" in line:
            label, value = line.split(":", 1)
            html_lines.append(
                '<div><span style="font-weight:600;color:#475569">'
                f'{_esc(label)}:</span> <span style="color:#0f172a">{_esc(value.strip())}</span></div>'
            )
        else:
            html_lines.append(f'<div style="color:#0f172a">{esc}</div>')

    text_content = (
        '<div style="font-family:Arial,Segoe UI,sans-serif;'
        'width:100%;height:100%;padding:8px;box-sizing:border-box;'
        'overflow:hidden;line-height:1.2;text-align:left;'
        'font-weight:400;letter-spacing:0;'
        'background:rgba(255,255,255,.86)">'
        + "".join(html_lines)
        + "</div>"
    )

    if b64_img:
        img_mime = "image/jpeg" if img_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"
        img_tag = f'<img src="data:{img_mime};base64,{b64_img}" style="max-width: 100%; max-height: 100%; object-fit: contain;" />'
        if img_mode == "only":
            return f'<div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">{img_tag}</div>'
        elif img_mode == "bg":
            return f'<div style="position: relative; width: 100%; height: 100%;"><div style="position: absolute; inset: 0; opacity: 0.3; display: flex; align-items: center; justify-content: center; pointer-events: none;">{img_tag}</div><div style="position: relative; z-index: 1; width: 100%; height: 100%;">{text_content}</div></div>'
        else: # left
            return f'<div style="display: flex; flex-direction: row; align-items: center; width: 100%; height: 100%; gap: 10px; background:rgba(255,255,255,.86); box-sizing:border-box; padding: 4px;"><div style="flex: 0 0 35%; height: 100%; display: flex; align-items: center; justify-content: center;">{img_tag}</div><div style="flex: 1; overflow: hidden; height: 100%;">{text_content}</div></div>'

    return text_content


def _format_local_timestamp(value: datetime | None = None) -> str:
    dt = (value or datetime.now()).astimezone()
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _compact_signature_preview_value(value: object, *, head: int = 12, tail: int = 8, limit: int = 28) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:head]}...{text[-tail:]}"


def _signature_preview_scale(width_px: float, height_px: float, *, has_image: bool = False) -> float:
    base = min(max(float(width_px), 1.0), max(float(height_px), 1.0))
    if has_image:
        return max(0.55, min(1.8, base / 180.0))
    return max(0.65, min(2.2, base / 160.0))


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


def _make_pick_script(*, sig_image_url: str = "", sig_text_html: str = "") -> str:
    """Generate the pick-phase JS script, optionally with preview content."""
    img_url_json = json.dumps(sig_image_url) if sig_image_url else "''"
    text_html_json = json.dumps(sig_text_html) if sig_text_html else "''"

    return f"""
(function () {{
    if (window.__readerPdfSignaturePickCleanup) {{
        try {{ window.__readerPdfSignaturePickCleanup(); }} catch (_err) {{}}
    }}
    window.__readerPdfSignaturePickInstalled = true;

    var _pickSigImgUrl = {img_url_json};
    var _pickSigTextHtml = {text_html_json};

    function attachBridge() {{
        if (typeof window.__3tWithBridge !== 'function') {{
            setTimeout(attachBridge, 50);
            return;
        }}

        window.__3tWithBridge('sigPickBridge', function (bridge) {{
            if (!bridge) {{
                return;
            }}

            let selection = null;

            function cleanupSelection() {{
                document.removeEventListener('mousedown', mouseDownHandler, true);
                document.removeEventListener('mousemove', mouseMoveHandler, true);
                document.removeEventListener('mouseup', mouseUpHandler, true);
                window.removeEventListener('keydown', keyHandler, true);
                if (selection && selection.box && selection.box.parentNode) {{
                    selection.box.parentNode.removeChild(selection.box);
                }}
                selection = null;
                window.__readerPdfSignaturePickCleanup = null;
                window.__readerPdfSignaturePickInstalled = false;
            }}

            window.__readerPdfSignaturePickCleanup = cleanupSelection;

            const keyHandler = function (event) {{
                if (event.key === 'Escape') {{
                    cleanupSelection();
                    bridge.cancelPick();
                }}
            }};

            function makeSelectionBox(page) {{
                const box = document.createElement('div');
                box.style.position = 'absolute';
                box.style.zIndex = '10000';
                box.style.pointerEvents = 'none';
                box.style.boxSizing = 'border-box';
                box.style.overflow = 'hidden';
                box.style.display = 'flex';
                box.style.alignItems = 'center';
                box.style.justifyContent = 'center';
                box.style.borderRadius = '4px';

                if (_pickSigImgUrl) {{
                    box.style.background = 'transparent';
                    box.style.border = '2px solid rgba(11,132,243,0.5)';
                    const img = document.createElement('img');
                    img.src = _pickSigImgUrl;
                    img.style.maxWidth = '90%';
                    img.style.maxHeight = '90%';
                    img.style.objectFit = 'contain';
                    img.style.pointerEvents = 'none';
                    img.draggable = false;
                    box.appendChild(img);
                }} else if (_pickSigTextHtml) {{
                    box.style.background = 'rgba(255,255,255,0.15)';
                    box.style.border = '2px solid rgba(11,132,243,0.65)';
                    box.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)';
                    const textDiv = document.createElement('div');
                    textDiv.innerHTML = _pickSigTextHtml;
                    textDiv.style.width = '100%';
                    textDiv.style.height = '100%';
                    textDiv.style.padding = '6px';
                    textDiv.style.boxSizing = 'border-box';
                    textDiv.style.overflow = 'hidden';
                    textDiv.style.pointerEvents = 'none';
                    textDiv.style.fontFamily = 'Arial, "Segoe UI", sans-serif';
                    textDiv.style.lineHeight = '1.2';
                    box.appendChild(textDiv);
                }} else {{
                    box.style.background = 'rgba(11, 132, 243, 0.3)';
                    box.style.border = '2px dashed rgba(11,132,243,0.4)';
                }}

                page.appendChild(box);
                return box;
            }}

            function applySelectionBox() {{
                if (!selection || !selection.box) return;
                const left = Math.min(selection.startX, selection.currentX);
                const top = Math.min(selection.startY, selection.currentY);
                const width = Math.abs(selection.currentX - selection.startX);
                const height = Math.abs(selection.currentY - selection.startY);
                selection.box.style.left = `${{left}}px`;
                selection.box.style.top = `${{top}}px`;
                selection.box.style.width = `${{Math.max(1, width)}}px`;
                selection.box.style.height = `${{Math.max(1, height)}}px`;
                const textDiv = selection.box.querySelector('div');
                if (textDiv && _pickSigTextHtml) {{
                    const lineCount = Math.max(1, textDiv.querySelectorAll('div').length || 1);
                    const fontSize = Math.max(5.5, Math.min(18, (Math.max(1, height) - 16) / (lineCount * 1.18), Math.max(1, width) / 30));
                    textDiv.style.fontSize = `${{fontSize}}px`;
                }}
            }}

            const mouseDownHandler = function(event) {{
                const page = event.target.closest('.page');
                if (!page || !page.dataset || !page.dataset.pageNumber) {{
                    return;
                }}
                const pageNumber = parseInt(page.dataset.pageNumber, 10);
                const pdfViewer = window.PDFViewerApplication && PDFViewerApplication.pdfViewer;
                const pageView = pdfViewer && (pdfViewer.getPageView
                    ? pdfViewer.getPageView(pageNumber - 1)
                    : (pdfViewer._pages && pdfViewer._pages[pageNumber - 1]));
                if (!pageView || !pageView.viewport || !pageView.pdfPage) {{
                    return;
                }}

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const rect = page.getBoundingClientRect();
                const localX = Math.max(0, Math.min(event.clientX - rect.left, page.clientWidth));
                const localY = Math.max(0, Math.min(event.clientY - rect.top, page.clientHeight));
                selection = {{
                    page,
                    pageNumber,
                    pageView,
                    startX: localX,
                    startY: localY,
                    currentX: localX,
                    currentY: localY,
                    box: makeSelectionBox(page),
                    dragging: true
                }};
                applySelectionBox();
            }};

            const mouseMoveHandler = function(event) {{
                if (!selection || !selection.dragging) return;
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const rect = selection.page.getBoundingClientRect();
                selection.currentX = Math.max(0, Math.min(event.clientX - rect.left, selection.page.clientWidth));
                selection.currentY = Math.max(0, Math.min(event.clientY - rect.top, selection.page.clientHeight));
                applySelectionBox();
            }};

            const mouseUpHandler = function(event) {{
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

                const baseViewport = selection.pageView.pdfPage.getViewport({{ scale: 1 }});
                const pageNumber = selection.pageNumber;

                if (dx < 5 && dy < 5) {{
                    const pdfPoint = selection.pageView.viewport.convertToPdfPoint(selection.startX, selection.startY);
                    cleanupSelection();
                    bridge.reportPick(
                        pageNumber,
                        pdfPoint[0],
                        pdfPoint[1],
                        baseViewport.width,
                        baseViewport.height
                    );
                }} else {{
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
                }}
            }};

            document.addEventListener('mousedown', mouseDownHandler, true);
            document.addEventListener('mousemove', mouseMoveHandler, true);
            document.addEventListener('mouseup', mouseUpHandler, true);
            window.addEventListener('keydown', keyHandler, true);
        }});
    }}

    if (document.readyState === 'complete') {{
        attachBridge();
    }} else {{
        window.addEventListener('load', attachBridge);
    }}
}})();
"""


def _set_signature_preview(window, placement: dict | None, *, sig_image_url: str = "", sig_text_html: str = ""):
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
            textDiv: null,
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
        if (typeof window.__3tWithBridge !== 'function') {{
            setTimeout(ensureBridge, 50);
            return;
        }}
        window.__3tWithBridge('sigPreviewBridge', function(bridge) {{
            window.__readerPdfSigPreviewBridge = bridge || null;
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
        state.textDiv = null;
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
        syncPreviewTypography(rect.width, rect.height);
    }}

    function syncPreviewTypography(width, height) {{
        if (!state.textDiv) {{
            return;
        }}
        const lineCount = Math.max(1, state.textDiv.querySelectorAll('div').length || 1);
        const byHeight = Math.max(5.5, (Math.max(1, height) - 16) / (lineCount * 1.18));
        const byWidth = Math.max(5.5, Math.max(1, width) / 30);
        const fontSize = Math.max(5.5, Math.min(18, byHeight, byWidth));
        state.textDiv.style.fontSize = `${{fontSize}}px`;
        state.textDiv.style.lineHeight = '1.2';
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

    const sigImgUrl = {json.dumps(sig_image_url) if sig_image_url else "''"};
    const sigTextHtml = {json.dumps(sig_text_html) if sig_text_html else "''"};

    let overlay = state.overlay;
    if (!overlay) {{
        overlay = document.createElement('div');
        overlay.style.position = 'absolute';
        overlay.style.pointerEvents = 'auto';
        overlay.style.zIndex = '40';
        overlay.style.boxSizing = 'border-box';
        overlay.style.cursor = 'move';
        overlay.style.userSelect = 'none';
        overlay.style.touchAction = 'none';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.overflow = 'hidden';
        overlay.style.borderRadius = '4px';

        if (sigImgUrl) {{
            overlay.style.background = 'transparent';
            overlay.style.border = '2px solid rgba(11,132,243,0.5)';
        }} else if (sigTextHtml) {{
            overlay.style.background = 'rgba(255,255,255,0.15)';
            overlay.style.border = '2px solid rgba(11,132,243,0.65)';
            overlay.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)';
        }} else {{
            overlay.style.background = 'rgba(11, 132, 243, 0.22)';
            overlay.style.border = '2px dashed rgba(11,132,243,0.5)';
        }}

        if (sigImgUrl) {{
            const img = document.createElement('img');
            img.src = sigImgUrl;
            img.style.maxWidth = '90%';
            img.style.maxHeight = '90%';
            img.style.objectFit = 'contain';
            img.style.pointerEvents = 'none';
            img.draggable = false;
            overlay.appendChild(img);
        }} else if (sigTextHtml) {{
            const textDiv = document.createElement('div');
            textDiv.innerHTML = sigTextHtml;
            textDiv.style.width = '100%';
            textDiv.style.height = '100%';
            textDiv.style.display = 'flex';
            textDiv.style.flexDirection = 'column';
            textDiv.style.justifyContent = 'flex-start';
            textDiv.style.alignItems = 'stretch';
            textDiv.style.boxSizing = 'border-box';
            textDiv.style.padding = '6px';
            textDiv.style.maxWidth = '95%';
            textDiv.style.maxHeight = '95%';
            textDiv.style.overflow = 'hidden';
            textDiv.style.pointerEvents = 'none';
            textDiv.style.fontFamily = 'Arial, "Segoe UI", sans-serif';
            overlay.appendChild(textDiv);
            state.textDiv = textDiv;
        }}

        const badge = document.createElement('div');
        badge.textContent = sigImgUrl ? 'Chữ ký mẫu' : (sigTextHtml ? 'Preview chữ ký số' : 'Preview chữ ký');
        badge.style.position = 'absolute';
        badge.style.left = '0';
        badge.style.top = '-20px';
        badge.style.padding = '1px 6px';
        badge.style.fontSize = '11px';
        badge.style.color = '#ffffff';
        badge.style.background = sigImgUrl ? '#22c55e' : (sigTextHtml ? '#168038' : '#0B84F3');
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
        signature_image_path: str = "",
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

        # ── Signature image preview ──
        self._sig_image_path = signature_image_path
        if signature_image_path and os.path.isfile(signature_image_path):
            preview_frame = QFrame()
            preview_frame.setStyleSheet(
                "QFrame { background: #ffffff; border: 1px solid #ccc; "
                "border-radius: 6px; padding: 8px; }"
            )
            preview_layout = QVBoxLayout(preview_frame)
            preview_layout.setContentsMargins(8, 8, 8, 8)

            preview_label = QLabel("Mẫu chữ ký:")
            preview_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #333;")
            preview_layout.addWidget(preview_label)

            img_label = QLabel()
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setMinimumHeight(60)
            img_label.setMaximumHeight(140)
            img_label.setStyleSheet("background: #fafafa; border: 1px dashed #ddd; border-radius: 4px;")
            pixmap = QPixmap(signature_image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(
                    120, Qt.TransformationMode.SmoothTransformation
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setText("(Không đọc được ảnh)")
            preview_layout.addWidget(img_label)
            root.addWidget(preview_frame)

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
        self.setWindowTitle("Thông tin chữ ký")
        self.setModal(True)

        root = QVBoxLayout(self)

        form = QFormLayout()
        self.signer_name_input = QLineEdit()
        self.signer_name_input.setPlaceholderText("Nhập tên người ký")
        if default_signer_name:
            self.signer_name_input.setText(default_signer_name)
        self.signer_name_input.textChanged.connect(self._update_preview)
        form.addRow("Người ký", self.signer_name_input)
        root.addLayout(form)

        preview_title = QLabel("Xem trước")
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
        ts = _format_local_timestamp()
        self.preview.setText(
            "ĐÃ KÝ SỐ\n"
            f"Người ký: {signer_name}\n"
            f"Thời điểm: {ts}"
        )

    def signer_name(self) -> str:
        return self.signer_name_input.text().strip() or "Khong ro"


class UnsignedSignatureSetupDialog(QDialog):
    def __init__(self, parent=None, *, report: dict | None = None):
        super().__init__(parent)
        self._report = report or {}
        self._selected_token = None
        self.setWindowTitle("Ký ô ký")
        self.setModal(True)
        self.resize(620, 420)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        title = QLabel("Ô ký chưa được ký số")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #c23b22;")
        root.addWidget(title)

        field_name = str(self._report.get("selected_field_name") or self._report.get("clicked_field") or "Không rõ")
        page_number = int(self._report.get("clicked_page") or 0)
        info = QLabel(f"Trường: {field_name}    Trang: {page_number or 'Không rõ'}")
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft)

        self.sign_as_combo = QComboBox()
        self.location_input = QLineEdit()
        self.reason_input = QComboBox()
        self.reason_input.setEditable(True)
        self.reason_input.addItems(
            [
                "Tôi là người tạo tài liệu này",
                "Tôi phê duyệt tài liệu này",
                "Tôi đã xem xét và chấp nhận tài liệu này",
            ]
        )
        self.reason_input.setCurrentText(str(self._report.get("reason") or "Tôi là người tạo tài liệu này"))

        provider = get_signing_provider()
        tokens = _list_signing_tokens(provider)
        for token in tokens:
            self.sign_as_combo.addItem(_token_display_name(token), token)
        if tokens:
            self._selected_token = tokens[0]
            self.sign_as_combo.setCurrentIndex(0)
        else:
            self.sign_as_combo.addItem("Không tìm thấy USB", None)

        self.sign_as_combo.currentIndexChanged.connect(self._on_sign_as_changed)
        self.location_input.textChanged.connect(self._update_preview)
        self.reason_input.currentTextChanged.connect(self._update_preview)

        form.addRow("Ký với tư cách", self.sign_as_combo)
        form.addRow("Địa điểm", self.location_input)
        form.addRow("Lý do", self.reason_input)
        root.addLayout(form)

        preview_title = QLabel("Xem trước")
        root.addWidget(preview_title)
        self.preview = QLabel()
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview.setStyleSheet(
            "background:#f7f7f7; border:1px solid #c9d2de; border-radius:6px; padding:10px;"
            "font-family:'Consolas';"
        )
        self.preview.setMinimumHeight(130)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.preview)

        buttons = QDialogButtonBox()
        self._sign_btn = QPushButton("Ký USB")
        self._close_btn = QPushButton("Đóng")
        buttons.addButton(self._sign_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self._close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self._sign_btn.clicked.connect(self._sign_usb)
        self._close_btn.clicked.connect(self.reject)
        root.addWidget(buttons)

        self._update_preview()

    def _on_sign_as_changed(self, index: int):
        token = self.sign_as_combo.currentData()
        self._selected_token = token
        self._update_preview()

    def _update_preview(self):
        signer = _token_display_name(self._selected_token) if self._selected_token else "Không rõ"
        location = self.location_input.text().strip() or "Địa điểm ký"
        reason = self.reason_input.currentText().strip() or "Tôi là người tạo tài liệu này"
        ts = _format_local_timestamp()
        self.preview.setText(
            "ĐÃ KÝ SỐ\n"
            f"Người ký: {signer}\n"
            f"Lý do: {reason}\n"
            f"Địa điểm: {location}\n"
            f"Thời điểm: {ts}\n"
            "Xem trước chữ ký của 3T Reader"
        )

    def _sign_usb(self):
        token = self.sign_as_combo.currentData()
        if token is None:
            show_warning(self, "USB token", "Không có USB nào khả dụng.")
            return
        self._selected_token = token
        self.accept()


def _sign_existing_signature_field_with_usb(window, report: dict, token_info) -> None:
    global _cached_usb_pin
    field_name = str(report.get("selected_field_name") or report.get("clicked_field") or "").strip()
    if not field_name:
        show_warning(window, "Thiếu ô ký", "Không xác định được ô ký cần ký.")
        return

    pin = _cached_usb_pin
    if not pin:
        pin, ok = QInputDialog.getText(
            window,
            "Nhập mã PIN",
            "PIN của USB ký số:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not pin:
            return
    _cached_usb_pin = pin

    default_output = f"{os.path.splitext(window.current_path)[0]}_signed.pdf"
    output_path, _ = QFileDialog.getSaveFileName(
        window,
        "Lưu file đã ký",
        default_output,
        "PDF Files (*.pdf)",
    )
    if not output_path:
        return

    in_place_output = os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(window.current_path))
    actual_output_path = (
        make_staged_pdf_path(window.current_path, prefix=".3t_existing_sig_", suffix=".pdf")
        if in_place_output
        else output_path
    )

    field_rect = report.get("field_rect") or (50, 50, 300, 100)
    box = tuple(float(v) for v in field_rect[:4]) if isinstance(field_rect, (list, tuple)) and len(field_rect) >= 4 else (50, 50, 300, 100)
    signer_name = _token_text(token_info, "signer_name") or _token_display_name(token_info)
    location = str(report.get("location") or "").strip()
    reason = str(report.get("reason") or "").strip()

    try:
        ok, error = _run_usb_signing_task(
            window,
            lambda: _run_usb_signing_subprocess(
                token_info,
                window.current_path,
                actual_output_path,
                pin,
                signer_name=signer_name,
                page_number=int(report.get("clicked_page") or 1),
                box=box,  # Existing field uses its own widget, but pyHanko still expects a box.
                field_name=field_name,
                reason=reason or None,
                location=location or None,
                contact_info=str(report.get("contact_info") or "").strip() or None,
                tsa_url=_get_tsa_url(),
                enable_ltv=_get_ltv_setting(),
            ),
            status_message="Đang ký ô ký đã chọn bằng USB...",
        )
        if not ok:
            exc_type_name, exc_message, tb_text = error or ("RuntimeError", "Ký số thất bại.", "")
            raise RuntimeError(f"{exc_type_name}: {exc_message}\n{tb_text}".strip())

        with open(actual_output_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            os.remove(actual_output_path)
            raise RuntimeError("File ký xong không hợp lệ (thiếu %PDF header).")

        if in_place_output:
            replace_document_with_staged(
                window,
                actual_output_path,
                target_path=window.current_path,
                page=int(report.get("clicked_page") or 1),
            )
            final_output_path = window.current_path
        else:
            final_output_path = output_path

        validation = validate_signed_pdf_status(final_output_path, field_name=field_name)
        validation_line = str(validation.get("message") or "")
        QMessageBox.information(
            window,
            "Ký ô ký thành công",
            "Ký ô ký thành công!\n\n"
            f"Trạng thái: {validation_line}\n\n"
            f"File đã được cập nhật tại:\n{final_output_path}",
        )
    except Exception:
        traceback.print_exc()
        msg = QMessageBox(window)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Lỗi ký ô ký")
        msg.setText("Ký ô ký thất bại!")
        msg.setDetailedText(traceback.format_exc())
        msg.exec()


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


def _pick_signature_placement(window, *, sig_image_url: str = "", sig_text_html: str = ""):
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
        prompt.accept()
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
        prompt.accept()
        if loop.isRunning():
            loop.quit()

    def _cancel_pick():
        result.clear()
        prompt.reject()
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
        pick_script = _make_pick_script(sig_image_url=sig_image_url, sig_text_html=sig_text_html)
        web_view.page().runJavaScript(pick_script)
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
        output_path = make_staged_pdf_path(window.current_path, prefix=".3t_sigfields_", suffix=".pdf")
        with open(window.current_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f, strict=False)
            try:
                used_names: set[str] = {
                    str(name)
                    for name, _value, _ref in fields.enumerate_sig_fields(writer)
                    if name
                }
            except Exception:
                used_names: set[str] = set()

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

        replace_document_with_staged(
            window,
            output_path,
            target_path=window.current_path,
            page=placements[-1]["page_number"],
        )
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
    _pfx_stamp_html = _build_stamp_preview_html(
        "(Người ký sẽ xác định)",
        signed_at=_format_local_timestamp(),
    )
    placement = _pick_signature_placement(window, sig_text_html=_pfx_stamp_html)
    if not placement or "box" not in placement or "page_number" not in placement:
        _cleanup_signature_preview(window)
        return
    _set_signature_preview(window, placement, sig_text_html=_pfx_stamp_html)
    if not _confirm_signature_selection(window):
        _cleanup_signature_preview(window)
        return

    pfx_path, _ = QFileDialog.getOpenFileName(
        window,
        "Chọn file chứng thư ký số",
        "",
        "PKCS#12 Files (*.p12 *.pfx);;All Files (*)",
    )
    if not pfx_path:
        _cleanup_signature_preview(window)
        return

    pin, ok = QInputDialog.getText(
        window,
        "Nhập mật khẩu chứng thư",
        "Mật khẩu file PFX/P12:",
        QLineEdit.EchoMode.Password,
    )
    if not ok:
        _cleanup_signature_preview(window)
        return

    identity_dialog = SignatureIdentityDialog(
        window,
        default_signer_name=os.path.splitext(os.path.basename(pfx_path))[0],
    )
    if identity_dialog.exec() != QDialog.DialogCode.Accepted:
        _cleanup_signature_preview(window)
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
        _cleanup_signature_preview(window)
        return

    in_place_output = os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(window.current_path))
    actual_output_path = (
        make_staged_pdf_path(window.current_path, prefix=".3t_pfx_signed_", suffix=".pdf")
        if in_place_output
        else output_path
    )

    try:
        ok, error = _run_signing_task(
            window,
            lambda: asyncio.run(
                sign_pdf_with_pkcs12(
                    pfx_path,
                    pin,
                    window.current_path,
                    actual_output_path,
                    signer_name=signer_name,
                    page_number=placement["page_number"],
                    box=placement["box"],
                    enable_ltv=_get_ltv_setting(),
                )
            ),
            status_message="Đang ký tài liệu bằng file chứng thư…",
        )
        if not ok:
            exc_type_name, exc_message, tb_text = error or ("RuntimeError", "Ký số thất bại.", "")
            raise RuntimeError(f"{exc_type_name}: {exc_message}\n{tb_text}".strip())

        with open(actual_output_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            os.remove(actual_output_path)
            raise RuntimeError(
                "File ký xong không hợp lệ (thiếu %PDF header).\n"
                "Vui lòng thử lại."
            )

        final_output_path = output_path
        if in_place_output:
            replace_document_with_staged(
                window,
                actual_output_path,
                target_path=window.current_path,
                page=placement["page_number"],
            )
            final_output_path = window.current_path

        validation = validate_signed_pdf_status(final_output_path)
        validation_line = str(validation.get("message") or "")

        if in_place_output:
            QMessageBox.information(
                window,
                "Ký từ file chứng thư thành công",
                "Ký từ file chứng thư thành công!\n\n"
                f"Trạng thái: {validation_line}\n\n"
                f"File đã được cập nhật tại:\n{final_output_path}",
            )
        else:
            reply = QMessageBox.question(
                window,
                "Ký từ file chứng thư thành công",
                "Ký từ file chứng thư thành công!\n\n"
                f"Trạng thái: {validation_line}\n\n"
                f"File lưu tại:\n{final_output_path}\n\n"
                "Mở file đã ký ngay?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                _refresh_document_view(window, final_output_path, page_number=placement["page_number"])

    except Exception:
        traceback.print_exc()
        msg = QMessageBox(window)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Lỗi ký từ file chứng thư")
        msg.setText("Ký từ file chứng thư thất bại!")
        msg.setDetailedText(traceback.format_exc())
        msg.exec()
    finally:
        _cleanup_signature_preview(window)


@require_document(show_message=True)
def sign_document(window):
    global _cached_usb_pin
    signing_provider = get_signing_provider()
    signer_info = _choose_signing_token(
        window,
        signing_provider,
        title="Chọn USB ký số để ký tài liệu",
        required=True,
    )
    if not signer_info:
        return

    _token_stamp_html = _build_stamp_preview_html(
        _token_display_name(signer_info),
        tax_code=_token_text(signer_info, "tax_code"),
        issuer_name=_token_text(signer_info, "issuer_name"),
        token_serial=_token_text(signer_info, "serial"),
        cert_serial=_token_text(signer_info, "cert_serial"),
        signed_at=_format_local_timestamp(),
    )
    placement = _pick_signature_placement(window, sig_text_html=_token_stamp_html)
    if not placement or "box" not in placement or "page_number" not in placement:
        _cleanup_signature_preview(window)
        return
    _set_signature_preview(window, placement, sig_text_html=_token_stamp_html)
    if not _confirm_signature_selection(window):
        _cleanup_signature_preview(window)
        return

    default_signer_name = signer_info.signer_name if signer_info else ""

    identity_dialog = SignatureIdentityDialog(
        window,
        default_signer_name=default_signer_name,
    )
    if identity_dialog.exec() != QDialog.DialogCode.Accepted:
        _cleanup_signature_preview(window)
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
        _cleanup_signature_preview(window)
        return

    pin = _cached_usb_pin
    if not pin:
        pin, ok = QInputDialog.getText(
            window, "Nhập mã PIN", "PIN của USB ký số:",
            QLineEdit.EchoMode.Password
        )
        if not ok or not pin:
            _cleanup_signature_preview(window)
            return
    _cached_usb_pin = pin

    in_place_output = os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(window.current_path))
    actual_output_path = (
        make_staged_pdf_path(window.current_path, prefix=".3t_signed_", suffix=".pdf")
        if in_place_output
        else output_path
    )

    try:
        ok, error = _run_usb_signing_task(
            window,
            lambda: _run_usb_signing_subprocess(
                signer_info,
                window.current_path,
                actual_output_path,
                pin,
                signer_name=signer_name,
                page_number=placement["page_number"],
                box=placement["box"],
                tsa_url=_get_tsa_url(),
                enable_ltv=_get_ltv_setting(),
            ),
            status_message="Đang ký số tài liệu…",
        )
        if not ok:
            exc_type_name, exc_message, tb_text = error or ("RuntimeError", "Ký số thất bại.", "")
            raise RuntimeError(f"{exc_type_name}: {exc_message}\n{tb_text}".strip())

        with open(actual_output_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            os.remove(actual_output_path)
            raise RuntimeError(
                "File ký xong không hợp lệ (thiếu %PDF header).\n"
                "Vui lòng thử lại."
            )

        final_output_path = output_path
        if in_place_output:
            replace_document_with_staged(
                window,
                actual_output_path,
                target_path=window.current_path,
                page=placement["page_number"],
            )
            final_output_path = window.current_path

        validation = validate_signed_pdf_status(final_output_path)
        validation_line = str(validation.get("message") or "")

        if in_place_output:
            QMessageBox.information(
                window,
                "Ký số thành công",
                "Ký số thành công!\n\n"
                f"Trạng thái: {validation_line}\n\n"
                f"File đã được cập nhật tại:\n{final_output_path}",
            )
        else:
            reply = QMessageBox.question(
                window,
                "Ký số thành công",
                "Ký số thành công!\n\n"
                f"Trạng thái: {validation_line}\n\n"
                f"File lưu tại:\n{final_output_path}\n\n"
                "Mở file đã ký ngay?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                _refresh_document_view(window, final_output_path, page_number=placement["page_number"])

    except Exception as exc:
        exc_type_name = type(exc).__name__
        exc_message = str(exc)
        if exc_type_name == "RuntimeError":
            first_line = exc_message.splitlines()[0]
            if ":" in first_line:
                maybe_type, _, maybe_message = first_line.partition(":")
                if maybe_type in {"PinIncorrect", "PinLocked"}:
                    exc_type_name = maybe_type
                    exc_message = maybe_message.strip()

        if exc_type_name == "PinIncorrect" or "PinIncorrect" in str(type(exc)):
            _cached_usb_pin = ""
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
        _cleanup_signature_preview(window)


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


@require_document(show_message=True)
def sign_handwritten(window):
    """Draw or import a signature image and place it on the current PDF."""
    import shutil
    import uuid
    import os as _os

    from app.signature_pad import SignaturePadDialog, SignatureTemplateManagerDialog

    source, ok = QInputDialog.getItem(
        window,
        "Chọn kiểu ký",
        "Nguồn chữ ký:",
        ["Vẽ tay", "Nhập mã mẫu", "Chọn từ danh sách", "Quản lý mẫu chữ ký", "Chọn ảnh chữ ký", "Chọn con dấu PNG"],
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
            manager = SignatureTemplateManagerDialog(window)
            if manager.exec() != QDialog.DialogCode.Accepted or not manager.selected_path:
                return
            sig_img_path = manager.selected_path
        else:
            labels = ["+ Quản lý / thêm / sửa / xóa mẫu..."] + [item["label"] for item in templates]
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
            if chosen == labels[0]:
                manager = SignatureTemplateManagerDialog(window)
                if manager.exec() != QDialog.DialogCode.Accepted or not manager.selected_path:
                    return
                sig_img_path = manager.selected_path
            else:
                chosen_item = next((item for item in templates if item["label"] == chosen), None)
                if not chosen_item:
                    return
                sig_img_path = chosen_item["path"]
    elif source == "Quản lý mẫu chữ ký":
        manager = SignatureTemplateManagerDialog(window)
        if manager.exec() != QDialog.DialogCode.Accepted or not manager.selected_path:
            return
        sig_img_path = manager.selected_path
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

    # Convert signature image to data URL early for pick-phase preview
    _sig_data_url = ""
    if sig_img_path and _os.path.isfile(sig_img_path):
        try:
            import base64
            with open(sig_img_path, "rb") as _f:
                _b64 = base64.b64encode(_f.read()).decode("ascii")
            _ext = _os.path.splitext(sig_img_path)[1].lower()
            _mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "bmp": "image/bmp", "webp": "image/webp"}.get(_ext.lstrip("."), "image/png")
            _sig_data_url = f"data:{_mime};base64,{_b64}"
        except Exception:
            pass

    placement = _pick_signature_placement(window, sig_image_url=_sig_data_url)
    # Nếu huỷ click chọn vị trí thì placement=None, dùng vị trí mặc định
    # (không bắt buộc phải click — có thể chọn qua spinbox)
    if not placement or "box" not in placement or "page_number" not in placement:
        _cleanup_signature_preview(window)
        return
    _set_signature_preview(window, placement, sig_image_url=_sig_data_url)
    if not _confirm_signature_selection(window):
        _cleanup_signature_preview(window)
        return

    page_no = placement["page_number"]
    box = placement["box"]

    try:
        from packages.pdf_engine import get_pdf_engine

        out_path = make_staged_pdf_path(window.current_path, prefix=".3t_handwritten_", suffix=".pdf")
        get_pdf_engine().rebuild_pdf_with_ops(
            window.current_path,
            out_path,
            [{
                "type": "image",
                "page_number": page_no,
                "box": box,
                "image_path": sig_img_path,
                "rotation": 0,
            }],
        )

        replace_document_with_staged(
            window,
            out_path,
            target_path=window.current_path,
            page=page_no,
        )
        if hasattr(window, "status"):
            window.status.showMessage("Đã đặt chữ ký tay lên PDF", 3000)
    except Exception:
        import traceback
        show_warning(window, "Lỗi chèn chữ ký", traceback.format_exc())
    finally:
        _cleanup_signature_preview(window)
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

        clicked_page = int(report.get("clicked_page") or 0)
        clicked_field = str(report.get("clicked_field") or "").strip()
        if clicked_page:
            form.addRow("Vi tri da bam", QLabel(f"Trang {clicked_page}"))
        if clicked_field:
            field_value = QLabel(clicked_field)
            field_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow("Truong chu ky", field_value)

        form.addRow("Danh tính người ký", identity_value)
        form.addRow("Đã sửa đổi tài liệu", modify_value)
        form.addRow("Trạng thái chứng thư", cert_value)
        form.addRow("Nhà cung cấp", issuer_value)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._detail_btn = QPushButton("Thuộc tính")
        buttons.addButton(self._detail_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._detail_btn.clicked.connect(self._show_details)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _show_details(self):
        _show_signature_report_vn(self, "Chi tiết chữ ký số", self._report, path=self._path)


class SignatureStatusDialog(QDialog):
    def __init__(self, parent, report: dict, *, path: str | None = None):
        super().__init__(parent)
        self._report = report
        self._path = path
        self.setWindowTitle("Chữ ký số")
        self.setModal(True)
        self.setMinimumWidth(520)

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
        title = QLabel("Hợp lệ chữ ký" if report.get("ok") else "Chữ ký không hợp lệ")
        title.setStyleSheet(
            "font-size: 17px; font-weight: 700; color: %s;"
            % ("#168038" if report.get("ok") else "#c23b22")
        )
        title_wrap.addWidget(title)
        field_signed = bool(report.get("field_signed"))

        signer = str(
            report.get("display_signer")
            or report.get("signer_reported_name")
            or report.get("subject_name")
            or "Không rõ"
        )
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
        if not bool(report.get("field_signed")):
            if not report.get("trusted"):
                identity_value.setText("Chưa ký")
            if not str(report.get("certificate_status") or "").strip():
                cert_value.setText("Không có chứng thư")
            if not str(report.get("issuer_name") or "").strip():
                issuer_value.setText("Không có chứng thư")
        signer_value = QLabel(signer)
        reason_value = QLabel(str(report.get("reason") or "Không có"))
        when_value = QLabel(str(report.get("signing_time") or "Không rõ"))
        location_value = QLabel(str(report.get("location") or "Không có"))
        contact_value = QLabel(str(report.get("contact_info") or "Không có"))
        serial_value = QLabel(str(report.get("serial_hex") or "Không rõ"))
        valid_range_value = QLabel(
            f"{report.get('valid_from') or 'Không rõ'} - {report.get('valid_to') or 'Không rõ'}"
        )

        for widget in (
            identity_value,
            modify_value,
            cert_value,
            issuer_value,
            signer_value,
            reason_value,
            when_value,
            location_value,
            contact_value,
            serial_value,
            valid_range_value,
        ):
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            widget.setWordWrap(True)

        clicked_page = int(report.get("clicked_page") or 0)
        clicked_field = str(report.get("clicked_field") or report.get("selected_field_name") or "").strip()
        if clicked_page:
            form.addRow("Vị trí đã bấm", QLabel(f"Trang {clicked_page}"))
        if clicked_field:
            field_value = QLabel(clicked_field)
            field_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            field_value.setWordWrap(True)
            form.addRow("Trường chữ ký", field_value)

        form.addRow("Người ký", signer_value)
        form.addRow("Lý do", reason_value)
        form.addRow("Ngày ký", when_value)
        form.addRow("Địa điểm", location_value)
        form.addRow("Liên hệ", contact_value)
        form.addRow("Danh tính người ký", identity_value)
        form.addRow("Đã sửa đổi tài liệu", modify_value)
        form.addRow("Trạng thái chứng thư", cert_value)
        form.addRow("Nhà cung cấp", issuer_value)
        form.addRow("Serial chứng thư", serial_value)
        form.addRow("Hiệu lực chứng thư", valid_range_value)
        root.addLayout(form)

        summary_lines = report.get("validation_summary_lines") or []
        if summary_lines:
            validation_box = QLabel("\n".join(f"- {line}" for line in summary_lines))
            validation_box.setWordWrap(True)
            validation_box.setStyleSheet(
                "background:#fcfcfe; border:1px solid #d9e0ea; border-radius:8px; "
                "padding:8px 10px; color:#223; font-size:11px;"
            )
            root.addWidget(validation_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._detail_btn = QPushButton("Thuộc tính")
        self._cert_btn = QPushButton("Chứng thư")
        buttons.addButton(self._detail_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._cert_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self._detail_btn.clicked.connect(self._show_details)
        self._cert_btn.clicked.connect(self._show_certificate_details)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _show_details(self):
        _show_signature_report_vn(self, "Chi tiết chữ ký số", self._report, path=self._path)

    def _show_certificate_details(self):
        if not bool(self._report.get("field_signed")):
            lines = [
                f"Trường chữ ký: {self._report.get('selected_field_name') or self._report.get('clicked_field') or 'Không rõ'}",
                f"Vị trí: Trang {self._report.get('clicked_page') or 'Không rõ'}",
                "Trạng thái: Ô ký chưa được ký số.",
            ]
            QMessageBox.information(self, "Chứng thư số", "\n".join(lines))
            return
        lines = [
            f"Người ký: {self._report.get('display_signer') or self._report.get('subject_name') or 'Không rõ'}",
            f"Nhà cung cấp: {self._report.get('issuer_name') or 'Không rõ'}",
            f"Serial: {self._report.get('serial_hex') or 'Không rõ'}",
            f"Hiệu lực: {self._report.get('valid_from') or 'Không rõ'} - {self._report.get('valid_to') or 'Không rõ'}",
            f"Trạng thái chứng thư: {self._report.get('certificate_status') or 'Không rõ'}",
        ]
        QMessageBox.information(self, "Chứng thư số", "\n".join(lines))


def verify_signed_document(window):
    """Check the currently opened PDF signature validity."""
    default_path = getattr(window, "current_path", "") or ""
    if not default_path or not os.path.exists(default_path):
        show_warning(window, "Chưa có tệp", "Vui lòng mở file PDF trước khi kiểm tra chữ ký.")
        return

    report = validate_signed_pdf_status(default_path)
    dlg = SignatureStatusDialog(window, report, path=default_path)
    dlg.exec()

def _run_usb_signing_batch_subprocess(
    token_info,
    jobs: list[dict],
    pin: str,
    *,
    tsa_url: str | None = None,
    enable_ltv: bool = False,
) -> None:
    payload = {
        "token": _token_info_payload(token_info),
        "pin": pin,
        "jobs": jobs,
        "tsa_url": tsa_url or "",
        "enable_ltv": enable_ltv,
    }

    payload_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
    payload_path = payload_file.name
    try:
        json.dump(payload, payload_file, ensure_ascii=False)
        payload_file.close()

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--usb-sign-worker", payload_path]
        else:
            cmd = [
                sys.executable,
                "-m",
                "packages.signing.usb_worker",
                payload_path,
            ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            err_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Tien trinh ky so that bai (Ma loi: {result.returncode}):\n{err_msg}")

        try:
            out_data = json.loads(result.stdout)
        except Exception:
            raise RuntimeError(f"Khong the phan tich ket qua tu tien trinh ky so:\n{result.stdout}")

        if not out_data.get("ok"):
            err_type = out_data.get("error_type", "Error")
            err_msg = out_data.get("error_message", "Unknown error")
            raise RuntimeError(f"{err_type}: {err_msg}")
    finally:
        try:
            os.remove(payload_path)
        except Exception:
            pass


def sign_document_batch(window):
    from app.license_dialog import require_plan
    if not require_plan(window, "Ký tài liệu hàng loạt (Batch Sign)", ["personal", "enterprise"]):
        return

    if not window.current_path:
        from packages.qt_compat.QtWidgets import QMessageBox
        QMessageBox.warning(window, "Lỗi", "Vui lòng mở một tài liệu mẫu trước để làm căn cứ chọn vị trí ký.")
        return

    global _cached_usb_pin
    signing_provider = get_signing_provider()
    signer_info = _choose_signing_token(
        window,
        signing_provider,
        title="Chọn USB ký số để ký hàng loạt",
        required=True,
    )
    if not signer_info:
        return

    _token_stamp_html = _build_stamp_preview_html(
        _token_display_name(signer_info),
        tax_code=_token_text(signer_info, "tax_code"),
        issuer_name=_token_text(signer_info, "issuer_name"),
        token_serial=_token_text(signer_info, "serial"),
        cert_serial=_token_text(signer_info, "cert_serial"),
        signed_at=_format_local_timestamp(),
    )
    
    from packages.qt_compat.QtWidgets import QMessageBox
    QMessageBox.information(window, "Hướng dẫn", "Hãy chọn vị trí chữ ký trên tài liệu ĐANG MỞ. Vị trí này sẽ được áp dụng cho toàn bộ các file trong thư mục.")

    placement = _pick_signature_placement(window, sig_text_html=_token_stamp_html)
    if not placement or "box" not in placement or "page_number" not in placement:
        _cleanup_signature_preview(window)
        return
    _set_signature_preview(window, placement, sig_text_html=_token_stamp_html)
    if not _confirm_signature_selection(window):
        _cleanup_signature_preview(window)
        return

    default_signer_name = signer_info.signer_name if signer_info else ""
    identity_dialog = SignatureIdentityDialog(
        window,
        default_signer_name=default_signer_name,
    )
    if identity_dialog.exec() != QDialog.DialogCode.Accepted:
        _cleanup_signature_preview(window)
        return
    signer_name = identity_dialog.signer_name()

    from packages.qt_compat.QtWidgets import QFileDialog, QInputDialog, QLineEdit
    input_dir = QFileDialog.getExistingDirectory(window, "Chọn thư mục chứa các file PDF CẦN KÝ", window.current_path)
    if not input_dir:
        _cleanup_signature_preview(window)
        return

    output_dir = QFileDialog.getExistingDirectory(window, "Chọn thư mục ĐÍCH để lưu các file ĐÃ KÝ", input_dir)
    if not output_dir:
        _cleanup_signature_preview(window)
        return

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        QMessageBox.warning(window, "Lỗi", "Không tìm thấy file PDF nào trong thư mục nguồn.")
        _cleanup_signature_preview(window)
        return

    pin = _cached_usb_pin
    if not pin:
        pin, ok = QInputDialog.getText(
            window, "Nhập mã PIN", f"PIN của USB ký số (Sẽ áp dụng cho {len(pdf_files)} file):",
            QLineEdit.EchoMode.Password
        )
        if not ok or not pin:
            _cleanup_signature_preview(window)
            return
    _cached_usb_pin = pin

    jobs = []
    for f in pdf_files:
        in_path = os.path.join(input_dir, f)
        base, ext = os.path.splitext(f)
        out_path = os.path.join(output_dir, f"{base}_signed{ext}")
        jobs.append({
            "input_path": in_path,
            "output_path": out_path,
            "signer_name": signer_name,
            "page_number": placement["page_number"],
            "box": placement["box"]
        })

    tsa_url = _get_tsa_url()

    try:
        ok, error = _run_usb_signing_task(
            window,
            lambda: _run_usb_signing_batch_subprocess(
                signer_info,
                jobs,
                pin,
                tsa_url=tsa_url,
                enable_ltv=_get_ltv_setting(),
            ),
            status_message=f"Đang ký hàng loạt {len(pdf_files)} tài liệu...",
        )
        if not ok:
            exc_type_name, exc_message, tb_text = error or ("RuntimeError", "Ký số thất bại.", "")
            raise RuntimeError(f"{exc_type_name}: {exc_message}\n{tb_text}".strip())

        QMessageBox.information(
            window,
            "Hoàn tất",
            f"Ký số hàng loạt thành công {len(pdf_files)} tài liệu!\n\n"
            f"Thư mục lưu: {output_dir}",
        )
    except Exception as e:
        QMessageBox.critical(window, "Lỗi Ký Lô", f"Lỗi trong quá trình ký hàng loạt:\n{e}")
    finally:
        _cleanup_signature_preview(window)
