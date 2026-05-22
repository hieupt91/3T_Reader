from __future__ import annotations

import re
import threading

_KEY_RE = re.compile(r'^3TR-[BPE]-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')

from packages.qt_compat.QtCore import Qt, QTimer
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


# ── helpers ──────────────────────────────────────────────────────────────────

def _vps_error_to_user_message(raw: str) -> str:
    """Map VPS error strings to user-friendly Vietnamese messages."""
    s = raw.lower()
    # invalid / not found key
    if any(k in s for k in ("not found", "invalid", "không tìm thấy", "not exist",
                             "không đúng", "không tồn tại", "key not", "license not")):
        return "Mã key không đúng hoặc không tồn tại.\nVui lòng kiểm tra lại key của bạn."
    # expired
    if any(k in s for k in ("expired", "hết hạn", "expir")):
        return "Mã key đã hết hạn.\nVui lòng liên hệ 3T Company để gia hạn."
    # already activated / device conflict
    if any(k in s for k in ("already activated", "đã kích hoạt", "already used",
                             "device mismatch", "khác thiết bị")):
        return "Key này đã được kích hoạt trên thiết bị khác.\nMỗi key chỉ dùng được trên 1 máy."
    # device limit
    if any(k in s for k in ("max devices", "device limit", "too many devices", "giới hạn thiết bị")):
        return "Key đã đạt giới hạn số thiết bị được phép."
    # revoked / suspended
    if any(k in s for k in ("suspended", "revoked", "blocked", "vô hiệu", "thu hồi")):
        return "Key này đã bị vô hiệu hóa.\nVui lòng liên hệ 3T Company."
    # rate limit
    if any(k in s for k in ("rate limit", "too many requests", "quá nhiều")):
        return "Quá nhiều yêu cầu. Vui lòng chờ vài phút rồi thử lại."
    return f"Kích hoạt thất bại: {raw}"


# ── dialog ───────────────────────────────────────────────────────────────────

class LicenseActivationDialog(QDialog):
    """
    Dialog kích hoạt license.
    - Nếu trial chưa bắt đầu: hiện nút "Dùng thử 30 ngày"
    - Nếu đang trong trial: hiện số ngày còn lại
    - Nếu trial hết hạn: chỉ hiện ô nhập key
    """

    def __init__(self, parent=None, show_trial_option: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Kích hoạt 3T Reader")
        self.setModal(True)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )
        self._activated = False
        self._trial_chosen = False
        self._show_trial_option = show_trial_option
        self._trial_info = self._load_trial_info()
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
        title = QLabel("Kích hoạt 3T Reader")
        title.setObjectName("title")
        root.addWidget(title)

        root.addSpacing(4)
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

        self._btn_quit = QPushButton("Thoát")
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
        self._set_status("Đang kết nối máy chủ…", "info")

        # Timeout timer — nếu sau 15s chưa có kết quả → báo lỗi
        self._activate_timeout = QTimer(self)
        self._activate_timeout.setSingleShot(True)
        self._activate_timeout.timeout.connect(
            lambda: self._finish_err(
                "Kết nối máy chủ quá lâu (>60 giây).\n"
                "Kiểm tra kết nối mạng rồi thử lại."
            )
        )
        self._activate_timeout.start(60_000)

        # Dots animation while waiting
        self._dot_count = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(500)
        def _tick():
            self._dot_count = (self._dot_count + 1) % 4
            dots = "." * self._dot_count
            self._set_status(f"Đang kích hoạt{dots}", "info")
        self._dot_timer.timeout.connect(_tick)
        self._dot_timer.start()

        def _do():
            try:
                from packages.license_client import get_license_client
                from packages.license_client.fingerprint import get_device_fingerprint
                client = get_license_client()
                fp = get_device_fingerprint()
                result = client.activate(key, "", fp)
                if result.status.active:
                    QTimer.singleShot(0, lambda: self._finish_ok(result))
                else:
                    QTimer.singleShot(0, lambda: self._finish_err(
                        "Mã key không hợp lệ hoặc đã hết hạn.\n"
                        "Vui lòng kiểm tra lại key của bạn."
                    ))
            except RuntimeError as e:
                # VPS trả về error message cụ thể
                raw = str(e).strip()
                user_msg = _vps_error_to_user_message(raw)
                QTimer.singleShot(0, lambda msg=user_msg: self._finish_err(msg))
            except Exception as e:
                err_str = str(e)
                if "timeout" in err_str.lower() or "timed out" in err_str.lower():
                    QTimer.singleShot(0, lambda: self._finish_err(
                        "Kết nối đến máy chủ bị timeout.\n"
                        "Kiểm tra mạng và thử lại."
                    ))
                elif "connect" in err_str.lower() or "network" in err_str.lower():
                    QTimer.singleShot(0, lambda: self._finish_err(
                        "Không thể kết nối máy chủ.\n"
                        "Kiểm tra kết nối internet rồi thử lại."
                    ))
                else:
                    QTimer.singleShot(0, lambda: self._finish_err(
                        f"Lỗi không xác định:\n{err_str}"
                    ))

        threading.Thread(target=_do, daemon=True).start()

    def _finish_ok(self, result):
        self._stop_loading_ui()
        exp = result.status.expires_at
        exp_str = exp.strftime("%d/%m/%Y") if exp else "không xác định"
        plan = result.status.plan_code or ""
        plan_str = f"  ·  Gói: {plan}" if plan else ""
        self._set_status(
            f"✓  Kích hoạt thành công!{plan_str}\n   Hết hạn: {exp_str}",
            "ok"
        )
        self._activated = True
        QTimer.singleShot(1800, self.accept)

    def _finish_err(self, msg: str):
        self._stop_loading_ui()
        self._set_status(msg, "err")
        self._btn_activate.setEnabled(True)
        self._btn_quit.setEnabled(True)
        if hasattr(self, "_btn_trial"):
            self._btn_trial.setEnabled(True)

    def _stop_loading_ui(self):
        """Dừng timeout timer và animation dots."""
        if hasattr(self, "_activate_timeout") and self._activate_timeout:
            self._activate_timeout.stop()
            self._activate_timeout = None
        if hasattr(self, "_dot_timer") and self._dot_timer:
            self._dot_timer.stop()
            self._dot_timer = None

    def _on_quit(self):
        QApplication.quit()

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


# ── public helpers ────────────────────────────────────────────────────────────

def check_license_on_startup(window) -> bool:
    """
    Kiểm tra license khi khởi động.
    Luồng:
      1. License hợp lệ → chạy bình thường
      2. Chưa có license:
         a. Trial chưa bắt đầu → hiện dialog (có nút Dùng thử + Kích hoạt)
         b. Trial đang chạy   → chạy bình thường + banner đếm ngược
         c. Trial hết hạn     → hiện dialog chỉ có Kích hoạt (bắt buộc)
    """
    from app.config import VPS_LICENSE_BASE_URL
    if not VPS_LICENSE_BASE_URL:
        return True  # bypass mode — không cần license

    from packages.license_client import get_license_client
    client = get_license_client()
    status = client.validate_cached()

    if status.active:
        _start_heartbeat(window, client)
        return True

    # Không có license — kiểm tra trial
    from packages.license_client.trial import has_trial_started, get_or_init_trial

    if not has_trial_started():
        # Lần đầu dùng app → hiện dialog cho người dùng chọn
        dlg = LicenseActivationDialog(window, show_trial_option=True)
        dlg.exec()

        if dlg.was_activated():
            _start_heartbeat(window, get_license_client())
            return True

        if dlg.was_trial_chosen():
            trial = get_or_init_trial()
            _show_trial_banner(window, trial["days_remaining"])
            return True

        return False  # user bấm Thoát

    # Trial đã bắt đầu — kiểm tra còn hạn không
    trial = get_or_init_trial()

    if not trial["expired"]:
        # Vẫn trong thời gian dùng thử
        _show_trial_banner(window, trial["days_remaining"])
        return True

    # Trial hết hạn → bắt buộc kích hoạt
    dlg = LicenseActivationDialog(window, show_trial_option=False)
    dlg.exec()

    if dlg.was_activated():
        _remove_trial_banner(window)
        _start_heartbeat(window, get_license_client())
        return True

    return False  # user bấm Thoát


def open_license_dialog(window):
    """Mở dialog từ menu License — dùng khi app đang chạy."""
    from packages.license_client import get_license_client
    status = get_license_client().validate_cached()
    if status.active:
        exp = status.expires_at
        from app.dialogs import show_info
        exp_str = exp.strftime("%d/%m/%Y") if exp else "không xác định"
        show_info(window, "Bản quyền đang hoạt động",
                  f"License key đã kích hoạt.\nHết hạn: {exp_str}")
        return

    dlg = LicenseActivationDialog(window, show_trial_option=True)
    dlg.exec()
    if dlg.was_activated():
        _remove_trial_banner(window)
        _start_heartbeat(window, get_license_client())


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
    timer = QTimer(window)
    timer.setInterval(6 * 3600 * 1000)  # 6h

    def _beat():
        def _worker():
            try:
                status = client.heartbeat()
                if not status.active:
                    QTimer.singleShot(0, lambda: _warn_expired(window))
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    timer.timeout.connect(_beat)
    timer.start()
    window._license_heartbeat_timer = timer


def _warn_expired(window):
    from app.dialogs import show_warning
    show_warning(
        window,
        "License hết hạn",
        "License đã bị thu hồi hoặc hết hạn.\n"
        "Vui lòng liên hệ 3T Company để gia hạn.",
    )
