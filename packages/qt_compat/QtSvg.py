from . import _QTSVG


def __getattr__(name):
    return getattr(_QTSVG, name)