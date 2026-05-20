"""macOS-specific smoke tests for Phase 1.

These tests verify macOS platform behavior: correct paths, correct signing
provider selection, font resolution, and import cleanliness. They run on
macOS only and are skipped on other platforms.
"""

import sys
import os
import platform
from pathlib import Path

import pytest

MACOS = sys.platform == "darwin"
skip_non_mac = pytest.mark.skipif(not MACOS, reason="macOS only")


# ── Platform paths ────────────────────────────────────────────────────────────

class TestMacOSPaths:
    @skip_non_mac
    def test_app_data_dir_uses_library_application_support(self):
        from packages.platform.paths import get_app_data_dir
        path = get_app_data_dir()
        assert "Library/Application Support" in path

    @skip_non_mac
    def test_cache_dir_uses_library_caches(self):
        from packages.platform.paths import get_cache_dir
        path = get_cache_dir()
        assert "Library/Caches" in path

    @skip_non_mac
    def test_log_dir_uses_library_logs(self):
        from packages.platform.paths import get_log_dir
        path = get_log_dir()
        assert "Library/Logs" in path

    @skip_non_mac
    def test_app_data_dir_contains_app_name(self):
        from packages.platform.paths import get_app_data_dir
        from app.config import APP_DATA_DIR_NAME
        path = get_app_data_dir()
        assert APP_DATA_DIR_NAME in path

    @skip_non_mac
    def test_no_windows_path_in_any_platform_result(self):
        from packages.platform.paths import get_app_data_dir, get_cache_dir, get_log_dir
        for fn in (get_app_data_dir, get_cache_dir, get_log_dir):
            result = fn()
            assert "AppData" not in result
            assert "System32" not in result
            assert "C:\\" not in result


# ── Font resolver ─────────────────────────────────────────────────────────────

class TestMacOSFontResolver:
    @skip_non_mac
    def test_font_path_resolves_on_macos(self):
        from packages.platform.fonts import get_vietnamese_font_path
        path = get_vietnamese_font_path()
        # May be None if no matching font found, but must not raise
        assert path is None or isinstance(path, str)

    @skip_non_mac
    def test_font_path_not_in_windows_fonts_dir(self):
        from packages.platform.fonts import get_vietnamese_font_path
        path = get_vietnamese_font_path()
        if path:
            assert "C:\\Windows" not in path
            assert "System32" not in path

    @skip_non_mac
    def test_font_in_macos_font_dirs_when_found(self):
        from packages.platform.fonts import get_vietnamese_font_path
        path = get_vietnamese_font_path()
        if path:
            macos_dirs = [
                "/Library/Fonts",
                "/System/Library/Fonts",
                str(Path.home() / "Library" / "Fonts"),
            ]
            assert any(path.startswith(d) for d in macos_dirs), (
                f"Font path '{path}' not in expected macOS font dirs"
            )


# ── Signing provider ──────────────────────────────────────────────────────────

class TestMacOSSigningProvider:
    @skip_non_mac
    def test_macos_provider_is_selected(self):
        from packages.signing import get_signing_provider
        from packages.signing.macos_provider import MacOSPkcs11Provider
        provider = get_signing_provider()
        assert isinstance(provider, MacOSPkcs11Provider)

    @skip_non_mac
    def test_provider_detects_no_token_without_hardware(self):
        from packages.signing import get_signing_provider
        provider = get_signing_provider()
        result = provider.detect_driver()
        assert result is None or isinstance(result, str)

    @skip_non_mac
    def test_provider_error_is_string(self):
        from packages.signing import get_signing_provider
        provider = get_signing_provider()
        provider.detect_driver()
        err = provider.get_last_error()
        assert isinstance(err, str)

    @skip_non_mac
    def test_windows_provider_not_imported_on_macos(self):
        import packages.signing
        assert not hasattr(packages.signing, "WindowsPkcs11Provider"), (
            "WindowsPkcs11Provider must not be imported at module level on macOS"
        )


# ── PDF engine ────────────────────────────────────────────────────────────────

class TestMacOSPdfEngine:
    @skip_non_mac
    def test_default_engine_is_pdfium(self):
        from packages.pdf_engine import get_pdf_engine, PdfiumEngine
        assert isinstance(get_pdf_engine(), PdfiumEngine)

    @skip_non_mac
    def test_pymupdf_not_imported_in_default_path(self):
        import sys
        from packages.pdf_engine import get_pdf_engine
        get_pdf_engine()
        # Check the actual PyMuPDF package keys, not substring — our own
        # packages.pdf_engine.pymupdf_engine module name would otherwise match.
        fitz_loaded = "fitz" in sys.modules or "pymupdf" in sys.modules
        assert not fitz_loaded, "PyMuPDF/fitz must not be loaded in the default engine path"


# ── Import cleanliness ────────────────────────────────────────────────────────

class TestMacOSImportCleanliness:
    @skip_non_mac
    def test_no_pyqt6_import(self):
        import sys
        assert "PyQt6" not in sys.modules

    @skip_non_mac
    def test_pyside6_binding_active(self):
        from packages.qt_compat import BINDING
        assert BINDING == "PySide6"

    @skip_non_mac
    def test_app_config_name_is_3t_reader(self):
        from app.config import APP_NAME
        assert APP_NAME == "3T Reader"


# ── Bundle layout check ───────────────────────────────────────────────────────

class TestMacOSBundleLayout:
    @skip_non_mac
    def test_pdfjs_viewer_exists(self):
        viewer = Path("third_party/pdfjs/web/viewer.html")
        assert viewer.exists(), "PDF.js viewer.html missing"

    @skip_non_mac
    def test_icons_present(self):
        icons_dir = Path("assets/icons")
        svgs = list(icons_dir.glob("*.svg"))
        assert len(svgs) >= 12, f"Expected ≥12 icons, found {len(svgs)}"

    @skip_non_mac
    def test_mac_spec_exists(self):
        spec = Path("installer/macos/3T_Reader_mac.spec")
        assert spec.exists(), "macOS PyInstaller spec missing"

    @skip_non_mac
    def test_entitlements_exists(self):
        ent = Path("installer/macos/entitlements.plist")
        assert ent.exists(), "macOS entitlements.plist missing"

    @skip_non_mac
    def test_build_script_exists_and_executable(self):
        script = Path("installer/macos/build_mac.sh")
        assert script.exists(), "macOS build_mac.sh missing"
        assert os.access(script, os.X_OK), "build_mac.sh is not executable"
