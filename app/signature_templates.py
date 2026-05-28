from __future__ import annotations

import re
from pathlib import Path

from packages.platform import get_app_data_dir


TEMPLATE_DIR = Path(get_app_data_dir()) / "signature_templates"


def _ensure_dir() -> Path:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    return TEMPLATE_DIR


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
    return cleaned or "signature_template"


def find_signature_template(code: str) -> dict[str, str] | None:
    target = _safe_name(code)
    if not target:
        return None
    root = _ensure_dir()
    for path in sorted(root.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.stem == target:
            return {
                "name": path.stem,
                "path": str(path),
                "label": path.stem,
                "code": path.stem,
            }
    return None


def list_signature_templates() -> list[dict[str, str]]:
    root = _ensure_dir()
    items: list[dict[str, str]] = []
    for path in sorted(root.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        items.append({
            "name": path.stem,
            "path": str(path),
            "label": path.stem,
            "code": path.stem,
        })
    return items


def save_signature_template(code: str, pixmap) -> str:
    root = _ensure_dir()
    base = _safe_name(code)
    if not base:
        raise ValueError("Ma mau chu ky khong hop le.")
    path = root / f"{base}.png"
    if path.exists():
        idx = 2
        while True:
            candidate = root / f"{base}_{idx}.png"
            if not candidate.exists():
                path = candidate
                break
            idx += 1

    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError("Khong luu duoc mau chu ky.")
    return str(path)


def load_signature_template(path: str):
    from packages.qt_compat.QtGui import QPixmap

    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap
