import json


def test_builtin_translation_fallback():
    from app.language_manager import get_translation

    assert get_translation("en", "menu.file", "Tệp") == "File"
    assert get_translation("vi", "menu.file", "Tệp") == "Tệp"


def test_download_language_pack_saves_file(tmp_path, monkeypatch):
    from app import language_manager as lm

    monkeypatch.setattr(lm, "language_pack_dir", lambda: tmp_path)

    captured = {}

    def fake_urlretrieve(url, save_path, reporthook=None):
        captured["url"] = url
        captured["path"] = save_path
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump({"strings": {"menu.file": "File"}}, f)
        return save_path, None

    monkeypatch.setattr(lm.urllib.request, "urlretrieve", fake_urlretrieve)

    ok, detail = lm.download_language_pack("en", parent=None)
    assert ok is True
    assert captured["url"].endswith("/en.json")
    assert str(captured["path"]).endswith("en.json")
    assert tmp_path.joinpath("en.json").exists()
