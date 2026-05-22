from PySide6 import QtSvgWidgets as _mod


def __getattr__(name):
    return getattr(_mod, name)
