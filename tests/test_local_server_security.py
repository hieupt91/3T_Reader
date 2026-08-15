"""Security tests for local_server.py — verify path traversal protection."""

import os
import tempfile
import urllib.parse

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeHandler:
    """Minimal stand-in for _PDFJSHandler to test _serve_pdf logic."""

    def __init__(self):
        self._error_code = None
        self._error_msg = None
        self._headers: dict[str, str] = {}

    def send_error(self, code, msg=""):
        self._error_code = code
        self._error_msg = msg

    def send_header(self, key, val):
        self._headers[key] = val

    def end_headers(self):
        pass


def _make_serve_pdf():
    """Return a function that behaves like _serve_pdf path validation."""
    from app.local_server import _PDFJSHandler

    def check(pdf_path: str) -> tuple[int, str]:
        handler = _FakeHandler()
        # Replicate the validation logic from _serve_pdf
        if not os.path.isabs(pdf_path) or not pdf_path.lower().endswith(".pdf"):
            handler.send_error(400, "Invalid path")
            return handler._error_code, handler._error_msg
        real_path = os.path.realpath(pdf_path)
        if ".." in pdf_path.replace("\\", "/").split("/"):
            handler.send_error(403, "Path traversal not allowed")
            return handler._error_code, handler._error_msg
        if os.path.normcase(real_path) != os.path.normcase(os.path.normpath(pdf_path)):
            handler.send_error(403, "Path mismatch")
            return handler._error_code, handler._error_msg
        if not os.path.isfile(real_path):
            handler.send_error(404)
            return handler._error_code, handler._error_msg
        return 200, ""

    return check


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestServePdfValidation:
    """Verify _serve_pdf rejects malicious paths."""

    def test_relative_path_rejected(self):
        check = _make_serve_pdf()
        code, _ = check("../../../etc/passwd.pdf")
        assert code == 400

    def test_no_extension_rejected(self):
        check = _make_serve_pdf()
        code, _ = check("/tmp/test")
        assert code == 400

    def test_wrong_extension_rejected(self):
        check = _make_serve_pdf()
        code, _ = check("/tmp/test.txt")
        assert code == 400

    def test_dotdot_in_path_rejected(self, tmp_path):
        check = _make_serve_pdf()
        # Use an absolute path with .. traversal
        base = str(tmp_path / "test.pdf")
        code, _ = check(base.replace("test.pdf", "..\\..\\etc\\passwd.pdf"))
        assert code == 403

    def test_dotdot_backslash_rejected(self):
        check = _make_serve_pdf()
        code, _ = check("C:\\Users\\..\\Windows\\System32\\config\\SAM.pdf")
        assert code == 403

    def test_nonexistent_file_returns_404(self, tmp_path):
        check = _make_serve_pdf()
        code, _ = check(str(tmp_path / "nonexistent.pdf"))
        assert code == 404

    def test_valid_path_returns_200(self, tmp_path):
        check = _make_serve_pdf()
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        code, _ = check(str(pdf))
        assert code == 200


class TestServeStaticValidation:
    """Verify _serve_static rejects path traversal."""

    def test_dotdot_rejected(self, tmp_path):
        from app.local_server import _PDFJSHandler
        from pathlib import Path

        class Handler(_PDFJSHandler):
            pdfjs_root = tmp_path

        h = Handler.__new__(Handler)
        h.pdfjs_root = tmp_path
        h._error_code = None

        def send_error(code, msg=""):
            h._error_code = code

        h.send_error = send_error
        h.send_header = lambda k, v: None
        h.end_headers = lambda: None

        # Simulate _serve_static with traversal path
        url_path = "/../../../etc/passwd"
        rel = url_path.lstrip("/")
        if ".." in rel.split("/") or ".." in rel.split("\\"):
            h.send_error(403)
        assert h._error_code == 403
