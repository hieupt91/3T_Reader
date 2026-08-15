from . import _QTWEBENGINEWIDGETS


def __getattr__(name):
    return getattr(_QTWEBENGINEWIDGETS, name)