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
    quyền admin liên tục. _launch_deelevated() phải relaunch qua
    ``explorer.exe <path>`` (Explorer đã chạy sẵn ở integrity level thường
    của user, nhận yêu cầu và tự CreateProcess) - không phải
    subprocess.Popen thẳng kế thừa token elevated hiện tại.

    Fix lần 1 (dùng win32com Shell.Application COM) tưởng đã xong nhưng khi
    verify lại lần 2 trên bản cài thật (15/08/2026) app vẫn quay lại chạy
    Admin - win32com/pythoncom là dependency dễ vỡ trong bản đóng gói
    PyInstaller và lỗi bị nuốt im lặng không để lại dấu vết. Đổi sang
    explorer.exe: chỉ dùng subprocess (stdlib), không phụ thuộc COM/pywin32
    cho đường chính nữa."""
    from packages.updater import delta_runtime

    popen_calls = []
    monkeypatch.setattr(delta_runtime.subprocess, "Popen", lambda *a, **kw: popen_calls.append((a, kw)))

    delta_runtime._launch_deelevated(r"C:\Program Files\3T Reader\3T_Reader.exe", r"C:\Program Files\3T Reader")

    assert len(popen_calls) == 1
    args, kwargs = popen_calls[0]
    assert args[0] == ["explorer.exe", r"C:\Program Files\3T Reader\3T_Reader.exe"], (
        "phải relaunch qua explorer.exe (de-elevated), không gọi thẳng executable "
        "(kế thừa token elevated của helper hiện tại)"
    )
    assert kwargs.get("cwd") == r"C:\Program Files\3T Reader"


def test_relaunch_falls_back_to_elevated_popen_if_explorer_launch_fails(monkeypatch, tmp_path):
    """Nếu subprocess.Popen(["explorer.exe", ...]) lỗi vì lý do gì đó, vẫn
    phải mở lại được app (thà chạy quyền cao hơn cần thiết còn hơn app
    không tự mở lại được sau khi vá) - và phải ghi lại lý do thất bại để
    còn chẩn đoán được nếu tái diễn (khác lần trước, lỗi bị nuốt im lặng
    hoàn toàn không để lại dấu vết)."""
    from packages.updater import delta_runtime

    popen_calls = []

    def _fake_popen(*a, **kw):
        if a[0][0] == "explorer.exe":
            raise OSError("explorer.exe not found")
        popen_calls.append((a, kw))

    monkeypatch.setattr(delta_runtime.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(
        __import__("packages.platform", fromlist=["get_app_data_dir"]),
        "get_app_data_dir",
        lambda: str(tmp_path),
    )

    delta_runtime._launch_deelevated(r"C:\Program Files\3T Reader\3T_Reader.exe", r"C:\Program Files\3T Reader")

    assert len(popen_calls) == 1
    assert popen_calls[0][0][0] == [r"C:\Program Files\3T Reader\3T_Reader.exe"]
    log_file = tmp_path / "deelevation_fallback.log"
    assert log_file.exists()
    assert "explorer.exe" in log_file.read_text(encoding="utf-8")
