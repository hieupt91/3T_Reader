from __future__ import annotations

import re
import threading

_KEY_RE = re.compile(r'^3TR-[BPE]-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QApplication,
)


# ── stylesheet ──────────────────────────────────────────────────────────────

_STYLE = """
QDialog {
    background: #16162A;
}
QLabel#title {
    color: #E8EEFF;
    font-size: 18px;
    font-weight: 700;
}
QLabel#subtitle {
    color: #8080B0;
    font-size: 12px;
}
QLabel#field_label {
    color: #B0B8E0;
    font-size: 12px;
    font-weight: 600;
}
QLabel#trial_info {
    color: #f59e0b;
    font-size: 12px;
    font-weight: 600;
    background: rgba(245,158,11,0.12);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 6px;
    padding: 6px 12px;
}
QLabel#trial_expired {
    color: #E05050;
    font-size: 12px;
    font-weight: 600;
    background: rgba(224,80,80,0.1);
    border: 1px solid rgba(224,80,80,0.3);
    border-radius: 6px;
    padding: 6px 12px;
}
QLabel#or_label {
    color: #3A3A60;
    font-size: 11px;
    font-weight: 600;
}
QLineEdit {
    background: #1E1E38;
    color: #E8EEFF;
    border: 1px solid #3A3A60;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    font-family: monospace;
    letter-spacing: 1px;
}
QLineEdit:focus {
    border-color: #FF6600;
}
QPushButton#btn_activate {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #FF7700, stop:1 #FF4400);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#btn_activate:hover { background: #FF9900; }
QPushButton#btn_activate:pressed { background: #DD4400; }
QPushButton#btn_activate:disabled { background: #553322; color: #886655; }
QPushButton#btn_trial {
    background: transparent;
    color: #f59e0b;
    border: 1px solid rgba(245,158,11,0.5);
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#btn_trial:hover {
    background: rgba(245,158,11,0.12);
    border-color: #f59e0b;
}
QPushButton#btn_quit {
    background: transparent;
    color: #6060A0;
    border: 1px solid #3A3A60;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
}
QPushButton#btn_quit:hover { color: #E05050; border-color: #E05050; }
QLabel#status_ok  { color: #4fc080; font-size: 12px; }
QLabel#status_err { color: #E05050; font-size: 12px; }
QLabel#status_info { color: #8080B0; font-size: 12px; }
QFrame#divider { background: #2A2A4A; }
QFrame#or_line { background: #2A2A4A; }
"""


# ── dialog ───────────────────────────────────────────────────────────────────

class LicenseActivationDialog(QDialog):
    """
    Dialog kích hoạt license.
    - Nếu trial chưa bắt đầu: hiện nút "Dùng thử 30 ngày"
    - Nếu đang trong trial: hiện số ngày còn lại
    - Nếu trial hết hạn: chỉ hiện ô nhập key
    """
    _sig_ok  = Signal(object)  # ActivationResult
    _sig_err = Signal(str)     # error message

    def __init__(self, parent=None, show_trial_option: bool = True, quit_on_close: bool = False, current_status=None):
        super().__init__(parent)
        self.setWindowTitle("Kích hoạt / Nâng cấp 3T Reader")
        self.setModal(True)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )
        self._activated = False
        self._activation_result = None
        self._trial_chosen = False
        self._show_trial_option = show_trial_option
        self._quit_on_close = quit_on_close
        self._current_status = current_status
        self._trial_info = self._load_trial_info()
        self._sig_ok.connect(self._finish_ok)
        self._sig_err.connect(self._finish_err)
        self._build_ui()

    def _load_trial_info(self) -> dict:
        try:
            from packages.license_client.trial import get_or_init_trial, has_trial_started
            started = has_trial_started()
            if not started:
                return {"started": False, "expired": False, "days_remaining": 30}
            info = get_or_init_trial()
            return {"started": True, **info}
        except Exception:
            return {"started": False, "expired": False, "days_remaining": 30}

    def _build_ui(self):
        ti = self._trial_info
        # Tính chiều cao dialog
        extra_h = 0
        if self._show_trial_option:
            if ti.get("started") and not ti.get("expired"):
                extra_h = 36  # trial info badge
            elif not ti.get("started"):
                extra_h = 80  # nút dùng thử + divider

        self.setFixedSize(480, 340 + extra_h)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # Header
        title = QLabel("Kích hoạt / Nâng cấp 3T Reader")
        title.setObjectName("title")
        root.addWidget(title)

        root.addSpacing(4)
        if self._current_status and self._current_status.active:
            plan_names = {"free": "Miễn Phí", "personal": "Cá Nhân", "enterprise": "Doanh Nghiệp", "3tr-b": "Cơ Bản", "3tr-p": "Cá Nhân", "3tr-e": "Doanh Nghiệp"}
            code = (self._current_status.plan_code or "free").lower().strip()
            plan_label = plan_names.get(code, code.upper())
            if code in ["enterprise", "3tr-e"]:
                sub = QLabel(f"Bạn đang dùng gói: {plan_label} (Cao cấp nhất).\nNhập mã để Gia hạn thời gian sử dụng.")
            else:
                sub = QLabel(f"Bạn đang dùng gói: {plan_label}.\nNhập mã mới để Nâng cấp hoặc Gia hạn.")
        else:
            sub = QLabel("Nhập license key để sử dụng đầy đủ tính năng.")
        sub.setObjectName("subtitle")
        root.addWidget(sub)

        # Trial info banner (nếu đang trong trial)
        if self._show_trial_option and ti.get("started") and not ti.get("expired"):
            root.addSpacing(12)
            days = ti.get("days_remaining", 0)
            trial_lbl = QLabel(f"🕐  Bạn đang trong thời gian dùng thử — còn {days} ngày")
            trial_lbl.setObjectName("trial_info")
            root.addWidget(trial_lbl)

        root.addSpacing(20)

        # License key field
        lbl_key = QLabel("License Key")
        lbl_key.setObjectName("field_label")
        root.addWidget(lbl_key)
        root.addSpacing(6)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("3TR-P-XXXX-XXXX-XXXX")
        self._key_input.setMaxLength(64)
        self._key_input.textChanged.connect(self._on_input_changed)
        root.addWidget(self._key_input)

        root.addSpacing(14)

        # Status label
        self._status = QLabel("")
        self._status.setObjectName("status_info")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # Phần "— Hoặc —" + nút Dùng thử (chỉ khi trial chưa bắt đầu)
        if self._show_trial_option and not ti.get("started"):
            root.addSpacing(14)
            # Đường kẻ ngang "— hoặc —"
            or_row = QHBoxLayout()
            or_row.setSpacing(8)
            line1 = QFrame(); line1.setObjectName("or_line"); line1.setFixedHeight(1)
            line2 = QFrame(); line2.setObjectName("or_line"); line2.setFixedHeight(1)
            or_lbl = QLabel("hoặc")
            or_lbl.setObjectName("or_label")
            or_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            or_row.addWidget(line1, 1)
            or_row.addWidget(or_lbl)
            or_row.addWidget(line2, 1)
            root.addLayout(or_row)
            root.addSpacing(10)

            self._btn_trial = QPushButton("🕐  Dùng thử miễn phí 30 ngày")
            self._btn_trial.setObjectName("btn_trial")
            self._btn_trial.clicked.connect(self._on_trial)
            root.addWidget(self._btn_trial)

        root.addStretch()

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)
        root.addSpacing(16)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        quit_label = "Thoát ứng dụng" if self._quit_on_close else "Để sau"
        self._btn_quit = QPushButton(quit_label)
        self._btn_quit.setObjectName("btn_quit")
        self._btn_quit.clicked.connect(self._on_quit)

        self._btn_activate = QPushButton("Kích hoạt")
        self._btn_activate.setObjectName("btn_activate")
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._on_activate)
        self._key_input.returnPressed.connect(self._btn_activate.click)

        btn_row.addWidget(self._btn_quit)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_activate)
        root.addLayout(btn_row)

    # ── slots ────────────────────────────────────────────────────────────────

    def _on_input_changed(self, text: str):
        key = text.strip().upper()
        valid = bool(_KEY_RE.match(key))
        self._btn_activate.setEnabled(valid)
        if key and not valid:
            self._set_status("Định dạng key không đúng. VD: 3TR-P-XXXX-XXXX-XXXX", "err")
        else:
            self._set_status("", "info")

    def _on_trial(self):
        try:
            from packages.license_client.trial import start_trial
            start_trial()
        except Exception:
            pass
        self._trial_chosen = True
        self.accept()

    def _on_activate(self):
        key = self._key_input.text().strip().upper()
        if not key:
            return

        self._btn_activate.setEnabled(False)
        self._btn_quit.setEnabled(False)
        if hasattr(self, "_btn_trial"):
            self._btn_trial.setEnabled(False)
        self._set_status("Đang kích hoạt…", "info")

        def _do():
            try:
                from packages.license_client import get_license_client
                from packages.license_client.fingerprint import get_device_fingerprint
                client = get_license_client()
                fp = get_device_fingerprint()
                result = client.activate(key, "", fp)
                if result.status.active:
                    self._sig_ok.emit(result)
                else:
                    self._sig_err.emit("Kích hoạt thất bại.")
            except RuntimeError as e:
                self._sig_err.emit(str(e))
            except Exception as e:
                self._sig_err.emit(f"Lỗi kết nối: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def _finish_ok(self, result):
        exp = result.status.expires_at
        exp_str = exp.strftime("%d/%m/%Y") if exp else "không xác định"
        self._set_status(f"✓  Kích hoạt thành công! Hết hạn: {exp_str}", "ok")
        self._activated = True
        self._activation_result = result
        QTimer.singleShot(700, self.accept)

    def _finish_err(self, msg: str):
        self._set_status(msg, "err")
        self._btn_activate.setEnabled(True)
        self._btn_quit.setEnabled(True)
        if hasattr(self, "_btn_trial"):
            self._btn_trial.setEnabled(True)

    def _on_quit(self):
        if self._quit_on_close:
            QApplication.quit()
        else:
            self.reject()

    def _set_status(self, text: str, level: str):
        self._status.setText(text)
        obj = {"ok": "status_ok", "err": "status_err"}.get(level, "status_info")
        self._status.setObjectName(obj)
        self._status.setStyleSheet(
            {"ok": "color:#4fc080;", "err": "color:#E05050;"}.get(level, "color:#8080B0;")
        )

    def was_activated(self) -> bool:
        return self._activated

    def was_trial_chosen(self) -> bool:
        return self._trial_chosen

    def get_activation_result(self):
        return self._activation_result


# ── public helpers ────────────────────────────────────────────────────────────

def check_license_on_startup(window) -> bool:
    """
    Kiểm tra license khi khởi động. (Freemium Model)
    Nếu không có license hợp lệ -> Chạy ở chế độ FREE.
    """
    from app.config import VPS_LICENSE_BASE_URL
    if not VPS_LICENSE_BASE_URL:
        # We don't bypass anymore. We just treat it as free mode if there's no URL configured
        pass

    from packages.license_client import get_license_client
    client = get_license_client()
    status = client.validate_cached()

    if status.active:
        _show_license_badge(window, status.plan_code or "free", status.expires_at)
        _start_heartbeat(window, client)
    else:
        _show_license_badge(window, "free", None)

    return True

def get_current_plan() -> str:
    from packages.license_client import get_license_client
    status = get_license_client().validate_cached()
    if status.active:
        plan_code = (status.plan_code or "free").lower().strip()
        if plan_code.startswith("3tr-e") or "enterprise" in plan_code or "doanh nghiệp" in plan_code:
            return "enterprise"
        if plan_code.startswith("3tr-p") or "personal" in plan_code or "cá nhân" in plan_code:
            return "personal"
        if plan_code.startswith("3tr-b") or "basic" in plan_code or "cơ bản" in plan_code:
            return "basic"
        return plan_code
    return "free"

def require_plan(window, feature_name: str, allowed_plans: list[str]) -> bool:
    plan = get_current_plan().lower().strip()
    allowed_plans_lower = [p.lower().strip() for p in allowed_plans]
    if plan in allowed_plans_lower or plan == "enterprise":
        return True
        
    from packages.qt_compat.QtWidgets import QMessageBox
    if "personal" in allowed_plans:
        req = "Cá Nhân"
    else:
        req = "Doanh Nghiệp"
        
    reply = QMessageBox.question(
        window,
        "Nâng cấp tính năng",
        f"Tính năng {feature_name} yêu cầu gói {req} hoặc cao hơn.\n\n"
        "Bạn có muốn nhập mã Nâng cấp Bản quyền ngay bây giờ không?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes
    )
    if reply == QMessageBox.StandardButton.Yes:
        open_license_dialog(window)
    return False


def open_license_dialog(window):
    """Mở dialog từ menu License — dùng khi app đang chạy."""
    from packages.license_client import get_license_client
    status = get_license_client().validate_cached()

    dlg = LicenseActivationDialog(window, show_trial_option=not status.active, current_status=status)
    dlg.exec()
    if dlg.was_activated():
        r = dlg.get_activation_result()
        _remove_trial_banner(window)
        _show_license_badge(window, r.status.plan_code or "" if r else "", r.status.expires_at if r else None)
        _start_heartbeat(window, get_license_client())


def _show_license_badge(window, plan_code: str = "", expires_at=None):
    """Hiển thị badge 'Đã kích hoạt' ở statusbar."""
    from packages.qt_compat.QtWidgets import QLabel
    from packages.qt_compat.QtCore import Qt

    _remove_trial_banner(window)
    _remove_license_badge(window)

    plan_names = {"free": "Miễn Phí", "personal": "Cá Nhân", "enterprise": "Doanh Nghiệp", "3TR-B": "Cơ Bản", "3TR-P": "Cá Nhân", "3TR-E": "Doanh Nghiệp"}
    plan_label = plan_names.get(plan_code, plan_names.get(plan_code[:5] if plan_code else "", ""))
    plan_str = f" — {plan_label}" if plan_label else ""

    exp_str = ""
    if expires_at:
        try:
            exp_str = f"  ·  HH: {expires_at.strftime('%d/%m/%Y')}"
        except Exception:
            pass

    text = f"✓  Đã kích hoạt{plan_str}{exp_str}"

    class _LicenseBadge(QLabel):
        def mousePressEvent(self, _ev):
            open_license_dialog(window)

    lbl = _LicenseBadge(text)
    lbl.setObjectName("_license_badge")
    lbl.setStyleSheet(
        "color:#4fc080; font-size:11px; padding:2px 10px;"
        "background:transparent; border-radius:4px;"
    )
    lbl.setCursor(Qt.CursorShape.PointingHandCursor)
    lbl.setToolTip("License đang hoạt động — bấm để xem chi tiết")

    window.statusBar().addPermanentWidget(lbl)
    window._license_badge = lbl


def _remove_license_badge(window):
    badge = getattr(window, "_license_badge", None)
    if badge:
        window.statusBar().removeWidget(badge)
        badge.deleteLater()
        window._license_badge = None


def _show_trial_banner(window, days_remaining: int):
    """Hiển thị badge dùng thử ở statusbar."""
    from packages.qt_compat.QtWidgets import QLabel
    from packages.qt_compat.QtCore import Qt

    if days_remaining <= 5:
        color, prefix = "#E05050", "⚠️"
    elif days_remaining <= 10:
        color, prefix = "#f59e0b", "🕐"
    else:
        color, prefix = "#64a86e", "✓"

    text = f"{prefix} Dùng thử: còn {days_remaining} ngày  ·  Bấm để kích hoạt"

    class _TrialLabel(QLabel):
        def mousePressEvent(self, _ev):
            open_license_dialog(window)

    lbl = _TrialLabel(text)
    lbl.setObjectName("_trial_badge")
    lbl.setStyleSheet(
        f"color:{color}; font-size:11px; padding:2px 10px;"
        "background:transparent; border-radius:4px;"
    )
    lbl.setCursor(Qt.CursorShape.PointingHandCursor)
    lbl.setToolTip("Bấm để nhập license key và kích hoạt bản quyền")

    window.statusBar().addPermanentWidget(lbl)
    window._trial_badge = lbl


def _remove_trial_banner(window):
    badge = getattr(window, "_trial_badge", None)
    if badge:
        window.statusBar().removeWidget(badge)
        badge.deleteLater()
        window._trial_badge = None


def _start_heartbeat(window, client):
    """Gửi heartbeat mỗi 6 giờ trong background."""
    from packages.qt_compat.QtCore import QTimer
    _stop_heartbeat(window)
    timer = QTimer(window)
    timer.setInterval(6 * 3600 * 1000)  # 6h

    def _beat():
        def _worker():
            try:
                status = client.heartbeat()
                if not status.active and not getattr(window, "_closing", False):
                    QTimer.singleShot(0, lambda: _warn_expired(window))
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    timer.timeout.connect(_beat)
    timer.start()
    window._license_heartbeat_timer = timer


def _stop_heartbeat(window):
    timer = getattr(window, "_license_heartbeat_timer", None)
    if timer is None:
        return
    try:
        timer.stop()
    except Exception:
        pass
    try:
        timer.deleteLater()
    except Exception:
        pass
    window._license_heartbeat_timer = None


def _warn_expired(window):
    from app.dialogs import show_warning
    show_warning(
        window,
        "License hết hạn",
        "License đã bị thu hồi hoặc hết hạn.\n"
        "Vui lòng liên hệ 3T Company để gia hạn.",
    )
