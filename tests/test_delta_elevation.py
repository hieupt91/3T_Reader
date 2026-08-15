from __future__ import annotations


def test_windows_delta_helper_requests_uac(monkeypatch, tmp_path):
    from packages.updater import delta_runtime

    calls = []

    class _Shell32:
        @staticmethod
        def ShellExecuteW(*args):
            calls.append(args)
            return 33

    class _Windll:
        shell32 = _Shell32()

    monkeypatch.setattr(delta_runtime.sys, "platform", "win32")
    monkeypatch.setattr(delta_runtime.ctypes if hasattr(delta_runtime, "ctypes") else __import__("ctypes"), "windll", _Windll(), raising=False)
    # Import is inside the function, therefore expose the patched module via
    # sys.modules rather than relying on a Windows host.
    import ctypes
    monkeypatch.setattr(ctypes, "windll", _Windll(), raising=False)

    delta_runtime.spawn_apply_helper(str(tmp_path), parent_pid=123, executable=r"C:\\Program Files\\3T Reader\\3T_Reader.exe")

    assert len(calls) == 1
    assert calls[0][1] == "runas"
    assert "--apply-delta" in calls[0][3]


def test_relaunch_after_apply_is_deelevated_not_inherited(monkeypatch, tmp_path):
    """Regression cho lỗi thật phát hiện qua QA GUI test 15/08/2026: app sau
    khi tự khởi động lại lúc trước chạy với quyền Administrator (kế thừa
    token elevated của chính helper --apply-delta), khiến UI Automation/
    input mô phỏng từ tiến trình quyền thường không tương tác được (Windows
    UIPI) - vi phạm nguyên tắc least-privilege cho 1 app đọc PDF không cần
    quyền admin liên tục. _launch_deelevated() phải đi qua
    Shell.Application COM (chạy ở integrity level của Explorer, không phải
    subprocess.Popen thẳng kế thừa token elevated hiện tại)."""
    from packages.updater import delta_runtime

    shell_execute_calls = []

    class _FakeShell:
        def ShellExecute(self, *args):
            shell_execute_calls.append(args)

    class _FakeWin32Com:
        class client:
            @staticmethod
            def Dispatch(name):
                assert name == "Shell.Application"
                return _FakeShell()

    monkeypatch.setitem(__import__("sys").modules, "win32com", _FakeWin32Com())
    monkeypatch.setitem(__import__("sys").modules, "win32com.client", _FakeWin32Com.client)

    popen_calls = []
    monkeypatch.setattr(delta_runtime.subprocess, "Popen", lambda *a, **kw: popen_calls.append((a, kw)))

    delta_runtime._launch_deelevated(r"C:\Program Files\3T Reader\3T_Reader.exe", r"C:\Program Files\3T Reader")

    assert len(shell_execute_calls) == 1, "phải relaunch qua Shell.Application COM (de-elevated), không subprocess.Popen thẳng"
    assert popen_calls == [], "không được rơi xuống subprocess.Popen (kế thừa quyền elevated) khi COM de-elevation khả dụng"
    assert shell_execute_calls[0][0] == r"C:\Program Files\3T Reader\3T_Reader.exe"
    assert shell_execute_calls[0][3] == "open"


def test_relaunch_falls_back_to_popen_if_com_unavailable(monkeypatch, tmp_path):
    """Nếu win32com lỗi vì lý do gì đó, vẫn phải mở lại được app (thà chạy
    quyền cao hơn cần thiết còn hơn app không tự mở lại được sau khi vá)."""
    from packages.updater import delta_runtime

    def _raise_import(name, *a, **k):
        if name == "win32com.client":
            raise ImportError("no win32com")
        return __import__(name, *a, **k)

    monkeypatch.delitem(__import__("sys").modules, "win32com", raising=False)
    monkeypatch.delitem(__import__("sys").modules, "win32com.client", raising=False)

    popen_calls = []
    monkeypatch.setattr(delta_runtime.subprocess, "Popen", lambda *a, **kw: popen_calls.append((a, kw)))

    import builtins
    real_import = builtins.__import__
    def _fake_import(name, *a, **k):
        if name == "win32com.client":
            raise ImportError("no win32com")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", _fake_import)

    delta_runtime._launch_deelevated(r"C:\Program Files\3T Reader\3T_Reader.exe", r"C:\Program Files\3T Reader")

    assert len(popen_calls) == 1
