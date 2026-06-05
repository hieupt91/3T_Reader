"""Edit overlay system — show text/image previews on PDF.js canvas without rebuilding.

This module provides overlay rendering for edit operations (insert text, insert image)
similar to how annotations use overlay marks. The key difference:
- Annotations: overlay → queue save (no reload)
- Edit ops: overlay → deferred rebuild (only on explicit save)

This eliminates the lag caused by rebuilding the entire PDF on every edit operation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _edit_overlay_ops(window) -> list[dict]:
    """Get the list of edit overlay operations for the current session."""
    ops = getattr(window, "_edit_overlay_ops", None)
    if not isinstance(ops, list):
        ops = []
        window._edit_overlay_ops = ops
    return ops


def add_edit_overlay(
    window,
    *,
    op_id: str,
    op_type: str,  # "text" or "image"
    page_number: int,
    rect: tuple[float, float, float, float],  # (left, bottom, right, top) in PDF coords
    text: str = "",
    image_path: str = "",
    font_size: float = 14,
    color_hex: str = "#000000",
    bold: bool = False,
    underline: bool = False,
    rotation: float = 0,
) -> None:
    """Add an edit overlay to the PDF.js canvas."""
    overlay = {
        "id": op_id,
        "type": op_type,
        "page_number": page_number,
        "rect": list(rect),
        "text": text,
        "image_path": image_path,
        "font_size": font_size,
        "color_hex": color_hex,
        "bold": bold,
        "underline": underline,
        "rotation": rotation,
    }
    _edit_overlay_ops(window).append(overlay)
    _refresh_edit_overlays_js(window)


def remove_edit_overlay(window, op_id: str) -> None:
    """Remove an edit overlay by ID."""
    ops = _edit_overlay_ops(window)
    _edit_overlay_ops(window)[:] = [op for op in ops if op.get("id") != op_id]
    _refresh_edit_overlays_js(window)


def clear_edit_overlays(window) -> None:
    """Remove all edit overlays."""
    _edit_overlay_ops(window).clear()
    _refresh_edit_overlays_js(window)


def _refresh_edit_overlays_js(window) -> None:
    """Inject JS to render all edit overlays on the PDF.js canvas."""
    ops = _edit_overlay_ops(window)
    if not ops:
        # Clear overlays
        try:
            web_view = getattr(window, "viewer", None)
            if web_view and hasattr(web_view, "page"):
                web_view.page().runJavaScript(
                    "document.querySelectorAll('.t3-edit-overlay').forEach(el => el.remove());"
                )
        except Exception:
            pass
        return

    # Build JS to render overlays
    js_parts = [
        "(function() {",
        "  document.querySelectorAll('.t3-edit-overlay').forEach(el => el.remove());",
        "  var ops = " + _ops_to_json(ops) + ";",
        "  var app = window.PDFViewerApplication;",
        "  if (!app || !app.pdfViewer) return;",
        "  var pages = app.pdfViewer._pages;",
        "  if (!pages) return;",
        "  ops.forEach(function(op) {",
        "    var pageIdx = op.page_number - 1;",
        "    if (pageIdx < 0 || pageIdx >= pages.length) return;",
        "    var pageView = pages[pageIdx];",
        "    if (!pageView || !pageView.div) return;",
        "    var viewport = pageView.viewport;",
        "    if (!viewport) return;",
        "    var rect = op.rect;",
        "    var p1 = viewport.convertToViewportPoint(rect[0], rect[3]);",
        "    var p2 = viewport.convertToViewportPoint(rect[2], rect[1]);",
        "    var left = Math.min(p1[0], p2[0]);",
        "    var top = Math.min(p1[1], p2[1]);",
        "    var width = Math.abs(p2[0] - p1[0]);",
        "    var height = Math.abs(p2[1] - p1[1]);",
        "    var overlay = document.createElement('div');",
        "    overlay.className = 't3-edit-overlay';",
        "    overlay.style.cssText = 'position:absolute;left:'+left+'px;top:'+top+'px;width:'+width+'px;height:'+height+'px;z-index:5000;pointer-events:none;';",
        "    if (op.type === 'text') {",
        "      overlay.style.fontFamily = 'Arial,sans-serif';",
        "      overlay.style.fontSize = (op.font_size * viewport.scale) + 'px';",
        "      overlay.style.color = op.color_hex;",
        "      overlay.style.fontWeight = op.bold ? 'bold' : 'normal';",
        "      overlay.style.textDecoration = op.underline ? 'underline' : 'none';",
        "      overlay.style.lineHeight = '1.6';",
        "      overlay.style.overflow = 'hidden';",
        "      overlay.style.whiteSpace = 'pre-wrap';",
        "      overlay.style.wordBreak = 'break-word';",
        "      overlay.textContent = op.text;",
        "      if (op.rotation) {",
        "        overlay.style.transformOrigin = 'center center';",
        "        overlay.style.transform = 'rotate(' + op.rotation + 'deg)';",
        "      }",
        "    } else if (op.type === 'image' && op.image_path) {",
        "      var img = document.createElement('img');",
        "      img.src = 'file:///' + op.image_path.replace(/\\\\/g, '/');",
        "      img.style.cssText = 'width:100%;height:100%;object-fit:contain;';",
        "      overlay.appendChild(img);",
        "      if (op.rotation) {",
        "        overlay.style.transformOrigin = 'center center';",
        "        overlay.style.transform = 'rotate(' + op.rotation + 'deg)';",
        "      }",
        "    }",
        "    pageView.div.appendChild(overlay);",
        "  });",
        "})()"
    ]

    try:
        web_view = getattr(window, "viewer", None)
        if web_view and hasattr(web_view, "page"):
            web_view.page().runJavaScript("\n".join(js_parts))
    except Exception:
        pass


def _ops_to_json(ops: list[dict]) -> str:
    """Convert ops list to JSON string for JS injection."""
    import json
    return json.dumps(ops, ensure_ascii=False)


def get_overlay_ops_for_save(window) -> list[dict]:
    """Get all overlay ops as a list suitable for PDF rebuild."""
    return list(_edit_overlay_ops(window))
