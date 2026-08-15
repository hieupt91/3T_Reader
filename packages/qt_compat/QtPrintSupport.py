from . import _QTPRINTSUPPORT


def __getattr__(name):
    return getattr(_QTPRINTSUPPORT, name)