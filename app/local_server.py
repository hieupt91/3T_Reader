"""Local HTTP server that serves PDF.js and PDF files over 127.0.0.1.

ES modules (used by PDF.js 4+) cannot load from file:// origins in QtWebEngine
due to cross-origin restrictions. Serving via http://127.0.0.1 avoids this.
"""

import os
import socket
import threading
import urllib.parse
import http.server
import mimetypes
import sys
from pathlib import Path


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pdfjs_root() -> Path | None:
    """Return path to third_party/pdfjs regardless of frozen vs. dev context."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))
        exe = Path(sys.executable).resolve()
        candidates.append(exe.parent)
        candidates.append(exe.parent.parent / "Resources")
    else:
        candidates.append(Path(__file__).resolve().parents[1])
    for root in candidates:
        p = root / "third_party" / "pdfjs"
        if p.exists():
            return p
    return None


class _PDFJSHandler(http.server.BaseHTTPRequestHandler):
    """Handles:
      GET /pdf?p=<url-encoded-absolute-path>  → streams the PDF file
      GET /...                                → serves static files from pdfjs_root
    """

    pdfjs_root: Path = Path(".")  # set by factory

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/pdf":
            self._serve_pdf(parsed.query)
        else:
            self._serve_static(path)

    def _serve_pdf(self, query: str):
        params = urllib.parse.parse_qs(query)
        raw = params.get("p", [None])[0]
        if not raw:
            self.send_error(400, "Missing ?p= parameter")
            return
        pdf_path = urllib.parse.unquote(raw)
        if not os.path.isabs(pdf_path) or not pdf_path.lower().endswith(".pdf"):
            self.send_error(400, "Invalid path")
            return
        if not os.path.isfile(pdf_path):
            self.send_error(404)
            return
        try:
            with open(pdf_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            self.send_error(500)

    def _serve_static(self, url_path: str):
        rel = url_path.lstrip("/")
        file_path = self.pdfjs_root / rel
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if not file_path.exists():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        # Windows registry may map .mjs/.js to text/plain — force correct MIME
        if file_path.suffix.lower() in {".mjs", ".js"}:
            mime = "text/javascript"
        elif not mime:
            mime = "application/octet-stream"
        try:
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            self.send_error(500)

    def log_message(self, *args):
        pass  # suppress access log


class LocalPDFJSServer:
    """Singleton-like local HTTP server for serving PDF.js over 127.0.0.1."""

    _instance: "LocalPDFJSServer | None" = None

    def __init__(self):
        self._port: int = 0
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._root: Path | None = _pdfjs_root()

    def start(self):
        if self._server:
            return
        if not self._root:
            return

        root = self._root

        class Handler(_PDFJSHandler):
            pdfjs_root = root

        self._port = _find_free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self._port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="pdfjs-server",
        )
        self._thread.start()

    def viewer_url(self, pdf_path: str, *, page: int = 1, zoom: str = "page-width", pagemode: str | None = None) -> str | None:
        if not self._server or not self._root:
            return None
        encoded_path = urllib.parse.quote(os.path.abspath(pdf_path))
        pdf_url = f"http://127.0.0.1:{self._port}/pdf?p={encoded_path}"
        encoded_pdf_url = urllib.parse.quote(pdf_url, safe="")
        url = f"http://127.0.0.1:{self._port}/web/viewer.html?file={encoded_pdf_url}#page={page}"
        if zoom:
            url += f"&zoom={zoom}"
        if pagemode:
            url += f"&pagemode={pagemode}"
        return url

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None

    @classmethod
    def get(cls) -> "LocalPDFJSServer":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.start()
        return cls._instance
