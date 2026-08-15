"""OCR uses Windows child-process flags and isolated automatic workers."""
from app.config import AUTO_OCR_ON_OPEN
from app.actions import auto_ocr
from packages.ocr import engine


def test_auto_ocr_is_enabled_with_the_isolated_worker():
    assert AUTO_OCR_ON_OPEN is True


def test_hidden_process_kwargs_are_empty_off_windows(monkeypatch):
    monkeypatch.setattr(engine.sys, "platform", "linux")
    assert engine._hidden_process_kwargs() == {}


def test_auto_ocr_uses_an_isolated_hidden_helper():
    import inspect

    source = inspect.getsource(auto_ocr._run_isolated_ocr)
    assert "--auto-ocr-worker" in source
    assert "CREATE_NO_WINDOW" in source
    assert "uuid.uuid4" in source
