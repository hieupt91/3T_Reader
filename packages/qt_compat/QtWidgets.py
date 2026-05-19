from . import _QTWIDGETS


def __getattr__(name):
    return getattr(_QTWIDGETS, name)
