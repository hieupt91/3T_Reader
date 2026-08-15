from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_SIGNATURE_QSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "css" / "signature_ui.css"


@lru_cache(maxsize=1)
def signature_stylesheet() -> str:
    try:
        return _SIGNATURE_QSS_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def apply_signature_styles(widget, *, object_name: str | None = None, extra_qss: str = "") -> None:
    if object_name:
        try:
            widget.setObjectName(object_name)
        except Exception:
            pass
    base = signature_stylesheet()
    qss = "\n".join(part for part in (base, extra_qss) if part)
    if qss:
        try:
            widget.setStyleSheet(qss)
        except Exception:
            pass

