import os
from functools import lru_cache

from packages.qt_compat.QtGui import QIcon, QPixmap, QPainter
from packages.qt_compat.QtSvg import QSvgRenderer
from packages.qt_compat.QtCore import QSize, Qt, QRectF

import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 6.x onedir mode puts everything in _internal
        # but sys._MEIPASS points to the root directory
        path = os.path.join(sys._MEIPASS, relative_path)
        if not os.path.exists(path):
            alt_path = os.path.join(sys._MEIPASS, "_internal", relative_path)
            if os.path.exists(alt_path):
                return alt_path
        return path
    return os.path.join(os.path.abspath("."), relative_path)

ICON_DIR = get_resource_path(os.path.join("assets", "icons"))
ASSET_DIR = get_resource_path("assets")


def _resolve_svg_path(filename: str) -> str:
    candidates = []
    for base in (ICON_DIR, ASSET_DIR):
        candidates.append(os.path.join(base, filename))
        if filename.endswith(".svg"):
            candidates.append(os.path.join(base, f"{filename}.svg"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _coerce_size(size) -> QSize:
    if isinstance(size, QSize):
        return size
    if isinstance(size, tuple):
        return QSize(int(size[0]), int(size[1]))
    return QSize(int(size), int(size))


@lru_cache(maxsize=128)
def svg_icon(filename: str, size: int = 20, color: str = "#9090b8") -> QIcon:
    path = _resolve_svg_path(filename)
    if not path:
        return QIcon()

    with open(path, "r", encoding="utf-8") as f:
        svg_data = f.read()

    # Thay TẤT CẢ màu tối → màu theme sáng
    for old in ['"#212121"', '"#000"', '"#000000"',
                "'#212121'", "'black'", '"black"']:
        svg_data = svg_data.replace(f'fill={old}', f'fill="{color}"')
        svg_data = svg_data.replace(f'stroke={old}', f'stroke="{color}"')

    # Nếu SVG không có fill cụ thể nào → thêm vào thẻ <svg>
    if color not in svg_data:
        svg_data = svg_data.replace("<svg ", f'<svg fill="{color}" ', 1)

    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


@lru_cache(maxsize=128)
def svg_pixmap(filename: str, size=20) -> QPixmap:
    path = _resolve_svg_path(filename)
    if not path:
        return QPixmap()

    with open(path, "r", encoding="utf-8") as f:
        svg_data = f.read()

    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    target_size = _coerce_size(size)
    pixmap = QPixmap(target_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    default_size = renderer.defaultSize()
    if default_size.isValid() and default_size.width() > 0 and default_size.height() > 0:
        scaled_size = default_size.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio)
        x = (target_size.width() - scaled_size.width()) / 2
        y = (target_size.height() - scaled_size.height()) / 2
        renderer.render(painter, QRectF(x, y, scaled_size.width(), scaled_size.height()))
    else:
        renderer.render(painter)
    painter.end()

    return pixmap
