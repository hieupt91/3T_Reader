from . import _QTCORE
from . import pyqtSignal, pyqtSlot


def __getattr__(name):
    return getattr(_QTCORE, name)