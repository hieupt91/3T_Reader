from __future__ import annotations


def test_open_file_missing_path_shows_clear_not_found_message(monkeypatch, tmp_path):
    from app.actions import file as file_actions

    missing = tmp_path / "missing.pdf"
    messages = []

    monkeypatch.setattr(file_actions, "show_warning", lambda _window, title, message: messages.append((title, message)))
    monkeypatch.setattr(
        "app.actions.document_converter.process_file_and_open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("converter should not run")),
    )

    file_actions.open_file(object(), str(missing))

    assert messages == [
        (
            "Không tìm thấy tài liệu",
            f"Không tìm thấy tài liệu tại đường dẫn:\n{missing}",
        )
    ]
