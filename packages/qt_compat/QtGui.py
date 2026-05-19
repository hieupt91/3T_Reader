from . import _QTGUI


def __getattr__(name):
    return getattr(_QTGUI, name)
