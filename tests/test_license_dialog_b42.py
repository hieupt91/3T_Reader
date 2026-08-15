"""B42: dòng 'Kích hoạt / Nhập key...' phải ẩn/đổi thành trạng thái đã kích
hoạt sau khi active, và bấm vào đó (badge/menu/ribbon) khi đang active phải
hiện thông tin gói - không còn bắt nhập lại key mỗi lần bấm (trước đây
open_license_dialog() luôn mở thẳng form nhập key trống)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest

from packages.license_client.models import LicenseStatus

sys.path.insert(0, ".")

from packages.qt_compat.QtWidgets import QApplication, QWidget
from packages.qt_compat.QtGui import QAction

from app.license_dialog import (
    _is_highest_plan,
    _plan_label,
    _update_license_menu_rows,
    LicenseInfoDialog,
    open_license_dialog,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_plan_label_known_codes():
    assert _plan_label("3tr-p") == "Cá Nhân"
    assert _plan_label("3tr-e") == "Doanh Nghiệp"
    assert _plan_label("") == "Miễn Phí"


def test_is_highest_plan_only_enterprise():
    assert _is_highest_plan("3tr-e") is True
    assert _is_highest_plan("enterprise") is True
    assert _is_highest_plan("3tr-p") is False
    assert _is_highest_plan("") is False


def test_update_license_menu_rows_shows_activated_state(qapp):
    window = QWidget()
    window._act_license_menu = QAction("placeholder")
    window._act_license_check = QAction("placeholder")

    status = LicenseStatus(active=True, plan_code="3tr-p", expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc))
    _update_license_menu_rows(window, status)

    assert "Đã kích hoạt" in window._act_license_menu.text()
    assert "Kích hoạt / Nhập key" not in window._act_license_menu.text()
    assert window._act_license_check.text() == "Đã kích hoạt"


def test_update_license_menu_rows_reverts_when_inactive(qapp):
    window = QWidget()
    window._act_license_menu = QAction("placeholder")
    window._act_license_check = QAction("placeholder")

    _update_license_menu_rows(window, None)

    assert "Kích hoạt / Nhập key" in window._act_license_menu.text()
    assert window._act_license_check.text() == "Kiểm tra key"


def test_license_info_dialog_hides_upgrade_button_for_highest_plan(qapp):
    window = QWidget()
    status = LicenseStatus(active=True, plan_code="3tr-e", expires_at=None)
    dlg = LicenseInfoDialog(window, status)

    upgrade_btn = None
    for child in dlg.findChildren(object):
        if getattr(child, "objectName", lambda: "")() == "btn_activate":
            upgrade_btn = child
            break
    assert upgrade_btn is None


def test_license_info_dialog_shows_upgrade_button_for_lower_plan(qapp):
    window = QWidget()
    status = LicenseStatus(active=True, plan_code="3tr-p", expires_at=None)
    dlg = LicenseInfoDialog(window, status)

    upgrade_btn = None
    for child in dlg.findChildren(object):
        if getattr(child, "objectName", lambda: "")() == "btn_activate":
            upgrade_btn = child
            break
    assert upgrade_btn is not None


def test_open_license_dialog_shows_info_not_key_form_when_active(qapp, monkeypatch):
    """Xác nhận đúng bug đã sửa: bấm vào license khi đang active không còn
    mở LicenseActivationDialog (form nhập key) mà mở LicenseInfoDialog."""
    import app.license_dialog as license_dialog_module

    window = QWidget()
    status = LicenseStatus(active=True, plan_code="3tr-p", expires_at=None)

    class _FakeClient:
        def validate_cached(self):
            return status

    import packages.license_client as license_client_pkg
    monkeypatch.setattr(license_client_pkg, "get_license_client", lambda: _FakeClient())

    opened = {}

    class _FakeInfoDialog:
        def __init__(self, parent, status):
            opened["info"] = True

        def exec(self):
            pass

        def wants_upgrade(self):
            return False

    class _FakeActivationDialog:
        def __init__(self, *a, **k):
            opened["activation"] = True

        def exec(self):
            pass

        def was_activated(self):
            return False

    monkeypatch.setattr(license_dialog_module, "LicenseInfoDialog", _FakeInfoDialog)
    monkeypatch.setattr(license_dialog_module, "LicenseActivationDialog", _FakeActivationDialog)

    open_license_dialog(window)

    assert opened.get("info") is True
    assert "activation" not in opened
