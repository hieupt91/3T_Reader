from __future__ import annotations

import json


class _FakeKey:
    def __init__(self, *, values=None, subkeys=None):
        self.values = values or {}
        self.subkeys = subkeys or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeWinReg:
    HKEY_LOCAL_MACHINE = object()
    HKEY_CURRENT_USER = object()

    def __init__(self, roots):
        self.roots = roots

    def OpenKey(self, root, subkey):
        if isinstance(root, _FakeKey):
            return root.subkeys[subkey]
        return self.roots[subkey]

    def QueryInfoKey(self, key):
        return len(key.subkeys), 0, 0

    def EnumKey(self, key, index):
        return list(key.subkeys.keys())[index]

    def QueryValueEx(self, key, value_name):
        if value_name not in key.values:
            raise OSError(value_name)
        return key.values[value_name], None


def test_registry_install_dirs_extracts_vendor_paths(tmp_path, monkeypatch):
    from packages.signing import windows_provider as wp

    install_dir = tmp_path / "Program Files" / "Viettel CA"
    install_dir.mkdir(parents=True)

    uninstall_root = _FakeKey(
        subkeys={
            "Viettel CA Token Manager": _FakeKey(
                values={
                    "DisplayName": "Viettel CA Token Manager",
                    "Publisher": "Viettel",
                    "InstallLocation": str(install_dir),
                }
            ),
            "Noise Entry": _FakeKey(
                values={
                    "DisplayName": "Some unrelated app",
                    "Publisher": "Example",
                    "InstallLocation": str(tmp_path / "ignored"),
                }
            ),
        }
    )
    fake_winreg = _FakeWinReg(
        {
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall": uninstall_root,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall": _FakeKey(),
        }
    )
    monkeypatch.setattr(wp, "_winreg", fake_winreg)

    dirs = wp._registry_install_dirs()
    assert str(install_dir) in dirs


def test_registry_candidate_dir_parses_display_icon_path(tmp_path):
    from packages.signing import windows_provider as wp

    dll_dir = tmp_path / "FPT" / "Token"
    dll_dir.mkdir(parents=True)
    dll_path = dll_dir / "FPT_Token.dll"
    dll_path.write_text("x", encoding="utf-8")

    parsed = wp._registry_candidate_dir(f'"{dll_path}",0')
    assert parsed == str(dll_dir)


def test_candidate_paths_scans_installed_signing_app_subdirectories(tmp_path, monkeypatch):
    from packages.signing import windows_provider as wp

    install_dir = tmp_path / "VNPT SmartCA"
    nested_dir = install_dir / "bin" / "x64" / "driver"
    nested_dir.mkdir(parents=True)
    dll_path = nested_dir / "cryptoki_driver.dll"
    dll_path.write_bytes(b"MZ")

    monkeypatch.setattr(wp, "_registry_install_dirs", lambda: [str(install_dir)])
    monkeypatch.setattr(wp, "_candidate_search_dirs", lambda: [])
    monkeypatch.delenv(wp.WINDOWS_PKCS11_PATHS_ENV, raising=False)

    paths = wp._candidate_paths()

    assert str(dll_path) in paths


def test_generic_pkcs11_dll_scan_can_recurse_for_installed_apps(tmp_path):
    from packages.signing import windows_provider as wp

    nested_dir = tmp_path / "EasyCA" / "module" / "pkcs"
    nested_dir.mkdir(parents=True)
    wanted = nested_dir / "easyca_p11.dll"
    ignored = nested_dir / "helper.dll"
    wanted.write_bytes(b"MZ")
    ignored.write_bytes(b"MZ")

    matches = wp._generic_pkcs11_dlls(str(tmp_path), recursive=True)

    assert str(wanted) in matches
    assert str(ignored) not in matches


def test_frozen_probe_uses_packaged_worker(monkeypatch):
    from packages.signing import windows_provider as wp

    captured = {}

    class _Result:
        stdout = "TOKEN\n"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Result()

    monkeypatch.setattr(wp.sys, "frozen", True, raising=False)
    monkeypatch.setattr(wp.sys, "executable", r"C:\App\3T_Reader.exe")
    monkeypatch.setattr(wp.subprocess, "run", fake_run)

    ok, detail = wp._probe_driver_for_token(r"C:\Vendor\token.dll")

    assert ok is True
    assert detail == ""
    assert captured["command"] == [
        r"C:\App\3T_Reader.exe",
        "--pkcs11-probe-token",
        r"C:\Vendor\token.dll",
    ]
    assert captured["kwargs"]["timeout"] == 8


def test_frozen_list_tokens_uses_packaged_worker(monkeypatch):
    from packages.signing import windows_provider as wp

    captured = {}

    class _Result:
        stdout = json.dumps({"tokens": [{"index": 0, "label": "USB Token"}]}) + "\n"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Result()

    monkeypatch.setattr(wp.sys, "frozen", True, raising=False)
    monkeypatch.setattr(wp.sys, "executable", r"C:\App\3T_Reader.exe")
    monkeypatch.setattr(wp.subprocess, "run", fake_run)

    tokens, detail = wp._probe_driver_tokens(r"C:\Vendor\token.dll")

    assert detail == ""
    assert tokens == [{"index": 0, "label": "USB Token"}]
    assert captured["command"] == [
        r"C:\App\3T_Reader.exe",
        "--pkcs11-list-tokens",
        r"C:\Vendor\token.dll",
    ]
    assert captured["kwargs"]["timeout"] == 10
