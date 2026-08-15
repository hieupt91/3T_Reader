"""Qt binding compatibility layer.

Commercial target is PySide6. Application code imports Qt through this module
so Windows and macOS can share the same UI code without depending on PyQt.
"""

from PySide6 import QtCore as _QTCORE
from PySide6 import QtGui as _QTGUI
from PySide6 import QtPrintSupport as _QTPRINTSUPPORT
from PySide6 import QtSvg as _QTSVG
from PySide6 import QtSvgWidgets as _QTSVGWIDGETS
from PySide6 import QtWebChannel as _QTWEBCHANNEL
from PySide6 import QtWebEngineCore as _QTWEBENGINECORE
from PySide6 import QtWebEngineWidgets as _QTWEBENGINEWIDGETS
from PySide6 import QtWidgets as _QTWIDGETS
from PySide6.QtCore import Signal as pyqtSignal
from PySide6.QtCore import Slot as pyqtSlot

BINDING = "PySide6"

QtCore = _QTCORE
QtGui = _QTGUI
QtPrintSupport = _QTPRINTSUPPORT
QtSvg = _QTSVG
QtSvgWidgets = _QTSVGWIDGETS
QtWebChannel = _QTWEBCHANNEL
QtWebEngineCore = _QTWEBENGINECORE
QtWebEngineWidgets = _QTWEBENGINEWIDGETS
QtWidgets = _QTWIDGETS

__all__ = [
    "BINDING",
    "QtCore",
    "QtGui",
    "QtPrintSupport",
    "QtSvg",
    "QtWebChannel",
    "QtWebEngineCore",
    "QtWebEngineWidgets",
    "QtWidgets",
    "pyqtSignal",
    "pyqtSlot",
    "_QTCORE",
    "_QTGUI",
    "_QTPRINTSUPPORT",
    "_QTSVG",
    "_QTSVGWIDGETS",
    "QtSvgWidgets",
    "_QTWEBCHANNEL",
    "_QTWEBENGINECORE",
    "_QTWEBENGINEWIDGETS",
    "_QTWIDGETS",
]