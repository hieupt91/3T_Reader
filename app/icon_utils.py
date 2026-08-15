import os
from functools import lru_cache

from packages.qt_compat.QtGui import QIcon, QPixmap, QPainter
from packages.qt_compat.QtSvg import QSvgRenderer
from packages.qt_compat.QtCore import QSize, Qt

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
ASSETS_DIR = get_resource_path("assets")


def _recolor_svg_data(svg_data: str, color: str) -> str:
    for old in ['"#212121"', '"#000"', '"#000000"',
                "'#212121'", "'black'", '"black"']:
        svg_data = svg_data.replace(f'fill={old}', f'fill="{color}"')
        svg_data = svg_data.replace(f'stroke={old}', f'stroke="{color}"')

    svg_data = svg_data.replace('currentColor', color)
    if 'color="' not in svg_data and "color='" not in svg_data:
        svg_data = svg_data.replace("<svg ", f'<svg color="{color}" ', 1)

    if color not in svg_data:
        svg_data = svg_data.replace("<svg ", f'<svg fill="{color}" ', 1)
    return svg_data


@lru_cache(maxsize=4)
def app_logo_icon(size: int = 64) -> QIcon:
    """Return QIcon from logo_mark.svg (full colour, no recolour)."""
    path = os.path.join(ASSETS_DIR, "logo_mark.svg")
    if not os.path.exists(path):
        return QIcon()
    renderer = QSvgRenderer(path)
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


@lru_cache(maxsize=128)
def svg_icon(filename: str, size: int = 20, color: str = "#9090b8") -> QIcon:
    path = os.path.join(ICON_DIR, filename)
    if not os.path.exists(path) and filename.endswith(".svg"):
        alt_path = os.path.join(ICON_DIR, f"{filename}.svg")
        if os.path.exists(alt_path):
            path = alt_path
    if not os.path.exists(path):
        return QIcon()

    with open(path, "r", encoding="utf-8") as f:
        svg_data = f.read()
    svg_data = _recolor_svg_data(svg_data, color)

    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)
