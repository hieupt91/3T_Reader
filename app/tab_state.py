"""Per-tab state container — replaces the untyped _global_state dict."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.pdf_viewer import PDFViewerWidget


@dataclass
class TabState:
    """Holds all mutable state for a single document tab."""

    viewer: PDFViewerWidget | None = None
    source_path: str | None = None
    display_path: str | None = None
    web_view: Any = None  # QWebEngineView — avoid import cycle
    search_query: str = ""
    temp_path: str | None = None

    # Inline editor state
    current_inserted: Any = field(default_factory=lambda: None)
    current_inserted_kind: str = ""

    # Annotation undo stack
    annotation_undo_stack: list = field(default_factory=list)

    # Staged save paths
    staged_path: str | None = None
