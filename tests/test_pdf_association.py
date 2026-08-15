"""Icon-cache self-heal when the user changes the default .pdf handler
via Windows Settings instead of the installer's checkbox — see
packages/platform/pdf_association.py for the full explanation."""
from __future__ import annotations


class _FakeKey:
    def __init__(self, values=None):
        self.values = values or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeWinReg:
    HKEY_CURRENT_USER = object()
    HKEY_CLASSES_ROOT = object()

    def __init__(self, user_choice_progid=None, hkcr_default=None):
        self._user_choice_progid = user_choice_progid
        self._hkcr_default = hkcr_default

    def OpenKey(self, root, subkey):
        if "UserChoice" in subkey:
            if self._user_choice_progid is None:
                raise OSError("not found")
            return _FakeKey({"ProgId": self._user_choice_progid})
        if subkey == ".pdf":
            if self._hkcr_default is None:
                raise OSError("not found")
            return _FakeKey({"": self._hkcr_default})
        raise OSError("unexpected subkey")

    def QueryValueEx(self, key, value_name):
        if value_name not in key.values:
            raise OSError(value_name)
        return key.values[value_name], None


def test_no_refresh_when_progid_unchanged(tmp_path, monkeypatch):
    from packages.platform import pdf_association as mod

    monkeypatch.setattr(mod, "_winreg", _FakeWinReg(user_choice_progid="3TReader.PDF"))
    monkeypatch.setattr(mod, "_STATE_FILE", str(tmp_path / "state.json"))
    calls = []
    monkeypatch.setattr(mod, "_refresh_explorer_icon_cache", lambda: calls.append(1))

    mod.refresh_pdf_icon_if_default_changed()
    assert calls == [1], "first launch after a real change must refresh once"

    mod.refresh_pdf_icon_if_default_changed()
    assert calls == [1], "unchanged progid on second launch must not refresh again"


def test_refresh_when_default_changes_to_us(tmp_path, monkeypatch):
    from packages.platform import pdf_association as mod

    monkeypatch.setattr(mod, "_STATE_FILE", str(tmp_path / "state.json"))
    calls = []
    monkeypatch.setattr(mod, "_refresh_explorer_icon_cache", lambda: calls.append(1))

    monkeypatch.setattr(mod, "_winreg", _FakeWinReg(user_choice_progid="OtherApp.PDF"))
    mod.refresh_pdf_icon_if_default_changed()
    assert calls == [], "not our progid yet - no refresh needed"

    monkeypatch.setattr(mod, "_winreg", _FakeWinReg(user_choice_progid="3TReader.PDF"))
    mod.refresh_pdf_icon_if_default_changed()
    assert calls == [1], "progid just changed to ours - must refresh"


def test_falls_back_to_hkcr_when_no_user_choice(tmp_path, monkeypatch):
    from packages.platform import pdf_association as mod

    monkeypatch.setattr(mod, "_winreg", _FakeWinReg(hkcr_default="3TReader.PDF"))
    monkeypatch.setattr(mod, "_STATE_FILE", str(tmp_path / "state.json"))
    calls = []
    monkeypatch.setattr(mod, "_refresh_explorer_icon_cache", lambda: calls.append(1))

    mod.refresh_pdf_icon_if_default_changed()
    assert calls == [1]


def test_noop_when_winreg_unavailable(tmp_path, monkeypatch):
    from packages.platform import pdf_association as mod

    monkeypatch.setattr(mod, "_winreg", None)
    # Must not raise.
    mod.refresh_pdf_icon_if_default_changed()
