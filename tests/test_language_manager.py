import json


def test_builtin_translation_fallback():
    from app.language_manager import get_translation

    assert get_translation("en", "menu.file", "Tệp") == "File"
    assert get_translation("vi", "menu.file", "Tệp") == "Tệp"
    assert get_translation("fr", "menu.file", "Tệp") == "Fichier"


def test_available_languages_includes_new_locale():
    from app.language_manager import available_languages

    codes = {item["code"] for item in available_languages()}
    assert {"vi", "en", "fr"}.issubset(codes)


def test_download_language_pack_saves_file(tmp_path, monkeypatch):
    from app import language_manager as lm

    monkeypatch.setattr(lm, "language_pack_dir", lambda: tmp_path)

    class _Resp:
        headers = {"Content-Length": "34"}

        def __init__(self):
            self._chunks = [b'{"strings":{"menu.file":"File"}}', b""]

        def read(self, n=65536):
            return self._chunks.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def close(self):
            return None

    class _Opener:
        def open(self, req, timeout=30):
            assert req.full_url.endswith("/en.json")
            return _Resp()

    monkeypatch.setattr(lm.urllib.request, "build_opener", lambda *args, **kwargs: _Opener())

    ok, detail = lm.download_language_pack("en", parent=None)
    assert ok is True
    assert tmp_path.joinpath("en.json").exists()


def test_download_language_pack_reports_tried_urls(tmp_path, monkeypatch):
    from app import language_manager as lm

    monkeypatch.setattr(lm, "language_pack_dir", lambda: tmp_path)

    class _Opener:
        def open(self, req, timeout=30):
            raise lm.HTTPError(req.full_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(lm.urllib.request, "build_opener", lambda *args, **kwargs: _Opener())

    ok, detail = lm.download_language_pack("fr", parent=None)
    assert ok is False
    assert "HTTPError 403 Forbidden" in detail
    assert "tried=" in detail
