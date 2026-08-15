"""Load external JavaScript files bundled with the application.

Usage::

    from app.js_loader import load_js
    polyfill_js = load_js("polyfill.js")
    hooks_js = load_js("pdfjs_ui_hooks.js")

Files are read once at import time and cached for the process lifetime.
"""

from __future__ import annotations

import os
from pathlib import Path

_JS_DIR = Path(__file__).resolve().parent.parent / "assets" / "js"

_cache: dict[str, str] = {}


def load_js(filename: str) -> str:
    """Return the contents of *filename* from ``assets/js/``.

    Raises ``FileNotFoundError`` if the file does not exist.
    """
    if filename not in _cache:
        path = _JS_DIR / filename
        _cache[filename] = path.read_text(encoding="utf-8")
    return _cache[filename]
