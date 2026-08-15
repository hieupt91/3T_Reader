"""B53: packages/updater/base_version.py - theo dõi base_version đã cài."""
from __future__ import annotations

from packages.updater import base_version


def test_get_installed_base_version_defaults_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(base_version, "_path", lambda: str(tmp_path / "does_not_exist.txt"))

    assert base_version.get_installed_base_version() == "base-1.0"


def test_set_then_get_roundtrip(monkeypatch, tmp_path):
    path = str(tmp_path / "base_version.txt")
    monkeypatch.setattr(base_version, "_path", lambda: path)

    base_version.set_installed_base_version("base-2.0")

    assert base_version.get_installed_base_version() == "base-2.0"


def test_set_empty_value_falls_back_to_default(monkeypatch, tmp_path):
    path = str(tmp_path / "base_version.txt")
    monkeypatch.setattr(base_version, "_path", lambda: path)

    base_version.set_installed_base_version("")

    assert base_version.get_installed_base_version() == "base-1.0"


def test_reconcile_fixes_stale_base_from_previous_delta_before_full_reinstall(monkeypatch, tmp_path):
    """Máy từng áp delta lên base cũ (vd. base-1.1), sau đó được cài lại bằng
    bản đầy đủ mới hơn (native base-1.2) - base_version.txt vẫn còn giá trị
    cũ vì cài đặt đầy đủ không đụng file này. Không reconcile thì server
    không bao giờ cấp delta tiếp cho máy này nữa (xác nhận thật 15/08/2026)."""
    path = str(tmp_path / "base_version.txt")
    monkeypatch.setattr(base_version, "_path", lambda: path)
    base_version.set_installed_base_version("base-1.1")

    base_version.reconcile_native_base_version()

    assert base_version.get_installed_base_version() == base_version.NATIVE_BASE_VERSION


def test_reconcile_is_a_noop_when_already_matching(monkeypatch, tmp_path):
    path = str(tmp_path / "base_version.txt")
    monkeypatch.setattr(base_version, "_path", lambda: path)
    base_version.set_installed_base_version(base_version.NATIVE_BASE_VERSION)

    write_calls = []
    real_set = base_version.set_installed_base_version

    def _tracking_set(value):
        write_calls.append(value)
        real_set(value)

    monkeypatch.setattr(base_version, "set_installed_base_version", _tracking_set)
    base_version.reconcile_native_base_version()

    assert write_calls == []


def test_reconcile_fixes_missing_file_too(monkeypatch, tmp_path):
    """Case cũ (chưa có file, cài đặt đầy đủ lần đầu) vẫn phải đúng ngay,
    không chỉ case file cũ còn sót."""
    monkeypatch.setattr(base_version, "_path", lambda: str(tmp_path / "does_not_exist.txt"))

    base_version.reconcile_native_base_version()

    assert base_version.get_installed_base_version() == base_version.NATIVE_BASE_VERSION
