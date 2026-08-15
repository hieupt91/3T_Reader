from . import _QTWEBENGINECORE


def __getattr__(name):
    return getattr(_QTWEBENGINECORE, name)
