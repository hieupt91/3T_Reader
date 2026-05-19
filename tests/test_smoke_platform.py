"""Smoke tests for platform-layer and signing-layer OS independence."""
import sys
import types
import importlib
import pytest


# ---------------------------------------------------------------------------
# Platform paths
# ---------------------------------------------------------------------------

class TestPlatformPaths:
    def test_app_data_dir_returns_string(self):
        from packages.platform import get_app_data_dir
        result = get_app_data_dir()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_cache_dir_returns_string(self):
        from packages.platform import get_cache_dir
        result = get_cache_dir()
        assert isinstance(result, str)

    def test_log_dir_returns_string(self):
        from packages.platform import get_log_dir
        result = get_log_dir()
        assert isinstance(result, str)

    def test_no_hardcoded_windows_path_in_result(self):
        from packages.platform import get_app_data_dir
        result = get_app_data_dir()
        if sys.platform != "win32":
            assert "C:\\" not in result
            assert "System32" not in result


# ---------------------------------------------------------------------------
# Font resolver
# ---------------------------------------------------------------------------

class TestFontResolver:
    def test_get_vietnamese_font_path_is_none_or_str(self):
        from packages.platform.fonts import get_vietnamese_font_path
        result = get_vietnamese_font_path()
        assert result is None or isinstance(result, str)

    def test_font_path_exists_when_not_none(self):
        import os
        from packages.platform.fonts import get_vietnamese_font_path
        result = get_vietnamese_font_path()
        if result is not None:
            assert os.path.exists(result), f"Font path does not exist: {result}"

    def test_no_windows_font_path_on_macos(self):
        from packages.platform.fonts import get_vietnamese_font_path
        result = get_vietnamese_font_path()
        if sys.platform == "darwin" and result is not None:
            assert "Windows" not in result
            assert "System32" not in result


# ---------------------------------------------------------------------------
# Signing provider selection
# ---------------------------------------------------------------------------

class TestSigningProviderSelection:
    def test_get_signing_provider_returns_object(self):
        from packages.signing import get_signing_provider
        provider = get_signing_provider()
        assert provider is not None

    def test_provider_has_required_methods(self):
        from packages.signing import get_signing_provider
        provider = get_signing_provider()
        assert callable(getattr(provider, "detect_driver", None))
        assert callable(getattr(provider, "get_token_info", None))
        assert callable(getattr(provider, "sign_pdf", None))
        assert callable(getattr(provider, "get_last_error", None))

    def test_macos_provider_selected_on_darwin(self):
        if sys.platform != "darwin":
            pytest.skip("macOS only")
        from packages.signing import get_signing_provider
        from packages.signing.macos_provider import MacOSPkcs11Provider
        provider = get_signing_provider()
        assert isinstance(provider, MacOSPkcs11Provider)

    def test_windows_provider_selected_on_win32(self):
        if sys.platform != "win32":
            pytest.skip("Windows only")
        from packages.signing import get_signing_provider
        from packages.signing.windows_provider import WindowsPkcs11Provider
        provider = get_signing_provider()
        assert isinstance(provider, WindowsPkcs11Provider)

    def test_detect_driver_returns_none_without_token(self):
        from packages.signing import get_signing_provider
        provider = get_signing_provider()
        result = provider.detect_driver()
        # Without a physical USB token, result must be None
        assert result is None

    def test_get_last_error_is_string_after_detect(self):
        from packages.signing import get_signing_provider
        provider = get_signing_provider()
        provider.detect_driver()
        err = provider.get_last_error()
        assert isinstance(err, str)


# ---------------------------------------------------------------------------
# Shared signing utilities — pure Python, no hardware required
# ---------------------------------------------------------------------------

class TestSharedSigningUtils:
    def test_strip_accents(self):
        from packages.signing.shared import strip_accents
        assert strip_accents("Nguyễn Văn A") == "Nguyen Van A"
        assert strip_accents("Đỗ Thị Bình") == "Do Thi Binh"
        assert strip_accents("") == ""

    def test_extract_tax_code_10_digits(self):
        from packages.signing.shared import _extract_tax_code_from_text
        text = "CN=Nguyen Van A, SN=0312345678"
        result = _extract_tax_code_from_text(text)
        assert result == "0312345678"

    def test_extract_tax_code_with_branch(self):
        from packages.signing.shared import _extract_tax_code_from_text
        text = "MST: 0312345678-001"
        result = _extract_tax_code_from_text(text)
        assert result == "0312345678-001"

    def test_extract_tax_code_returns_none_when_absent(self):
        from packages.signing.shared import _extract_tax_code_from_text
        assert _extract_tax_code_from_text("no numbers here") is None

    def test_extract_signer_identity_returns_none_for_none(self):
        from packages.signing.shared import extract_signer_identity_from_der
        assert extract_signer_identity_from_der(None) is None

    def test_extract_signer_identity_returns_none_for_garbage(self):
        from packages.signing.shared import extract_signer_identity_from_der
        assert extract_signer_identity_from_der(b"\x00\x01\x02") is None


# ---------------------------------------------------------------------------
# PDF engine
# ---------------------------------------------------------------------------

class TestPdfEngine:
    def test_pdfium_engine_importable(self):
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        engine = PdfiumEngine()
        assert engine is not None

    def test_pdf_engine_default_is_pdfium(self):
        from packages.pdf_engine import get_pdf_engine
        engine = get_pdf_engine()
        from packages.pdf_engine.pdfium_engine import PdfiumEngine
        assert isinstance(engine, PdfiumEngine)


# ---------------------------------------------------------------------------
# Recent files — no OS path assumption
# ---------------------------------------------------------------------------

class TestRecentFiles:
    def test_load_recent_returns_list(self):
        from core.recent import load_recent
        result = load_recent()
        assert isinstance(result, list)
