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
    display_cache: OrderedDict = OrderedDict()  # (path,mtime,size) -> bytes, LRU
    signature_probe_cache: OrderedDict = OrderedDict()  # (path,mtime,size) -> bool, LRU
    _MAX_CACHE_ENTRIES = 6
    _cache_lock = threading.RLock()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/pdf":
            self._serve_pdf(parsed.query)
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
        if not os.path.isfile(pdf_path):
            self.send_error(404)
            return
        try:
            if not self._has_signature_field_cached(pdf_path):
                self._serve_pdf_file(pdf_path, send_body=send_body)
                return
            data = self._read_pdf_for_display(pdf_path)
            self._serve_pdf_bytes(data, send_body=send_body)
        except OSError:
            self.send_error(500)

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

    def start(self):
        if self._server:
            return
        if not self._root:
            return

        root = self._root

        class Handler(_PDFJSHandler):
            pdfjs_root = root

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
        abs_path = os.path.abspath(pdf_path)
        encoded_path = urllib.parse.quote(abs_path)
        try:
            cache_key = str(os.stat(abs_path).st_mtime_ns)
        except OSError:
            cache_key = "0"
        pdf_url = f"http://127.0.0.1:{self._port}/pdf?p={encoded_path}&v={cache_key}"
        encoded_pdf_url = urllib.parse.quote(pdf_url, safe="")
        viewer_opts = (
            f"file={encoded_pdf_url}"
            "&disableStream=true"
            "&disableAutoFetch=true"
            "&disableRange=false"
            "&rangeChunkSize=1048576"
        )
        url = f"http://127.0.0.1:{self._port}/web/viewer.html?{viewer_opts}#page={page}"
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


def _normalise_pdfjs_appearance_boxes(pdf_path: str, original_data: bytes) -> bytes:
    """Serve a display-only copy that avoids PDF.js signature widget issues."""
    try:
        import pikepdf

        changed = False
        with pikepdf.Pdf.open(pdf_path) as pdf:
            signature_overlays: dict[int, list[dict]] = {}
            removed_sig_field_names: set[str] = set()
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
                        overlay = None if painted else _signature_overlay_from_annot(annot_obj)
                        if overlay and overlay.get("lines"):
                            signature_overlays.setdefault(page_index, []).append(overlay)
                        removed_signature_widgets += 1
                        field_name = _signature_field_name(annot_obj)
                        if field_name is not None:
                            removed_sig_field_names.add(field_name)
                        changed = True
                        continue
                    kept_annots.append(annot)
                    ap = annot_obj.get("/AP")
                    if not ap:
                        continue
                    normal = ap.get("/N")
                    if normal is None:
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
                if kept_annots:
                    page.obj["/Annots"] = pikepdf.Array(kept_annots)
                elif "/Annots" in page.obj:
                    del page.obj["/Annots"]

            for page_index, overlays in signature_overlays.items():
                page = pdf.pages[page_index - 1]
                width, height = _page_size(page)
                overlay_pdf_bytes = _build_signature_display_overlay(width, height, overlays)
                if not overlay_pdf_bytes:
                    continue
                with pikepdf.Pdf.open(io.BytesIO(overlay_pdf_bytes)) as overlay_pdf:
                    page.add_overlay(overlay_pdf.pages[0])

            # Also strip signature fields from AcroForm so PDF.js doesn't re-render
            # them through form-widget machinery (PDF.js draws a default frame
            # around any /Sig field it finds in AcroForm, regardless of /Annots).
            if removed_signature_widgets:
                try:
                    root = pdf.Root
                    acro = root.get("/AcroForm")
                    if acro is not None:
                        fields_arr = acro.get("/Fields")
                        if fields_arr is not None:
                            kept_fields, _changed_fields = _strip_signature_fields(
                                fields_arr,
                                removed_sig_field_names,
                            )
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
            annot.get("/FT") == "/Sig"
            or annot.get("/V") is not None
            or (parent_obj is not None and parent_obj.get("/FT") == "/Sig")
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
            bbox_w = abs(bx1 - bx0) or width
            bbox_h = abs(by1 - by0) or height
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
        xobjects[name] = stream

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
        extracted = _extract_signature_text_lines(annot)
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
        from reportlab.pdfgen import canvas
    except Exception:
        return b""

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    for overlay in overlays:
        left, bottom, right, top = overlay["box"]
        box_width = max(1.0, right - left)
        box_height = max(1.0, top - bottom)
        signed = bool(overlay.get("signed"))
        lines = [str(line).strip() for line in (overlay.get("lines") or []) if str(line).strip()]
        if not lines:
            continue

        c.saveState()
        # Render text only; never draw signature field frames in the display copy.
        c.setFillColorRGB(0.02, 0.18, 0.32)
        font_size = max(7.0, min(10.0, box_height / max(4.5, len(lines) + 1)))
        leading = font_size + 2
        c.setFont("Helvetica-Bold", font_size)
        y = top - font_size - 5
        for line in lines:
            if y < bottom + 3:
                break
            c.drawString(left + 5, y, str(line)[:70])
            y -= leading
        c.restoreState()
    c.save()
    return buf.getvalue()
