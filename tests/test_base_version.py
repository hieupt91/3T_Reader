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
