from __future__ import annotations


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
