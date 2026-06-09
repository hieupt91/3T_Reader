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
        try:
            cache_key = str(os.stat(abs_path).st_mtime_ns)
        except OSError:
            cache_key = "0"
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
            "&annotationMode=1"
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
                for annot in annots:
                    annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    if _is_signature_widget(annot_obj):
                        painted = _paint_signature_widget_appearance(
                            pdf,
                            page,
                            annot_obj,
                            f"T3Sig{page_index}_{removed_signature_widgets + 1}",
                        )
                        # Keep a display overlay even when the raw appearance
                        # stream was flattened successfully. Some signed-widget
                        # appearances still disappear in Qt/PDF.js after the
                        # widget is stripped, while a synthetic overlay remains
                        # stable and guarantees the signature box stays visible.
                        overlay = _signature_overlay_from_annot(annot_obj)
                        if overlay is not None:
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
                    overlay_pdf_bytes = _build_signature_display_overlay_ascii(width, height, overlays)
                if not overlay_pdf_bytes:
                    overlay_pdf_bytes = _build_signature_display_overlay_bitmap(width, height, overlays)
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


def _paint_signature_widget_appearance(pdf, page, annot, resource_name: str) -> bool:
    """Flatten a signature widget's real appearance into the display-only page."""
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
        stream_bytes = bytes(stream.read_bytes())
        stream_copy = pikepdf.Stream(pdf, stream_bytes)
        for key, value in stream.items():
            if str(key) in {"/Length", "/BBox"}:
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
            for page_index, page in enumerate(pdf.pages, start=1):
                annots = page.obj.get("/Annots")
                if not annots:
                    continue
                for annot in annots:
                    annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                    if not _is_signature_widget(annot_obj):
                        continue
                    rect = [float(v) for v in annot_obj.get("/Rect") or []]
                    if len(rect) != 4:
                        continue
                    left, bottom, right, top = (
                        min(rect[0], rect[2]),
                        min(rect[1], rect[3]),
                        max(rect[0], rect[2]),
                        max(rect[1], rect[3]),
                    )
                    if right - left < 1 or top - bottom < 1:
                        continue
                    targets.append(
                        {
                            "page": page_index,
                            "field_name": _signature_field_name(annot_obj) or "",
                            "rect": [left, bottom, right, top],
                        }
                    )
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

        name = sig.get("/Name")
        if name:
            lines.append(f"Tên: {str(name)}")

        signed_at = sig.get("/M")
        if signed_at:
            stamp = str(signed_at)
            if stamp.startswith("D:") and len(stamp) >= 16:
                stamp = f"{stamp[2:6]}-{stamp[6:8]}-{stamp[8:10]} {stamp[10:12]}:{stamp[12:14]}:{stamp[14:16]}"
            lines.append(f"Thời điểm: {stamp}")

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
            lines.append(f"Tên: {str(name)}")

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
        c.setFillColor(colors.Color(1, 1, 1, alpha=0))
        c.setStrokeColor(stroke)
        c.setLineWidth(0.9)
        c.roundRect(left, bottom, box_width, box_height, 4, fill=0, stroke=1)

        c.setFillColorRGB(0.02, 0.18, 0.32)
        title_size = max(7.0, min(9.0, box_height / 7.5))
        font_size = max(6.0, min(8.5, box_height / max(5.0, len(lines) + 2)))
        leading = font_size + 1.4
        c.setFont(title_font, title_size)
        y = top - title_size - 4
        c.drawString(left + 5, y, "ĐÃ KÝ SỐ")
        y -= title_size + 1
        if lines:
            c.setFont(body_font, font_size)
            for line in lines:
                if y < bottom + 3:
                    break
                c.drawString(left + 5, y, str(line)[:70])
                y -= leading
        c.restoreState()
    c.save()
    return buf.getvalue()


def _build_signature_display_overlay_ascii(width: float, height: float, overlays: list[dict]) -> bytes:
    try:
        import unicodedata
        from reportlab.lib import colors
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
        title_size = max(7.0, min(9.0, box_height / 7.5))
        font_size = max(6.0, min(8.5, box_height / max(5.0, len(lines) + 2)))
        leading = font_size + 1.4
        c.setFont(title_font, title_size)
        y = top - title_size - 4
        c.drawString(left + 5, y, "DA KY SO")
        y -= title_size + 1
        if lines:
            c.setFont(body_font, font_size)
            for line in lines:
                if y < bottom + 3:
                    break
                c.drawString(left + 5, y, _ascii_text(line)[:70])
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
    def _load_font(size: int):
        try:
            if font_path:
                return ImageFont.truetype(font_path, size)
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

    def _fit_block(lines: list[str], max_width: int, max_height: int):
        for size in range(14, 5, -1):
            font = _load_font(size)
            if font is None:
                continue
            wrapped: list[str] = []
            for line in lines:
                wrapped.extend(_wrap_line(line, font, max_width))
            if not wrapped:
                return font, wrapped, 0
            _, text_h = _text_size("Ag", font)
            line_height = max(7, int(text_h * 1.1))
            total_height = line_height * len(wrapped)
            if total_height <= max_height:
                return font, wrapped, line_height
        font = _load_font(6)
        wrapped = []
        for line in lines:
            wrapped.extend(_wrap_line(line, font, max_width))
        _, text_h = _text_size("Ag", font)
        return font, wrapped, max(7, int(text_h * 1.05))

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

        stroke = (11, 132, 243, 255) if signed else (100, 116, 139, 255)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=4, outline=stroke, width=2)

        text_color = (5, 46, 81, 255)
        margin_x = 5
        max_text_width = max(1, (x1 - x0) - 10)
        max_text_height = max(1, (y1 - y0) - 8)
        body_font, wrapped_lines, line_height = _fit_block(lines, max_text_width, max_text_height)
        y = y0 + 4
        for line in wrapped_lines:
            if y + line_height > y1 - 2:
                break
            draw.text((x0 + margin_x, y), line, font=body_font, fill=text_color)
            y += line_height

    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    png_buf.seek(0)

    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(width, height))
    c.drawImage(ImageReader(png_buf), 0, 0, width=width, height=height, mask="auto")
    c.save()
    return pdf_buf.getvalue()
