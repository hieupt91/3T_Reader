from __future__ import annotations


def test_tesseract_path_env_override(monkeypatch):
    from packages.ocr import engine

    monkeypatch.setenv("OCR_TESSERACT_CMD", r"C:\Custom\Tesseract-OCR\tesseract.exe")
    monkeypatch.setattr(engine, "_is_executable", lambda path: path.endswith("tesseract.exe"))

    assert engine._tesseract_cmd() == r"C:\Custom\Tesseract-OCR\tesseract.exe"


def test_bundled_tesseract_preferred_before_system_path(monkeypatch):
    from packages.ocr import engine

    bundled = r"C:\Program Files\3T Reader\_internal\Tesseract-OCR\tesseract.exe"
    system = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    monkeypatch.setattr(engine.sys, "executable", r"C:\Program Files\3T Reader\3T_Reader.exe")
    monkeypatch.setattr(engine.shutil, "which", lambda name: system)
    monkeypatch.setattr(engine, "_is_executable", lambda path: path in {bundled, system})

    assert engine._tesseract_cmd() == bundled


def test_tessdata_env_override(monkeypatch):
    from packages.ocr import engine

    monkeypatch.setenv("TESSDATA_PREFIX", r"C:\Custom\Tesseract-OCR\tessdata")
    monkeypatch.setattr(engine.os.path, "isdir", lambda path: path == r"C:\Custom\Tesseract-OCR\tessdata")

    assert engine._tessdata_dir() == r"C:\Custom\Tesseract-OCR\tessdata"


def test_runtime_status_reports_missing_tesseract(monkeypatch):
    from packages.ocr import engine

    monkeypatch.setattr(engine, "_tesseract_cmd", lambda: None)

    status = engine.runtime_status()

    assert status.available is False
    assert "Tesseract" in status.error


def test_runtime_status_reports_languages(monkeypatch):
    from packages.ocr import engine

    monkeypatch.setattr(engine, "_tesseract_cmd", lambda: r"C:\Tesseract-OCR\tesseract.exe")
    monkeypatch.setattr(engine, "_tessdata_dir", lambda cmd=None: r"C:\Tesseract-OCR\tessdata")
    monkeypatch.setattr(engine, "get_installed_langs", lambda: ["eng", "vie"])

    status = engine.runtime_status()

    assert status.available is True
    assert status.tesseract_cmd.endswith("tesseract.exe")
    assert status.tessdata_dir.endswith("tessdata")
    assert status.missing_vietnamese is False


def test_ocr_tessdata_url_uses_configured_base(monkeypatch):
    from app.actions import ocr

    monkeypatch.setenv("OCR_TESSDATA_BASE_URL", "https://reader.3tcomputer.com/downloads/ocr/tessdata/")

    assert ocr._ocr_tessdata_url("vie") == "https://reader.3tcomputer.com/downloads/ocr/tessdata/vie.traineddata"


def test_ocr_installer_url_can_be_overridden(monkeypatch):
    from app.actions import ocr

    monkeypatch.setenv("OCR_TESSERACT_INSTALLER_URL", "https://example.com/tesseract.exe")

    assert ocr._ocr_installer_url() == "https://example.com/tesseract.exe"
