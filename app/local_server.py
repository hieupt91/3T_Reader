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
import io
import json
from collections import OrderedDict
from pathlib import Path


# Runtime polyfill loaded from shared assets/js/polyfill.js (single source of truth).
from app.js_loader import load_js as _load_js
_PDFJS_RUNTIME_POLYFILL = _load_js("polyfill.js").encode("utf-8")


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

    ThreadingHTTPServer dispatches every request on its own thread, so the
    class-level caches must be guarded by a lock. We hold the lock only across
    dict mutations, never across the heavy normalization/IO work, so concurrent
    requests for *different* files still proceed in parallel.
    """

    pdfjs_root: Path = Path(".")  # set by factory
    allowed_pdf_paths: set[str] | None = None  # set by factory; None keeps direct unit tests simple
    allowed_pdf_paths_lock = threading.RLock()
    display_cache: OrderedDict = OrderedDict()  # (path,mtime,size) -> bytes, LRU
    signature_probe_cache: OrderedDict = OrderedDict()  # (path,mtime,size) -> bool, LRU
    signature_click_target_cache: OrderedDict = OrderedDict()  # (path,mtime,size) -> list[dict], LRU
    _MAX_CACHE_ENTRIES = 6
    _cache_lock = threading.RLock()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/pdf":
            self._serve_pdf(parsed.query)
        elif path == "/sigmeta":
            self._serve_signature_metadata(parsed.query)
        else:
            self._serve_static(path)

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/pdf":
            self._serve_pdf(parsed.query, send_body=False)
        else:
            self.send_error(405)

    def _serve_pdf(self, query: str, *, send_body: bool = True):
        params = urllib.parse.parse_qs(query)
        raw = params.get("p", [None])[0]
        if not raw:
            self.send_error(400, "Missing ?p= parameter")
            return
        pdf_path = urllib.parse.unquote(raw)
        if not os.path.isabs(pdf_path) or not pdf_path.lower().endswith(".pdf"):
            self.send_error(400, "Invalid path")
            return
        # Path traversal protection: resolve to canonical real path and
        # reject if the resolved path differs from the requested one (e.g.
        # due to ".." segments or symlink tricks).
        real_path = os.path.realpath(pdf_path)
        if ".." in pdf_path.replace("\\", "/").split("/"):
            self.send_error(403, "Path traversal not allowed")
            return
        if os.path.normcase(real_path) != os.path.normcase(os.path.normpath(pdf_path)):
            self.send_error(403, "Path mismatch")
            return
        pdf_path = real_path
        if not self._is_registered_pdf_path(pdf_path):
            self.send_error(403, "PDF path is not registered for this viewer session")
            return
        if not os.path.isfile(pdf_path):
            self.send_error(404)
            return
        try:
            # For files > 30MB, skip normalisation to save RAM and use Range requests
            file_size = os.path.getsize(pdf_path)
            if file_size > 30 * 1024 * 1024:
                self._serve_pdf_file(pdf_path, send_body=send_body)
            else:
                data = self._read_pdf_for_display(pdf_path)
                self._serve_pdf_bytes(data, send_body=send_body)
        except OSError:
            self.send_error(500)

    def _serve_signature_metadata(self, query: str):
        params = urllib.parse.parse_qs(query)
        raw = params.get("p", [None])[0]
        if not raw:
            self.send_error(400, "Missing ?p= parameter")
            return
        pdf_path = urllib.parse.unquote(raw)
        real_path = os.path.realpath(pdf_path)
        if not os.path.isabs(pdf_path) or not pdf_path.lower().endswith(".pdf"):
            self.send_error(400, "Invalid path")
            return
        if os.path.normcase(real_path) != os.path.normcase(os.path.normpath(pdf_path)):
            self.send_error(403, "Path mismatch")
            return
        if not self._is_registered_pdf_path(real_path):
            self.send_error(403, "PDF path is not registered for this viewer session")
            return
        if not os.path.isfile(real_path):
            self.send_error(404)
            return
        try:
            payload = json.dumps({"targets": self._read_signature_click_targets(real_path)}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)
        except OSError:
            self.send_error(500)

    @staticmethod
    def _normalise_allowed_path_key(pdf_path: str) -> str:
        return os.path.normcase(os.path.normpath(os.path.realpath(pdf_path)))

    def _is_registered_pdf_path(self, pdf_path: str) -> bool:
        allowed = getattr(self, "allowed_pdf_paths", None)
        if allowed is None:
            return True
        key = self._normalise_allowed_path_key(pdf_path)
        lock = getattr(self, "allowed_pdf_paths_lock", None)
        if lock is None:
            return key in allowed
        with lock:
            return key in allowed

    def _parse_range_header(self, content_length: int) -> tuple[int, int, int] | None:
        range_header = self.headers.get("Range", "")
        if not range_header.startswith("bytes="):
            return 200, 0, max(0, content_length - 1)
        start = 0
        end = content_length - 1
        try:
            spec = range_header.split("=", 1)[1].split(",", 1)[0].strip()
            if spec.startswith("-"):
                suffix = int(spec[1:] or "0")
                start = max(0, content_length - suffix)
            else:
                left, _, right = spec.partition("-")
                start = int(left or "0")
                if right:
                    end = min(content_length - 1, int(right))
        except ValueError:
            self.send_error(400, "Invalid Range header")
            return None
        if start < 0 or start >= content_length or end < start:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{content_length}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return None
        return 206, start, end

    def _serve_pdf_bytes(self, data: bytes, *, send_body: bool = True):
        file_size = len(data)
        parsed_range = self._parse_range_header(file_size)
        if parsed_range is None:
            return
        status, start, end = parsed_range
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        if send_body:
            self.wfile.write(data[start:end + 1])

    def _serve_pdf_file(self, pdf_path: str, *, send_body: bool = True):
        file_size = os.path.getsize(pdf_path)
        parsed_range = self._parse_range_header(file_size)
        if parsed_range is None:
            return
        status, start, end = parsed_range
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()

        if not send_body:
            return

        chunk_size = 1024 * 1024
        with open(pdf_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    @classmethod
    def _has_signature_field_cached(cls, pdf_path: str) -> bool:
        stat = os.stat(pdf_path)
        cache_key = (pdf_path, stat.st_mtime_ns, stat.st_size)
        with cls._cache_lock:
            cached = cls.signature_probe_cache.get(cache_key)
            if cached is not None:
                cls.signature_probe_cache.move_to_end(cache_key)
                return bool(cached)

        # Probe outside the lock — pikepdf.Pdf.open or the byte-scan can take
        # tens of ms on big files; we don't want to block other threads.
        result = _pdf_has_signature_field(pdf_path)

        with cls._cache_lock:
            cls.signature_probe_cache[cache_key] = result
            while len(cls.signature_probe_cache) > cls._MAX_CACHE_ENTRIES:
                cls.signature_probe_cache.popitem(last=False)
        return result

    def _read_pdf_for_display(self, pdf_path: str) -> bytes:
        stat = os.stat(pdf_path)
        cache_key = (pdf_path, stat.st_mtime_ns, stat.st_size)
        with self._cache_lock:
            cached = self.display_cache.get(cache_key)
            if cached is not None:
                self.display_cache.move_to_end(cache_key)
                return cached

        # Heavy work outside the lock — read + normalize a large PDF can take
        # seconds; holding the lock would serialise unrelated requests.
        with open(pdf_path, "rb") as f:
            data = f.read()
        display_data = _normalise_pdfjs_appearance_boxes(pdf_path, data)

        with self._cache_lock:
            self.display_cache[cache_key] = display_data
            while len(self.display_cache) > self._MAX_CACHE_ENTRIES:
                self.display_cache.popitem(last=False)
        return display_data

    def _read_signature_click_targets(self, pdf_path: str) -> list[dict]:
        stat = os.stat(pdf_path)
        cache_key = (pdf_path, stat.st_mtime_ns, stat.st_size)
        with self._cache_lock:
            cached = self.signature_click_target_cache.get(cache_key)
            if cached is not None:
                self.signature_click_target_cache.move_to_end(cache_key)
                return cached

        targets = _collect_signature_click_targets(pdf_path)

        with self._cache_lock:
            self.signature_click_target_cache[cache_key] = targets
            while len(self.signature_click_target_cache) > self._MAX_CACHE_ENTRIES:
                self.signature_click_target_cache.popitem(last=False)
        return targets

    _ALLOWED_STATIC_EXTENSIONS = frozenset({
        ".html", ".js", ".mjs", ".css", ".wasm", ".properties",
        ".svg", ".png", ".json", ".map", ".ico",
        ".bcmap", ".ftl", ".pfb", ".ttf", ".woff", ".woff2",
    })

    def _serve_static(self, url_path: str):
        rel = url_path.lstrip("/")
        # Path traversal protection: resolve the canonical path and verify
        # it stays within pdfjs_root. Reject any ".." segments outright.
        if ".." in rel.split("/") or ".." in rel.split("\\"):
            self.send_error(403)
            return
        file_path = (self.pdfjs_root / rel).resolve()
        if not str(file_path).startswith(str(self.pdfjs_root.resolve())):
            self.send_error(403)
            return
        if file_path.is_dir():
            file_path = file_path / "index.html"
        if not file_path.exists():
            self.send_error(404)
            return
        # Only serve whitelisted file types to prevent exposing source maps,
        # debug files, or other sensitive assets.
        if file_path.suffix.lower() not in self._ALLOWED_STATIC_EXTENSIONS:
            self.send_error(403)
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        # Windows registry may map .mjs/.js to text/plain — force correct MIME
        if file_path.suffix.lower() in {".mjs", ".js"}:
            mime = "text/javascript"
        elif not mime:
            mime = "application/octet-stream"
        try:
            data = file_path.read_bytes()
            if file_path.suffix.lower() in {".mjs", ".js"}:
                data = _PDFJS_RUNTIME_POLYFILL + b"\n" + data
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
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
        self._allowed_pdf_paths: set[str] = set()
        self._allowed_pdf_paths_lock = threading.RLock()
        self._path_versions: dict[str, int] = {}

    def start(self):
        if self._server:
            return
        if not self._root:
            return

        root = self._root

        class Handler(_PDFJSHandler):
            pdfjs_root = root
            allowed_pdf_paths = self._allowed_pdf_paths
            allowed_pdf_paths_lock = self._allowed_pdf_paths_lock

        self._port = _find_free_port()
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", self._port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="pdfjs-server",
        )
        self._thread.start()

    def viewer_url(self, pdf_path: str, *, page: int = 1, zoom: str = "page-width", pagemode: str | None = None) -> str | None:
        if not self._server or not self._root:
            return None
        abs_path = self.register_pdf(pdf_path)
        encoded_path = urllib.parse.quote(abs_path)
        cache_key = self.cache_bust_token(abs_path)
        pdf_url = f"http://127.0.0.1:{self._port}/pdf?p={encoded_path}&v={cache_key}"
        encoded_pdf_url = urllib.parse.quote(pdf_url, safe="")
        sigmeta_url = f"http://127.0.0.1:{self._port}/sigmeta?p={encoded_path}&v={cache_key}"
        encoded_sigmeta_url = urllib.parse.quote(sigmeta_url, safe="")
        viewer_opts = (
            f"file={encoded_pdf_url}"
            f"&sigmeta={encoded_sigmeta_url}"
            "&disableStream=true"
            "&disableAutoFetch=true"
            "&disableRange=false"
            "&rangeChunkSize=1048576"
            "&annotationMode=2"
            "&renderInteractiveForms=false"
        )
        url = f"http://127.0.0.1:{self._port}/web/viewer.html?{viewer_opts}#page={page}"
        if zoom:
            url += f"&zoom={zoom}"
        if pagemode:
            url += f"&pagemode={pagemode}"
        return url

    def register_pdf(self, pdf_path: str) -> str:
        abs_path = os.path.realpath(os.path.abspath(pdf_path))
        key = _PDFJSHandler._normalise_allowed_path_key(abs_path)
        if not hasattr(self, "_allowed_pdf_paths_lock"):
            self._allowed_pdf_paths_lock = threading.RLock()
        if not hasattr(self, "_allowed_pdf_paths"):
            self._allowed_pdf_paths = set()
        with self._allowed_pdf_paths_lock:
            self._allowed_pdf_paths.add(key)
        return abs_path

    def cache_bust_token(self, pdf_path: str) -> str:
        abs_path = os.path.realpath(os.path.abspath(pdf_path))
        key = _PDFJSHandler._normalise_allowed_path_key(abs_path)
        version = int(self._path_versions.get(key, 0))
        try:
            stat = os.stat(abs_path)
            return f"{stat.st_mtime_ns}-{stat.st_size}-{version}"
        except OSError:
            return f"0-0-{version}"

    def invalidate_pdf_cache(self, pdf_path: str) -> None:
        abs_path = os.path.realpath(os.path.abspath(pdf_path))
        path_key = _PDFJSHandler._normalise_allowed_path_key(abs_path)
        self._path_versions[path_key] = int(self._path_versions.get(path_key, 0)) + 1
        with _PDFJSHandler._cache_lock:
            for cache_name in (
                "display_cache",
                "signature_probe_cache",
                "signature_click_target_cache",
            ):
                cache = getattr(_PDFJSHandler, cache_name, None)
                if not cache:
                    continue
                stale_keys = [
                    key
                    for key in list(cache.keys())
                    if key and _PDFJSHandler._normalise_allowed_path_key(key[0]) == path_key
                ]
                for key in stale_keys:
                    cache.pop(key, None)

    def unregister_pdf(self, pdf_path: str) -> None:
        key = _PDFJSHandler._normalise_allowed_path_key(pdf_path)
        if not hasattr(self, "_allowed_pdf_paths_lock") or not hasattr(self, "_allowed_pdf_paths"):
            return
        with self._allowed_pdf_paths_lock:
            self._allowed_pdf_paths.discard(key)

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None
        with self._allowed_pdf_paths_lock:
            self._allowed_pdf_paths.clear()

    @classmethod
    def get(cls) -> "LocalPDFJSServer":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.start()
        return cls._instance


def _pdf_has_signature_field(pdf_path: str) -> bool:
    """Cheap pre-check: does the PDF declare any /Sig field in AcroForm?

    This walks only the document root + AcroForm.Fields list (a handful of
    object lookups), avoiding the per-page annotation iteration that dominates
    cost on large PDFs.
    """
    try:
        if os.path.getsize(pdf_path) > 64 * 1024 * 1024:
            return _pdf_has_signature_marker_fast(pdf_path)

        import pikepdf
        with pikepdf.Pdf.open(pdf_path) as pdf:
            acro = pdf.Root.get("/AcroForm")
            if acro is None:
                return False
            fields = acro.get("/Fields")
            if not fields:
                return False
            return _field_array_has_signature(fields)
    except Exception:
        # If we can't even probe the PDF, fall back to the full path so
        # normalization gets a chance to recover or bail.
        return True


def _pdf_has_signature_marker_fast(pdf_path: str) -> bool:
    """Fast large-file signature hint without parsing the whole PDF.

    pikepdf may scan the full file to locate xref data; on 700MB+ PDFs that
    blocks the first byte served to PDF.js. For large files, prefer fast loading
    and only normalize if common AcroForm signature markers are visible near the
    beginning or end of the file.
    """
    markers = (b"/FT/Sig", b"/FT /Sig", b"/SigFlags")
    scan_size = 4 * 1024 * 1024
    try:
        size = os.path.getsize(pdf_path)
        with open(pdf_path, "rb") as f:
            head = f.read(min(scan_size, size))
            if any(marker in head for marker in markers):
                return True
            if size > scan_size:
                f.seek(max(0, size - scan_size))
                tail = f.read(scan_size)
                if any(marker in tail for marker in markers):
                    return True
        return False
    except Exception:
        return False


def _field_array_has_signature(fields_arr) -> bool:
    for field in fields_arr:
        try:
            field_obj = field.get_object() if hasattr(field, "get_object") else field
            if field_obj.get("/FT") == "/Sig":
                return True
            kids = field_obj.get("/Kids")
            if kids and _field_array_has_signature(kids):
                return True
        except Exception:
            continue
    return False


def _normalise_pdfjs_appearance_boxes_legacy(pdf_path: str, original_data: bytes) -> bytes:
    """Fix inverted BBox values in annotation appearance streams.

    Signature widgets are kept intact — PDF.js is configured with
    ``renderForms=false`` so it renders the embedded appearance stream
    rather than interactive form inputs.  This ensures digital
    signatures remain visible when re-opening a signed PDF.
    """
    try:
        import pikepdf

        changed = False
        with pikepdf.Pdf.open(pdf_path) as pdf:
            for page in pdf.pages:
                annots = page.obj.get("/Annots")
                if not annots:
                    continue
                kept_annots = []
                for annot in annots:
                    annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    if _is_signature_widget(annot_obj):
                        kept_annots.append(annot)
                        continue

                    ap = annot_obj.get("/AP")
                    if not ap:
                        kept_annots.append(annot)
                        continue
                    normal = ap.get("/N")
                    if normal is None:
                        kept_annots.append(annot)
                        continue
                    streams = []
                    if isinstance(normal, pikepdf.Stream):
                        streams.append(normal)
                    elif isinstance(normal, pikepdf.Dictionary):
                        streams.extend(
                            value
                            for value in normal.values()
                            if isinstance(value, pikepdf.Stream)
                        )
                    for stream in streams:
                        bbox = stream.get("/BBox")
                        if not bbox or len(bbox) != 4:
                            continue
                        x1, y1, x2, y2 = [float(v) for v in bbox]
                        if x1 <= x2 and y1 <= y2:
                            continue
                        stream["/BBox"] = pikepdf.Array(
                            [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
                        )
                        changed = True
                    kept_annots.append(annot)

                if len(kept_annots) != len(annots):
                    if kept_annots:
                        page.obj["/Annots"] = pikepdf.Array(kept_annots)
                    elif "/Annots" in page.obj:
                            del page.obj["/Annots"]
                    changed = True

            if not changed:
                return original_data
            out = io.BytesIO()
            pdf.save(out)
            return out.getvalue()
    except Exception:
        return original_data


def _normalise_pdfjs_appearance_boxes(pdf_path: str, original_data: bytes) -> bytes:
    """Serve a display-friendly copy that preserves signed widget appearances.

    PDF.js in Qt WebEngine can fail to paint some signed signature widgets
    even when the same PDF renders correctly in other viewers. For the
    internal viewer only, flatten signature widget appearances into page
    content and strip those fields from AcroForm so PDF.js does not replace
    them with empty interactive widgets that our CSS later hides.
    """
    try:
        import pikepdf

        changed = False
        with pikepdf.Pdf.open(pdf_path) as pdf:
            signature_overlays: dict[int, list[dict]] = {}
            removed_signature_widgets = 0
            for page_index, page in enumerate(pdf.pages, start=1):
                annots = page.obj.get("/Annots")
                if not annots:
                    continue
                kept_annots = []
                for annot_idx, annot in enumerate(annots):
                    annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    if _is_signature_widget(annot_obj):
                        is_signed = annot_obj.get("/V") is not None
                        if not is_signed:
                            parent = annot_obj.get("/Parent")
                            parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
                            if parent_obj is not None:
                                is_signed = parent_obj.get("/V") is not None

                        painted = False
                        if is_signed:
                            painted = _paint_signature_widget_appearance(
                                pdf,
                                page,
                                annot_obj,
                                f"SigAP_{page_index}_{annot_idx}",
                            )

                        if not painted and not is_signed:
                            if (overlay := _signature_overlay_from_annot(annot_obj)) is not None:
                                signature_overlays.setdefault(page_index, []).append(overlay)

                        removed_signature_widgets += 1
                        changed = True
                        continue

                    ap = annot_obj.get("/AP")
                    if not ap:
                        kept_annots.append(annot)
                        continue
                    normal = ap.get("/N")
                    if normal is None:
                        kept_annots.append(annot)
                        continue
                    streams = []
                    if isinstance(normal, pikepdf.Stream):
                        streams.append(normal)
                    elif isinstance(normal, pikepdf.Dictionary):
                        streams.extend(
                            value
                            for value in normal.values()
                            if isinstance(value, pikepdf.Stream)
                        )
                    for stream in streams:
                        bbox = stream.get("/BBox")
                        if not bbox or len(bbox) != 4:
                            continue
                        x1, y1, x2, y2 = [float(v) for v in bbox]
                        if x1 <= x2 and y1 <= y2:
                            continue
                        stream["/BBox"] = pikepdf.Array(
                            [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
                        )
                        changed = True
                    kept_annots.append(annot)

                if len(kept_annots) != len(annots):
                    if kept_annots:
                        page.obj["/Annots"] = pikepdf.Array(kept_annots)
                    elif "/Annots" in page.obj:
                        del page.obj["/Annots"]
                    changed = True

            for page_index, overlays in signature_overlays.items():
                page = pdf.pages[page_index - 1]
                width, height = _page_size(page)
                overlay_pdf_bytes = _build_signature_display_overlay(width, height, overlays)
                if not overlay_pdf_bytes:
                    overlay_pdf_bytes = _build_signature_display_overlay_bitmap(width, height, overlays)
                if not overlay_pdf_bytes:
                    overlay_pdf_bytes = _build_signature_display_overlay_ascii(width, height, overlays)
                if not overlay_pdf_bytes:
                    continue
                with pikepdf.Pdf.open(io.BytesIO(overlay_pdf_bytes)) as overlay_pdf:
                    page.add_overlay(overlay_pdf.pages[0])
                changed = True

            if removed_signature_widgets:
                try:
                    root = pdf.Root
                    acro = root.get("/AcroForm")
                    if acro is not None:
                        fields_arr = acro.get("/Fields")
                        if fields_arr is not None:
                            kept_fields, changed_fields = _strip_signature_fields_all(fields_arr)
                            if changed_fields:
                                changed = True
                                if kept_fields:
                                    acro["/Fields"] = pikepdf.Array(kept_fields)
                                elif "/Fields" in acro:
                                    del acro["/Fields"]
                except Exception:
                    pass

            if not changed:
                return original_data
            out = io.BytesIO()
            pdf.save(out)
            return out.getvalue()
    except Exception:
        return original_data


def _is_signature_widget(annot) -> bool:
    try:
        if annot.get("/Subtype") != "/Widget":
            return False
        parent = annot.get("/Parent")
        parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
        return (
            str(annot.get("/FT") or "") == "/Sig"
            or annot.get("/V") is not None
            or (parent_obj is not None and str(parent_obj.get("/FT") or "") == "/Sig")
            or (parent_obj is not None and parent_obj.get("/V") is not None)
        )
    except Exception:
        return False


def _signature_field_name(annot) -> str | None:
    try:
        name = annot.get("/T")
        if name is not None:
            return str(name)
        parent = annot.get("/Parent")
        parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
        if parent_obj is not None:
            parent_name = parent_obj.get("/T")
            if parent_name is not None:
                return str(parent_name)
    except Exception:
        return None
    return None


def _signature_rect(obj) -> list[float] | None:
    try:
        rect = [float(v) for v in obj.get("/Rect") or []]
        if len(rect) != 4:
            return None
        left, bottom, right, top = (
            min(rect[0], rect[2]),
            min(rect[1], rect[3]),
            max(rect[0], rect[2]),
            max(rect[1], rect[3]),
        )
        if right - left < 1 or top - bottom < 1:
            return None
        return [left, bottom, right, top]
    except Exception:
        return None


def _pdf_obj_ref_key(obj) -> tuple[int, int] | None:
    try:
        objgen = getattr(obj, "objgen", None)
        if objgen and len(objgen) == 2:
            return int(objgen[0]), int(objgen[1])
    except Exception:
        return None
    return None


def _signature_appearance_stream(annot):
    try:
        ap = annot.get("/AP")
        normal = ap.get("/N") if ap else None
        if normal is None:
            return None
        if hasattr(normal, "read_bytes"):
            return normal
        if hasattr(normal, "items"):
            for key, value in normal.items():
                if str(key) == "/Off":
                    continue
                if hasattr(value, "read_bytes"):
                    return value
            for value in normal.values():
                if hasattr(value, "read_bytes"):
                    return value
    except Exception:
        return None
    return None


def _signature_appearance_bbox_is_normal(annot) -> bool:
    try:
        stream = _signature_appearance_stream(annot)
        if stream is None:
            return False
        bbox = stream.get("/BBox")
        if not bbox or len(bbox) != 4:
            return False
        x1, y1, x2, y2 = [float(v) for v in bbox]
        return x1 < x2 and y1 < y2
    except Exception:
        return False


def _paint_signature_widget_appearance(pdf, page, annot, resource_name: str) -> bool:
    """Flatten a signed widget appearance into the display-only PDF copy."""
    try:
        import pikepdf

        stream = _signature_appearance_stream(annot)
        if stream is None:
            return False
        rect = [float(v) for v in annot.get("/Rect")]
        if len(rect) != 4:
            return False
        left, bottom, right, top = (
            min(rect[0], rect[2]),
            min(rect[1], rect[3]),
            max(rect[0], rect[2]),
            max(rect[1], rect[3]),
        )
        width = right - left
        height = top - bottom
        if width <= 0 or height <= 0:
            return False

        bbox = stream.get("/BBox")
        if bbox and len(bbox) == 4:
            bx0, by0, bx1, by1 = [float(v) for v in bbox]
            bx0, bx1 = sorted((bx0, bx1))
            by0, by1 = sorted((by0, by1))
            bbox_w = (bx1 - bx0) or width
            bbox_h = (by1 - by0) or height
        else:
            bx0, by0, bbox_w, bbox_h = 0.0, 0.0, width, height

        sx = width / bbox_w
        sy = height / bbox_h
        tx = left - bx0 * sx
        ty = bottom - by0 * sy

        resources = page.obj.get("/Resources")
        if resources is None:
            resources = pikepdf.Dictionary()
            page.obj["/Resources"] = resources
        xobjects = resources.get("/XObject")
        if xobjects is None:
            xobjects = pikepdf.Dictionary()
            resources["/XObject"] = xobjects
        name = pikepdf.Name("/" + "".join(ch if ch.isalnum() else "_" for ch in resource_name))
        if hasattr(stream, "read_raw_bytes"):
            stream_bytes = bytes(stream.read_raw_bytes())
            stream_copy = pikepdf.Stream(pdf, stream_bytes)
            preserve_keys = {
                "/Type", "/Subtype", "/FormType", "/Matrix", "/Resources",
                "/Group", "/OC", "/StructParent", "/Metadata",
                "/Filter", "/DecodeParms",
            }
        else:
            stream_bytes = bytes(stream.read_bytes())
            stream_copy = pikepdf.Stream(pdf, stream_bytes)
            preserve_keys = {
                "/Type", "/Subtype", "/FormType", "/Matrix", "/Resources",
                "/Group", "/OC", "/StructParent", "/Metadata",
            }
        for key, value in stream.items():
            if str(key) in {"/Length", "/BBox"}:
                continue
            if str(key) not in preserve_keys:
                continue
            stream_copy[key] = value
        stream_copy["/BBox"] = pikepdf.Array([0.0, 0.0, bbox_w, bbox_h])
        xobjects[name] = stream_copy

        content = (
            f"q\n{sx:.8f} 0 0 {sy:.8f} {tx:.8f} {ty:.8f} cm\n"
            f"{name} Do\nQ\n"
        ).encode("ascii")
        new_stream = pikepdf.Stream(pdf, content)
        existing = page.obj.get("/Contents")
        if existing is None:
            page.obj["/Contents"] = new_stream
        elif isinstance(existing, pikepdf.Array):
            existing.append(new_stream)
        else:
            page.obj["/Contents"] = pikepdf.Array([existing, new_stream])
        return True
    except Exception:
        return False


def _strip_signature_fields(fields_arr, removed_names: set[str]) -> tuple[list, bool]:
    kept = []
    changed = False
    for field in fields_arr:
        try:
            field_obj = field.get_object() if hasattr(field, "get_object") else field
            name = field_obj.get("/T")
            name_text = str(name) if name is not None else None
            is_sig = field_obj.get("/FT") == "/Sig"
            matches_removed = not removed_names or (name_text in removed_names)
            if is_sig and matches_removed:
                changed = True
                continue

            kids = field_obj.get("/Kids")
            if kids:
                child_kept, child_changed = _strip_signature_fields(kids, removed_names)
                if child_changed:
                    import pikepdf

                    changed = True
                    if child_kept:
                        field_obj["/Kids"] = pikepdf.Array(child_kept)
                    elif "/Kids" in field_obj:
                        del field_obj["/Kids"]
            kept.append(field)
        except Exception:
            kept.append(field)
    return kept, changed


def _strip_signature_fields_all(fields_arr) -> tuple[list, bool]:
    kept = []
    changed = False
    for field in fields_arr:
        try:
            field_obj = field.get_object() if hasattr(field, "get_object") else field
            is_sig = (
                str(field_obj.get("/FT") or "") == "/Sig"
                or field_obj.get("/V") is not None
            )
            parent = field_obj.get("/Parent")
            parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
            if parent_obj is not None:
                is_sig = (
                    is_sig
                    or str(parent_obj.get("/FT") or "") == "/Sig"
                    or parent_obj.get("/V") is not None
                )
            if is_sig:
                changed = True
                continue

            kids = field_obj.get("/Kids")
            if kids:
                child_kept, child_changed = _strip_signature_fields_all(kids)
                if child_changed:
                    import pikepdf

                    changed = True
                    if child_kept:
                        field_obj["/Kids"] = pikepdf.Array(child_kept)
                    elif "/Kids" in field_obj:
                        del field_obj["/Kids"]
            kept.append(field)
        except Exception:
            kept.append(field)
    return kept, changed


def _signature_overlay_from_annot(annot) -> dict | None:
    try:
        rect = [float(v) for v in annot.get("/Rect")]
        if len(rect) != 4:
            return None
        left, bottom, right, top = (
            min(rect[0], rect[2]),
            min(rect[1], rect[3]),
            max(rect[0], rect[2]),
            max(rect[1], rect[3]),
        )
        if right - left < 1 or top - bottom < 1:
            return None
        extracted = _signature_display_lines(annot)
        parent = annot.get("/Parent")
        parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
        signed = (
            annot.get("/V") is not None
            or (parent_obj is not None and parent_obj.get("/V") is not None)
            or bool(extracted)
        )
        return {
            "box": (left, bottom, right, top),
            "lines": extracted,
            "signed": signed,
        }
    except Exception:
        return None


def _collect_signature_click_targets(pdf_path: str) -> list[dict]:
    try:
        import pikepdf

        targets: list[dict] = []
        with pikepdf.Pdf.open(pdf_path) as pdf:
            page_ref_to_number: dict[tuple[int, int], int] = {}
            annot_ref_to_page: dict[tuple[int, int], int] = {}
            seen: set[tuple[int, str, tuple[float, float, float, float]]] = set()

            def _add_target(page_index: int, field_name: str, rect: list[float] | None):
                if not page_index or rect is None:
                    return
                key = (
                    int(page_index),
                    str(field_name or ""),
                    tuple(round(float(v), 4) for v in rect),
                )
                if key in seen:
                    return
                seen.add(key)
                targets.append(
                    {
                        "page": int(page_index),
                        "field_name": str(field_name or ""),
                        "rect": [float(v) for v in rect],
                    }
                )

            def _page_for_obj(obj) -> int:
                try:
                    page_obj = obj.get("/P")
                    page_obj = page_obj.get_object() if hasattr(page_obj, "get_object") else page_obj
                    key = _pdf_obj_ref_key(page_obj)
                    if key in page_ref_to_number:
                        return int(page_ref_to_number[key])
                except Exception:
                    pass
                key = _pdf_obj_ref_key(obj)
                if key in annot_ref_to_page:
                    return int(annot_ref_to_page[key])
                return 0

            for page_index, page in enumerate(pdf.pages, start=1):
                page_key = _pdf_obj_ref_key(page.obj)
                if page_key is not None:
                    page_ref_to_number[page_key] = page_index
                annots = page.obj.get("/Annots")
                if not annots:
                    continue
                for annot in annots:
                    annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    annot_key = _pdf_obj_ref_key(annot_obj)
                    if annot_key is not None:
                        annot_ref_to_page[annot_key] = page_index
                    if not _is_signature_widget(annot_obj):
                        continue
                    _add_target(page_index, _signature_field_name(annot_obj) or "", _signature_rect(annot_obj))

            def _walk_sig_fields(fields, inherited_name: str = "", inherited_sig: bool = False):
                for field in fields or []:
                    try:
                        field_obj = field.get_object() if hasattr(field, "get_object") else field
                    except Exception:
                        continue
                    current_name = str(field_obj.get("/T") or "").strip() or inherited_name
                    current_sig = (
                        inherited_sig
                        or str(field_obj.get("/FT") or "") == "/Sig"
                        or field_obj.get("/V") is not None
                    )
                    if current_sig:
                        _add_target(_page_for_obj(field_obj), current_name, _signature_rect(field_obj))
                    kids = field_obj.get("/Kids") or []
                    if kids:
                        _walk_sig_fields(kids, current_name, current_sig)

            acroform = pdf.Root.get("/AcroForm")
            if acroform is not None:
                _walk_sig_fields(acroform.get("/Fields") or [])
        return targets
    except Exception:
        return []


def _signature_display_lines(annot) -> list[str]:
    try:
        parent = annot.get("/Parent")
        parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
        sig = annot.get("/V") or (parent_obj.get("/V") if parent_obj is not None else None)
        if sig is None:
            return []

        lines: list[str] = ["ĐÃ KÝ SỐ"]
        cert_details = _signature_certificate_details(sig)

        name = cert_details.get("subject_name") if cert_details else None
        name = name or sig.get("/Name")
        if name:
            lines.append(f"Người ký: {str(name)}")

        issuer = cert_details.get("issuer_provider") if cert_details else None
        if issuer:
            lines.append(f"Đơn vị CA: {issuer}")

        tax_code = cert_details.get("tax_code") if cert_details else None
        if tax_code:
            lines.append(f"MST/CCCD: {tax_code}")

        signed_at = sig.get("/M")
        if signed_at:
            stamp = _format_signature_stamp_time(str(signed_at))
            lines.append(f"Thời điểm: {stamp}")

        serial = cert_details.get("serial_hex") if cert_details else None
        if serial:
            lines.append(f"Serial: {_compact_signature_value(serial)}")

        cert_status = cert_details.get("certificate_status") if cert_details else None
        if cert_status:
            cert_status = {
                "Con han": "Còn hạn",
                "Het han": "Hết hạn",
                "Chua hieu luc": "Chưa hiệu lực",
            }.get(str(cert_status), str(cert_status))
            lines.append(f"Trạng thái: {cert_status}; tài liệu chưa bị sửa")

        reason = sig.get("/Reason")
        if reason:
            lines.append(f"Lý do: {str(reason)}")

        location = sig.get("/Location")
        if location:
            lines.append(f"Địa điểm: {str(location)}")

        contact = sig.get("/ContactInfo")
        if contact:
            lines.append(f"Liên hệ: {str(contact)}")

        return lines[:7]
    except Exception:
        return []


def _compact_signature_value(value: object, *, head: int = 12, tail: int = 8, limit: int = 28) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:head]}...{text[-tail:]}"


def _format_signature_stamp_time(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("D:") and len(text) >= 16:
        return f"{text[8:10]}/{text[6:8]}/{text[2:6]} {text[10:12]}:{text[12:14]}:{text[14:16]}"
    if len(text) >= 19 and text[4:5] == "-" and text[7:8] == "-":
        return f"{text[8:10]}/{text[5:7]}/{text[0:4]} {text[11:19]}"
    return text


def _signature_certificate_details(sig) -> dict | None:
    try:
        from asn1crypto import cms
        from packages.signing.shared import extract_certificate_details_from_der

        contents = sig.get("/Contents")
        if contents is None:
            return None
        cms_bytes = bytes(contents).rstrip(b"\x00")
        if not cms_bytes:
            return None
        content_info = cms.ContentInfo.load(cms_bytes)
        signed_data = content_info["content"]
        certificates = signed_data["certificates"]
        if not certificates:
            return None
        for cert_choice in certificates:
            if cert_choice.name != "certificate":
                continue
            details = extract_certificate_details_from_der(cert_choice.chosen.dump())
            if details:
                return details
    except Exception:
        return None
    return None


def _signature_metadata_lines(annot) -> list[str]:
    try:
        parent = annot.get("/Parent")
        parent_obj = parent.get_object() if hasattr(parent, "get_object") else parent
        sig = annot.get("/V") or (parent_obj.get("/V") if parent_obj is not None else None)
        if sig is None:
            return []

        lines: list[str] = ["ĐÃ KÝ SỐ"]

        name = sig.get("/Name")
        if name:
            lines.append(f"Người ký: {str(name)}")

        signed_at = sig.get("/M")
        if signed_at:
            lines.append(f"Thời điểm: {str(signed_at)}")

        reason = sig.get("/Reason")
        if reason:
            lines.append(f"Lý do: {str(reason)}")

        location = sig.get("/Location")
        if location:
            lines.append(f"Địa điểm: {str(location)}")

        contact = sig.get("/ContactInfo")
        if contact:
            lines.append(f"Liên hệ: {str(contact)}")

        return lines[:6]
    except Exception:
        return []


def _extract_signature_text_lines(annot) -> list[str]:
    try:
        ap = annot.get("/AP")
        normal = ap.get("/N") if ap else None
        if normal is None:
            return []
        stream = normal
        if not hasattr(stream, "read_bytes") and hasattr(normal, "values"):
            stream = next((v for v in normal.values() if hasattr(v, "read_bytes")), None)
        if stream is None or not hasattr(stream, "read_bytes"):
            return []
        data = bytes(stream.read_bytes())
    except Exception:
        return []

    import re

    lines: list[str] = []
    for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", data):
        text = _decode_pdf_literal(match.group(1)).strip()
        if text:
            lines.append(text)
    for match in re.finditer(rb"\[(.*?)\]\s*TJ", data, flags=re.S):
        array_data = match.group(1)
        for literal in re.finditer(rb"\(((?:\\.|[^\\)])*)\)", array_data):
            text = _decode_pdf_literal(literal.group(1)).strip()
            if text:
                lines.append(text)
        for hex_text in re.finditer(rb"<([0-9A-Fa-f\s]+)>", array_data):
            text = _decode_pdf_hex_string(hex_text.group(1)).strip()
            if text:
                lines.append(text)
    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)
    return deduped[:6]


def _decode_pdf_literal(data: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(data):
        ch = data[i]
        if ch != 0x5C:
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(data):
            break
        esc = data[i]
        if esc in b"nrtbf":
            out.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}[esc])
            i += 1
        elif esc in b"()\\":
            out.append(esc)
            i += 1
        elif 48 <= esc <= 55:
            octal = bytes([esc])
            i += 1
            for _ in range(2):
                if i < len(data) and 48 <= data[i] <= 55:
                    octal += bytes([data[i]])
                    i += 1
                else:
                    break
            out.append(int(octal, 8))
        else:
            out.append(esc)
            i += 1
    return out.decode("latin-1", errors="replace")


def _decode_pdf_hex_string(data: bytes) -> str:
    compact = b"".join(data.split())
    if len(compact) % 2 == 1:
        compact += b"0"
    try:
        raw = bytes.fromhex(compact.decode("ascii"))
    except Exception:
        return ""
    try:
        return raw.decode("utf-16-be").replace("\x00", "")
    except Exception:
        return raw.decode("latin-1", errors="replace")


def _page_size(page) -> tuple[float, float]:
    media_box = [float(v) for v in page.MediaBox]
    return (media_box[2] - media_box[0], media_box[3] - media_box[1])


def _build_signature_display_overlay(width: float, height: float, overlays: list[dict]) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        from packages.platform.fonts import get_vietnamese_font_path
    except Exception:
        return b""

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    def _font_name(bold: bool = False) -> str:
        font_path = get_vietnamese_font_path(bold=bold)
        if not font_path:
            return "Helvetica-Bold" if bold else "Helvetica"
        name = "3TSignatureSans-Bold" if bold else "3TSignatureSans"
        try:
            pdfmetrics.getFont(name)
        except Exception:
            try:
                pdfmetrics.registerFont(TTFont(name, font_path))
            except Exception:
                return "Helvetica-Bold" if bold else "Helvetica"
        return name

    title_font = _font_name(bold=True)
    body_font = _font_name(bold=False)

    def _fit_lines(raw_lines: list[str], box_width: float, box_height: float) -> tuple[float, float, list[str]]:
        clean = [line for line in raw_lines if line and line.upper() != "ĐÃ KÝ SỐ"]
        core = clean[:2] or ["Chữ ký số hợp lệ"]
        medium = clean[:3] if len(clean) >= 3 else core
        candidates = [clean, clean[:6], clean[:5], clean[:4], medium, core]
        max_text_width = max(32.0, box_width - 14.0)
        max_text_height = max(16.0, box_height - 12.0)
        title_size = max(6.5, min(18.0, box_height / 7.4))
        # Scale candidate sizes proportionally with box dimensions.
        _max_body = max(7.8, min(24.0, box_height / 8.0, box_width / 18.0))
        sizes = tuple(
            round(s, 1) for s in
            [_max_body - i * 0.4 for i in range(int((_max_body - 5.0) / 0.4) + 1)]
            if s >= 5.0
        ) or (7.8, 7.4, 7.0, 6.6, 6.2, 5.8, 5.4)
        for lineset in candidates:
            for size in sizes:
                wrapped: list[str] = []
                for line in lineset:
                    wrapped.extend(simpleSplit(str(line), body_font, size, max_text_width) or [str(line)])
                leading = max(size + 0.9, size * 1.16)
                if title_size + 2.0 + len(wrapped) * leading <= max_text_height:
                    return size, leading, wrapped
        size = 5.0
        leading = 5.9
        wrapped = []
        for line in core:
            wrapped.extend(simpleSplit(str(line), body_font, size, max_text_width) or [str(line)])
        max_lines = max(1, int((max_text_height - title_size - 2.0) // leading))
        return size, leading, wrapped[:max_lines]

    for overlay in overlays:
        left, bottom, right, top = overlay["box"]
        box_width = max(1.0, right - left)
        box_height = max(1.0, top - bottom)
        signed = bool(overlay.get("signed"))
        lines = [str(line).strip() for line in (overlay.get("lines") or []) if str(line).strip()]
        if lines and str(lines[0]).strip().upper() == "ĐÃ KÝ SỐ":
            lines = lines[1:]

        c.saveState()
        stroke = colors.HexColor("#0b84f3") if signed else colors.HexColor("#64748b")
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.0))
        c.setStrokeColor(stroke)
        c.setLineWidth(0.65)
        c.roundRect(left, bottom, box_width, box_height, 3, fill=0, stroke=1)

        title_size = max(6.5, min(18.0, box_height / 7.4))
        font_size, leading, wrapped_lines = _fit_lines(lines, box_width, box_height)
        block_height = title_size + 2.0 + len(wrapped_lines) * leading
        y = top - 7 - title_size
        if block_height < box_height - 16:
            y -= min(3.0, max(0.0, (box_height - 16.0 - block_height) / 3.0))
        c.setFillColor(colors.HexColor("#052e51"))
        c.setFont(title_font, title_size)
        c.drawString(left + 8, y, "ĐÃ KÝ SỐ")
        y -= title_size + 3.0
        if wrapped_lines:
            for line in wrapped_lines:
                if y < bottom + 4:
                    break
                text = str(line).strip()
                if text.startswith("Trạng thái:"):
                    c.setFillColor(colors.HexColor("#166534"))
                    c.setFont(body_font, font_size)
                    c.drawString(left + 8, y, text)
                elif ":" in text:
                    label, value = text.split(":", 1)
                    label_text = f"{label.strip()}: "
                    c.setFillColor(colors.HexColor("#475569"))
                    c.setFont(body_font, font_size)
                    c.drawString(left + 8, y, label_text)
                    label_width = pdfmetrics.stringWidth(label_text, body_font, font_size)
                    c.setFillColor(colors.HexColor("#0f172a"))
                    c.drawString(left + 8 + label_width, y, value.strip())
                else:
                    c.setFillColor(colors.HexColor("#0f172a"))
                    c.setFont(body_font, font_size)
                    c.drawString(left + 8, y, text)
                y -= leading
        c.restoreState()
    c.save()
    return buf.getvalue()


def _build_signature_display_overlay_ascii(width: float, height: float, overlays: list[dict]) -> bytes:
    try:
        import unicodedata
        from reportlab.lib import colors
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        from packages.platform.fonts import get_vietnamese_font_path
    except Exception:
        return b""

    def _ascii_text(value: str) -> str:
        return unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii") or str(value)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    def _font_name(bold: bool = False) -> str:
        font_path = get_vietnamese_font_path(bold=bold)
        if not font_path:
            return "Helvetica-Bold" if bold else "Helvetica"
        name = "3TSignatureSans-Bold" if bold else "3TSignatureSans"
        try:
            pdfmetrics.getFont(name)
        except Exception:
            try:
                pdfmetrics.registerFont(TTFont(name, font_path))
            except Exception:
                return "Helvetica-Bold" if bold else "Helvetica"
        return name

    title_font = _font_name(bold=True)
    body_font = _font_name(bold=False)

    def _fit_lines(raw_lines: list[str], box_width: float, box_height: float) -> tuple[float, float, list[str]]:
        clean = [line for line in raw_lines if line and line.upper() not in {"DA KY SO", "A KY SO"}]
        core = clean[:2] or ["Chu ky so hop le"]
        medium = clean[:3] if len(clean) >= 3 else core
        candidates = [clean, clean[:6], clean[:5], clean[:4], medium, core]
        max_text_width = max(32.0, box_width - 14.0)
        max_text_height = max(16.0, box_height - 12.0)
        title_size = max(7.0, min(18.0, box_height / 6.8))
        # Scale candidate sizes proportionally with box dimensions.
        _max_body = max(8.5, min(24.0, box_height / 7.0, box_width / 16.0))
        sizes = tuple(
            round(s, 1) for s in
            [_max_body - i * 0.5 for i in range(int((_max_body - 5.0) / 0.5) + 1)]
            if s >= 5.0
        ) or (8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5)
        for lineset in candidates:
            for size in sizes:
                wrapped: list[str] = []
                for line in lineset:
                    wrapped.extend(simpleSplit(str(line), body_font, size, max_text_width) or [str(line)])
                leading = max(size + 1.0, size * 1.18)
                if title_size + 2.0 + len(wrapped) * leading <= max_text_height:
                    return size, leading, wrapped
        size = 5.2
        leading = 6.3
        wrapped = []
        for line in core:
            wrapped.extend(simpleSplit(str(line), body_font, size, max_text_width) or [str(line)])
        max_lines = max(1, int((max_text_height - title_size - 2.0) // leading))
        return size, leading, wrapped[:max_lines]

    for overlay in overlays:
        left, bottom, right, top = overlay["box"]
        box_width = max(1.0, right - left)
        box_height = max(1.0, top - bottom)
        signed = bool(overlay.get("signed"))
        lines = [_ascii_text(line).strip() for line in (overlay.get("lines") or []) if _ascii_text(line).strip()]
        if lines and lines[0].upper() in {"DA KY SO", "A KY SO"}:
            lines = lines[1:]

        c.saveState()
        stroke = colors.HexColor("#0b84f3") if signed else colors.HexColor("#64748b")
        c.setFillColor(colors.Color(1, 1, 1, alpha=0))
        c.setStrokeColor(stroke)
        c.setLineWidth(0.9)
        c.roundRect(left, bottom, box_width, box_height, 4, fill=0, stroke=1)

        c.setFillColorRGB(0.02, 0.18, 0.32)
        title_size = max(7.0, min(18.0, box_height / 6.8))
        font_size, leading, wrapped_lines = _fit_lines(lines, box_width, box_height)
        block_height = title_size + 2.0 + len(wrapped_lines) * leading
        y = top - 6 - max(0.0, (box_height - 12.0 - block_height) / 2.0) - title_size
        c.setFont(title_font, title_size)
        c.drawString(left + 5, y, "DA KY SO")
        y -= title_size + 2.0
        if wrapped_lines:
            c.setFont(body_font, font_size)
            for line in wrapped_lines:
                if y < bottom + 4:
                    break
                c.drawString(left + 5, y, _ascii_text(line))
                y -= leading
        c.restoreState()
    c.save()
    return buf.getvalue()


def _build_signature_display_overlay_bitmap(width: float, height: float, overlays: list[dict]) -> bytes:
    try:
        import io
        from PIL import Image, ImageDraw, ImageFont
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
        from packages.platform.fonts import get_vietnamese_font_path
    except Exception:
        return b""

    w = max(1, int(round(width)))
    h = max(1, int(round(height)))
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    font_path = get_vietnamese_font_path(bold=False) or get_vietnamese_font_path(bold=True)
    bold_font_path = get_vietnamese_font_path(bold=True) or font_path

    def _load_font(size: int, *, bold: bool = False):
        try:
            selected = bold_font_path if bold else font_path
            if selected:
                return ImageFont.truetype(selected, size)
        except Exception:
            pass
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def _text_size(text: str, font) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])

    def _wrap_line(text: str, font, max_width: int) -> list[str]:
        raw = str(text).strip()
        if not raw:
            return []
        if _text_size(raw, font)[0] <= max_width:
            return [raw]
        words = raw.split()
        if len(words) <= 1:
            return [raw]
        wrapped: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _text_size(candidate, font)[0] <= max_width:
                current = candidate
            else:
                wrapped.append(current)
                current = word
        if current:
            wrapped.append(current)
        return wrapped

    def _fit_block(lines: list[str], max_width: int, max_height: int, title_height: int, box_height: int = 0, box_width: int = 0):
        clean = [line for line in lines if line and line.upper() != "ĐÃ KÝ SỐ"]
        core = clean[:2] or ["Chữ ký số hợp lệ"]
        medium = clean[:3] if len(clean) >= 3 else core
        candidates = [clean, clean[:6], clean[:5], clean[:4], medium, core]
        # Scale max font size proportionally: for ~96px box -> ~9pt; for ~200px box -> ~18pt
        _max_size = max(9, min(28, int(max(box_height, 0) / 8.0), int(max(box_width, 0) / 16.0))) if box_height > 0 else 9
        for lineset in candidates:
            for size in range(_max_size, 4, -1):
                font = _load_font(size)
                if font is None:
                    continue
                wrapped: list[str] = []
                for line in lineset:
                    wrapped.extend(_wrap_line(line, font, max_width))
                if not wrapped:
                    continue
                _, text_h = _text_size("Ag", font)
                line_height = max(6, int(text_h * 1.18))
                total_height = title_height + 3 + line_height * len(wrapped)
                if total_height <= max_height:
                    return font, wrapped, line_height, total_height
        font = _load_font(5)
        wrapped = []
        for line in core:
            wrapped.extend(_wrap_line(line, font, max_width))
        _, text_h = _text_size("Ag", font)
        line_height = max(6, int(text_h * 1.14))
        max_lines = max(1, (max_height - title_height - 3) // line_height)
        wrapped = wrapped[:max_lines]
        return font, wrapped, line_height, title_height + 3 + line_height * len(wrapped)

    def _fit_title(max_height: int, box_height: int = 0):
        _max_title = max(9, min(22, int(max(box_height, 0) / 7.0))) if box_height > 0 else 9
        for size in range(_max_title, 5, -1):
            font = _load_font(size, bold=True)
            if font is None:
                continue
            _, text_h = _text_size("ĐÃ KÝ SỐ", font)
            if text_h + 9 <= max_height:
                return font, max(6, int(text_h * 1.15))
        font = _load_font(6, bold=True)
        _, text_h = _text_size("ĐÃ KÝ SỐ", font)
        return font, max(6, int(text_h * 1.15))

    for overlay in overlays:
        left, bottom, right, top = overlay["box"]
        signed = bool(overlay.get("signed"))
        lines = [str(line).strip() for line in (overlay.get("lines") or []) if str(line).strip()]

        x0 = max(0, int(round(left)))
        x1 = min(w - 1, int(round(right)))
        y0 = max(0, int(round(h - top)))
        y1 = min(h - 1, int(round(h - bottom)))
        if x1 <= x0 or y1 <= y0:
            continue

        stroke = (11, 132, 243, 235) if signed else (100, 116, 139, 220)
        fill = (255, 255, 255, 0)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=3, fill=None, outline=stroke, width=1)

        title_color = (5, 46, 81, 255)
        label_color = (71, 85, 105, 255)
        value_color = (15, 23, 42, 255)
        ok_color = (22, 101, 52, 255)
        margin_x = 8
        max_text_width = max(1, (x1 - x0) - (margin_x * 2))
        max_text_height = max(1, (y1 - y0) - 12)
        bmp_box_h = y1 - y0
        bmp_box_w = x1 - x0
        title_font, title_height = _fit_title(max_text_height, box_height=bmp_box_h)
        body_font, wrapped_lines, line_height, total_height = _fit_block(lines, max_text_width, max_text_height, title_height, box_height=bmp_box_h, box_width=bmp_box_w)
        y = y0 + 7
        if total_height < max_text_height - 4:
            y += min(3, max(0, (max_text_height - total_height) // 3))
        draw.text((x0 + margin_x, y), "ĐÃ KÝ SỐ", font=title_font, fill=title_color)
        y += title_height + 3
        for line in wrapped_lines:
            if y + line_height > y1 - 2:
                break
            text = str(line).strip()
            lower = text.lower()
            if lower.startswith("trạng thái:"):
                draw.text((x0 + margin_x, y), text, font=body_font, fill=ok_color)
            elif ":" in text:
                label, value = text.split(":", 1)
                label_text = f"{label.strip()}:"
                label_font = _load_font(getattr(body_font, "size", 7), bold=False) or body_font
                draw.text((x0 + margin_x, y), label_text, font=label_font, fill=label_color)
                label_w, _ = _text_size(label_text + " ", label_font)
                draw.text((x0 + margin_x + label_w, y), value.strip(), font=body_font, fill=value_color)
            else:
                draw.text((x0 + margin_x, y), text, font=body_font, fill=value_color)
            y += line_height

    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    png_buf.seek(0)

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(width, height))
    c.drawImage(ImageReader(png_buf), 0, 0, width=width, height=height, mask="auto")
    c.save()
    return pdf_buf.getvalue()
