"""Tests for local_server.py — path traversal protection."""

from __future__ import annotations

import os
import threading
import tempfile
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _serve_pdf path traversal tests
# ---------------------------------------------------------------------------

class TestServePDFSecurity:
    """Verify _serve_pdf rejects path traversal attempts."""

    def _make_handler(self):
        """Create a minimal handler instance for testing."""
        from app.local_server import _PDFJSHandler
        handler = _PDFJSHandler.__new__(_PDFJSHandler)
        handler.send_error = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()
        handler.headers = {}
        handler.pdfjs_root = Path(tempfile.mkdtemp())
        return handler

    def test_reject_dot_dot_in_path(self):
        handler = self._make_handler()
        handler._serve_pdf("p=C:/Users/secret/../other/file.pdf")
        handler.send_error.assert_called_once()
        args = handler.send_error.call_args[0]
        assert args[0] == 403

    def test_reject_dot_dot_slash(self):
        """Relative path with .. is rejected as 400 (not absolute) before traversal check."""
        handler = self._make_handler()
        handler._serve_pdf("p=../../../etc/passwd.pdf")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 400

    def test_reject_relative_path(self):
        handler = self._make_handler()
        handler._serve_pdf("p=relative/path.pdf")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 400

    def test_reject_non_pdf_extension(self):
        handler = self._make_handler()
        handler._serve_pdf("p=C:/Users/test.txt")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 400

    def test_reject_missing_param(self):
        handler = self._make_handler()
        handler._serve_pdf("")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 400

    def test_reject_nonexistent_file(self, tmp_path):
        handler = self._make_handler()
        fake_path = str(tmp_path / "nonexistent.pdf")
        handler._serve_pdf(f"p={fake_path}")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 404

    def test_reject_unregistered_pdf_when_registry_enabled(self, tmp_path):
        handler = self._make_handler()
        handler.allowed_pdf_paths = set()
        handler.allowed_pdf_paths_lock = threading.RLock()
        pdf_path = tmp_path / "registered-only.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

        handler._serve_pdf("p=" + urllib.parse.quote(str(pdf_path)))

        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 403

    def test_allow_registered_pdf_when_registry_enabled(self, tmp_path):
        handler = self._make_handler()
        pdf_path = tmp_path / "allowed.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
        handler.allowed_pdf_paths = {
            handler._normalise_allowed_path_key(str(pdf_path))
        }
        handler.allowed_pdf_paths_lock = threading.RLock()
        handler._serve_pdf_file = MagicMock()

        with patch.object(handler, "_has_signature_field_cached", return_value=False):
            handler._serve_pdf("p=" + urllib.parse.quote(str(pdf_path)))

        handler.send_error.assert_not_called()
        handler._serve_pdf_file.assert_called_once()


# ---------------------------------------------------------------------------
# _serve_static path traversal tests
# ---------------------------------------------------------------------------

class TestServeStaticSecurity:
    """Verify _serve_static rejects path traversal attempts."""

    def _make_handler(self, root: Path):
        from app.local_server import _PDFJSHandler
        handler = _PDFJSHandler.__new__(_PDFJSHandler)
        handler.send_error = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()
        handler.headers = {}
        handler.pdfjs_root = root
        return handler

    def test_reject_dot_dot_slash(self, tmp_path):
        handler = self._make_handler(tmp_path)
        handler._serve_static("/../../../etc/passwd")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 403

    def test_reject_dot_dot_backslash(self, tmp_path):
        handler = self._make_handler(tmp_path)
        handler._serve_static("/..\\..\\..\\windows\\system32\\config\\sam")
        handler.send_error.assert_called_once()
        assert handler.send_error.call_args[0][0] == 403

    def test_serve_valid_file(self, tmp_path):
        """Valid file within pdfjs_root should be served (not rejected with 403)."""
        (tmp_path / "test.js").write_text("console.log('ok');")
        handler = self._make_handler(tmp_path)
        handler._serve_static("/test.js")
        # Should NOT have called send_error with 403
        for call in handler.send_error.call_args_list:
            assert call[0][0] != 403


# ---------------------------------------------------------------------------
# Integration: viewer_url produces valid URLs
# ---------------------------------------------------------------------------

class TestViewerURL:
    def test_viewer_url_encodes_path(self, tmp_path):
        from app.local_server import LocalPDFJSServer
        server = LocalPDFJSServer.__new__(LocalPDFJSServer)
        server._server = MagicMock()
        server._root = tmp_path
        server._port = 8765
        url = server.viewer_url(str(tmp_path / "test file.pdf"))
        assert "127.0.0.1:8765" in url
        # The space is encoded as %20 (possibly double-encoded as %2520)
        assert "test" in url and "file.pdf" in url

    def test_viewer_url_registers_pdf_path(self, tmp_path):
        from app.local_server import LocalPDFJSServer, _PDFJSHandler
        server = LocalPDFJSServer.__new__(LocalPDFJSServer)
        server._server = MagicMock()
        server._root = tmp_path
        server._port = 8765
        pdf_path = tmp_path / "session.pdf"

        url = server.viewer_url(str(pdf_path))

        assert url
        key = _PDFJSHandler._normalise_allowed_path_key(str(pdf_path))
        assert key in server._allowed_pdf_paths
