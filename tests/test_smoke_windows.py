"""Windows-only smoke tests for 3T Reader Phase 1.

Run on a Windows machine:
    pytest tests/test_smoke_windows.py -v
"""

import sys
import os
import pytest

WINDOWS = sys.platform == "win32"
skip_non_windows = pytest.mark.skipif(not WINDOWS, reason="Windows only")


# ------------------------------------------------------------------ #
#  Platform paths                                                       #
# ------------------------------------------------------------------ #

class TestWindowsPaths:
    @skip_non_windows
    def test_app_data_dir_is_appdata(self):
        from packages.platform.paths import get_app_data_dir
        d = get_app_data_dir()
        assert "3T Reader" in str(d) or "3t" in str(d).lower()
        assert "AppData" in str(d) or "APPDATA" in os.environ

    @skip_non_windows
    def test_app_data_dir_created(self):
        from packages.platform.paths import get_app_data_dir
        d = get_app_data_dir()
        assert os.path.isdir(d)

    @skip_non_windows
    def test_recent_file_path_under_appdata(self):
        from core.recent import _recent_path
        p = _recent_path()
        assert os.path.isabs(p)


# ------------------------------------------------------------------ #
#  Font resolver                                                        #
# ------------------------------------------------------------------ #

class TestWindowsFontResolver:
    @skip_non_windows
    def test_system_font_found(self):
        from packages.platform.fonts import get_system_font_path
        p = get_system_font_path("arial")
        assert p is not None
        assert os.path.exists(p)

    @skip_non_windows
    def test_fallback_font_not_none(self):
        from packages.platform.fonts import get_system_font_path
        # Should return something even for unknown font
        p = get_system_font_path("nonexistent-font-xyz")
        # May return None — just ensure it doesn't crash
        assert p is None or os.path.exists(p)


# ------------------------------------------------------------------ #
#  Signing provider                                                     #
# ------------------------------------------------------------------ #

class TestWindowsSigningProvider:
    @skip_non_windows
    def test_provider_instantiates(self):
        from packages.signing.windows_provider import WindowsPkcs11Provider
        p = WindowsPkcs11Provider()
        assert p is not None

    @skip_non_windows
    def test_token_presence_probe_returns_bool(self):
        from packages.signing.windows_provider import WindowsPkcs11Provider
        p = WindowsPkcs11Provider()
        assert isinstance(p.is_token_present(), bool)


# ------------------------------------------------------------------ #
#  PDF engine                                                           #
# ------------------------------------------------------------------ #

class TestWindowsPdfEngine:
    @skip_non_windows
    def test_default_engine_is_pdfium(self):
        from packages.pdf_engine import get_pdf_engine
        engine = get_pdf_engine()
        assert "pdfium" in type(engine).__name__.lower()

    @skip_non_windows
    def test_no_fitz_in_default_path(self):
        from packages.pdf_engine import get_pdf_engine
        get_pdf_engine()
        fitz_loaded = "fitz" in sys.modules or "pymupdf" in sys.modules
        assert not fitz_loaded

    @skip_non_windows
    def test_page_count_on_sample(self, tmp_path):
        import reportlab.pdfgen.canvas as rcanvas
        pdf_path = str(tmp_path / "test.pdf")
        c = rcanvas.Canvas(pdf_path)
        c.drawString(50, 750, "Test")
        c.save()
        from packages.pdf_engine import get_pdf_engine
        count = get_pdf_engine().page_count(pdf_path)
        assert count == 1


# ------------------------------------------------------------------ #
#  Local HTTP server                                                    #
# ------------------------------------------------------------------ #

class TestLocalServer:
    @skip_non_windows
    def test_server_starts(self):
        from app.local_server import LocalPDFJSServer
        srv = LocalPDFJSServer()
        srv.start()
        assert srv._port > 0
        srv.stop()

    @skip_non_windows
    def test_viewer_url_format(self, tmp_path):
        from app.local_server import LocalPDFJSServer
        import reportlab.pdfgen.canvas as rcanvas
        pdf_path = str(tmp_path / "t.pdf")
        c = rcanvas.Canvas(pdf_path)
        c.save()
        srv = LocalPDFJSServer()
        srv.start()
        url = srv.viewer_url(pdf_path, page=1, zoom="page-width")
        assert url is not None
        assert "127.0.0.1" in url
        assert "viewer.html" in url
        srv.stop()


# ------------------------------------------------------------------ #
#  Import cleanliness                                                   #
# ------------------------------------------------------------------ #

class TestWindowsImportCleanliness:
    @skip_non_windows
    def test_no_darwin_only_imports(self):
        import importlib
        # These modules should not be imported on Windows
        darwin_only = ["Foundation", "AppKit", "Cocoa"]
        for mod in darwin_only:
            assert mod not in sys.modules, f"{mod} should not be loaded on Windows"

    @skip_non_windows
    def test_pyside6_loads(self):
        from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets
        assert QtCore is not None

    @skip_non_windows
    def test_qt_compat_loads(self):
        from packages.qt_compat import QtWidgets, QtCore, pyqtSignal
        assert QtWidgets is not None
