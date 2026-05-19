from . import _QTWEBCHANNEL


def __getattr__(name):
    return getattr(_QTWEBCHANNEL, name)
