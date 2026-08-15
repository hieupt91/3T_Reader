"""B53: test tích hợp mô phỏng đúng vòng đời thật đã gây ra lỗi thật hôm
15/08/2026 - từng hàm riêng lẻ (base_version.py, delta_runtime.py) đều có
test đơn vị PASS, nhưng lỗi thật chỉ lộ ra khi các bước nối tiếp nhau theo
đúng trình tự người dùng thật trải qua: cài đặt đầy đủ -> áp 1 bản vá nhỏ ->
sau đó được cài lại bằng bản đầy đủ MỚI HƠN (đổi base). Test đơn vị của
từng file không bắt được lớp lỗi này vì mỗi test tự dựng lại trạng thái ban
đầu riêng, không nối tiếp qua nhiều "phiên cài đặt" như thật.

Mục đích: nếu ai đó (kể cả tương lai) sửa lại base_version.py hay
delta_runtime.py theo cách vô tình làm sống lại lỗi cũ, test này phải FAIL
ngay, không cần chờ tới lúc tự tay verify trên máy thật mới phát hiện ra."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from packages.updater import base_version, delta_runtime


def _make_code_package(root: Path, contents: bytes, *, name: str = "extracted") -> Path:
    extracted = root / name
    payload = extracted / "payload" / "app"
    payload.mkdir(parents=True)
    (payload / "module.pyc").write_bytes(contents)
    (extracted / "manifest.json").write_text(
        json.dumps({"files": [{"path": "app/module.pyc", "sha256": hashlib.sha256(contents).hexdigest()}]}),
        encoding="utf-8",
    )
    return extracted


def test_full_reinstall_on_newer_base_self_heals_stale_delta_state(monkeypatch, tmp_path):
    """Đúng trình tự thật đã gây lỗi 15/08/2026:

    1. Máy cài bản đầy đủ đầu tiên (base cũ) - lần khởi động đầu tự ghi đúng
       base cũ vào base_version.txt (reconcile).
    2. Server phát hành 1 bản vá delta nhỏ nhắm đúng base cũ đó - máy áp
       thành công, base_version.txt vẫn đúng base cũ (không đổi, vì delta
       không bao giờ nâng base).
    3. Sau đó máy được cài lại bằng bản đầy đủ MỚI HƠN (base mới) - file
       chương trình đã đổi hết nhưng base_version.txt (nằm ở AppData, không
       bị cài đặt đụng tới) VẪN CÒN base cũ.
    4. Lần khởi động đầu tiên của bản mới phải tự phát hiện và sửa đúng -
       nếu không, server sẽ mãi mãi coi máy này "chưa lên base mới", không
       bao giờ cấp delta cho máy này nữa (lỗi thật, không phải giả định)."""
    base_version_path = tmp_path / "base_version.txt"
    monkeypatch.setattr(base_version, "_path", lambda: str(base_version_path))

    # Bước 1: cài đặt đầy đủ đầu tiên, native base "base-OLD".
    monkeypatch.setattr(base_version, "NATIVE_BASE_VERSION", "base-OLD")
    base_version.reconcile_native_base_version()
    assert base_version.get_installed_base_version() == "base-OLD"

    # Bước 2: áp 1 delta thật nhắm đúng base-OLD (dùng hàm apply_pending_update
    # thật, không mock, để bắt được cả lỗi ở lớp ghi file delta lẫn lớp
    # base_version nếu 2 bên vô tình không khớp nhau nữa).
    pending_root = tmp_path / "pending"
    target = tmp_path / "_internal"
    (target / "app").mkdir(parents=True)
    (target / "app" / "module.pyc").write_bytes(b"old code")
    monkeypatch.setattr(delta_runtime, "_update_root", lambda: pending_root)

    state_dir = delta_runtime.prepare_pending_update(
        str(_make_code_package(tmp_path, b"patched code v1")),
        str(target),
        version="1.0.X.1",
        base_version="base-OLD",
    )
    assert delta_runtime.apply_pending_update(state_dir) is True
    assert (target / "app" / "module.pyc").read_bytes() == b"patched code v1"
    assert base_version.get_installed_base_version() == "base-OLD", (
        "áp delta xong base vẫn phải là base-OLD - delta không được phép tự đổi base"
    )

    # Bước 3+4: "cài lại" bằng bản đầy đủ mới hơn - mô phỏng bằng cách đổi
    # NATIVE_BASE_VERSION (đúng những gì xảy ra khi build mới build_secure.py
    # + Inno Setup ra 1 bản base mới) rồi gọi lại đúng hàm main.py gọi lúc
    # khởi động. base_version.txt KHÔNG bị xoá/đổi bởi bước "cài đặt" này
    # (chỉ mô phỏng đúng thật: installer không đụng AppData).
    monkeypatch.setattr(base_version, "NATIVE_BASE_VERSION", "base-NEW")
    base_version.reconcile_native_base_version()

    assert base_version.get_installed_base_version() == "base-NEW", (
        "sau khi cài lại bằng bản đầy đủ base mới, lần khởi động đầu tiên PHẢI "
        "tự sửa base_version.txt - để sót giá trị cũ nghĩa là server sẽ không "
        "bao giờ cấp delta cho máy này nữa (lỗi thật 15/08/2026)"
    )

    # Bonus: xác nhận máy vẫn áp được 1 delta MỚI nhắm đúng base-NEW sau khi
    # đã tự sửa - không chỉ sửa xong giá trị rồi thôi, cơ chế phải còn hoạt
    # động đúng cho vòng đời tiếp theo.
    (target / "app" / "module.pyc").write_bytes(b"patched code v1")  # baseline bản đầy đủ mới
    state_dir_2 = delta_runtime.prepare_pending_update(
        str(_make_code_package(tmp_path, b"patched code v2", name="extracted2")),
        str(target),
        version="1.0.X.2",
        base_version="base-NEW",
    )
    assert delta_runtime.apply_pending_update(state_dir_2) is True
    assert (target / "app" / "module.pyc").read_bytes() == b"patched code v2"
    assert base_version.get_installed_base_version() == "base-NEW"
