"""Lỗi ghi chú cũ: "xóa trang rồi thao tác gì một lát xóa lại thì báo lỗi:
[Errno 2] No such file or directory: '...reader_pdf_edit\\work_xxxx.pdf'".

Nguyên nhân thật: sau khi chèn ảnh/chữ, _run_object_action_session()
(app/actions/edit.py) hiện khung xoay/di chuyển và CHỜ trong 1 QEventLoop
LỒNG NHAU (loop.exec(), tối đa 10s) - Qt vẫn bơm sự kiện khác trong lúc chờ
đó, nên click "Xóa trang" của người dùng chạy CHEN NGANG được, gọi
save_edits_quiet() -> _reset_edit_state() XOÁ THẲNG file tạm
(base_snapshot/working_file) của đúng session đang treo dở đó. Khi
loop.exec() trả về, phần xử lý tiếp theo đọc lại đường dẫn đã bị xoá, báo
lỗi "No such file or directory".

Fix: cờ window._object_action_session_active - _auto_commit_edit_state()
(app/actions/pages.py, gọi trước khi xóa/xoay trang) phải từ chối chạy
save/reset khi cờ này đang bật, thay vì chạy chen ngang gây lỗi."""
from __future__ import annotations

from types import SimpleNamespace

from app.actions import pages


def test_refuses_to_commit_while_object_action_session_active(monkeypatch):
    save_calls = []
    monkeypatch.setattr("app.actions.edit._get_edit_state", lambda w: {"ops": [{"id": 1}]})
    monkeypatch.setattr("app.actions.edit.save_edits_quiet", lambda w: save_calls.append(w) or True)
    warnings = []
    monkeypatch.setattr(pages, "show_warning", lambda w, title, msg: warnings.append((title, msg)))

    window = SimpleNamespace(_object_action_session_active=True)

    result = pages._auto_commit_edit_state(window)

    assert result is False, "phải từ chối (return False) khi có session đối tượng đang treo dở"
    assert save_calls == [], "không được gọi save_edits_quiet() chen ngang session đang treo dở"
    assert warnings, "phải báo cho người dùng biết vì sao thao tác bị từ chối"


def test_commits_normally_when_no_object_action_session_active(monkeypatch):
    save_calls = []
    monkeypatch.setattr("app.actions.edit._get_edit_state", lambda w: {"ops": [{"id": 1}]})
    monkeypatch.setattr("app.actions.edit.save_edits_quiet", lambda w: save_calls.append(w) or True)

    window = SimpleNamespace(_object_action_session_active=False)

    result = pages._auto_commit_edit_state(window)

    assert result is True
    assert save_calls == [window]


def test_commits_normally_when_flag_attribute_missing_entirely(monkeypatch):
    """window thường (chưa từng chạy qua object-action session nào) không có
    thuộc tính này - phải coi như không active, không được vỡ vì AttributeError."""
    save_calls = []
    monkeypatch.setattr("app.actions.edit._get_edit_state", lambda w: {"ops": [{"id": 1}]})
    monkeypatch.setattr("app.actions.edit.save_edits_quiet", lambda w: save_calls.append(w) or True)

    window = SimpleNamespace()

    result = pages._auto_commit_edit_state(window)

    assert result is True
    assert save_calls == [window]
