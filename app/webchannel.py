from __future__ import annotations

from packages.qt_compat.QtCore import QObject, pyqtSlot
from packages.qt_compat.QtWebChannel import QWebChannel


class _BridgeProxyBase(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = None

    def set_target(self, target) -> None:
        self._target = target

    def clear_target(self) -> None:
        self._target = None

    def _call(self, method_name: str, *args) -> None:
        target = self._target
        if target is None:
            return
        method = getattr(target, method_name, None)
        if callable(method):
            method(*args)


class _PageStateBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int, int)
    def reportState(self, page_number: int, zoom_percent: int):
        self._call("reportState", page_number, zoom_percent)


class _NoteToolsBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(str, int, float, float, float, float)
    def moveNote(self, note_id: str, page_number: int, left: float, bottom: float, right: float, top: float):
        self._call("moveNote", note_id, page_number, left, bottom, right, top)

    @pyqtSlot(str, int)
    def editNote(self, note_id: str, page_number: int):
        self._call("editNote", note_id, page_number)

    @pyqtSlot(str, int)
    def deleteNote(self, note_id: str, page_number: int):
        self._call("deleteNote", note_id, page_number)


class _AreaPickBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int, float, float, float, float)
    def reportArea(self, page_number: int, left: float, bottom: float, right: float, top: float):
        self._call("reportArea", page_number, left, bottom, right, top)

    @pyqtSlot()
    def cancelPick(self):
        self._call("cancelPick")


class _SignaturePickBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int, float, float, float, float)
    def reportPick(self, page_number: int, pdf_x: float, pdf_y: float, page_width: float, page_height: float):
        self._call("reportPick", page_number, pdf_x, pdf_y, page_width, page_height)

    @pyqtSlot(int, float, float, float, float, float, float)
    def reportArea(
        self,
        page_number: int,
        left: float,
        bottom: float,
        right: float,
        top: float,
        page_width: float,
        page_height: float,
    ):
        self._call("reportArea", page_number, left, bottom, right, top, page_width, page_height)

    @pyqtSlot()
    def cancelPick(self):
        self._call("cancelPick")


class _SignaturePreviewBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int, float, float, float, float)
    def reportAdjusted(self, page_number: int, left: float, bottom: float, right: float, top: float):
        self._call("reportAdjusted", page_number, left, bottom, right, top)


class _SignatureInfoBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int, str)
    def showSignatureInfo(self, page_number: int, field_name: str):
        self._call("showSignatureInfo", page_number, field_name)


class _InlineTextBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int)
    def reportReady(self, page_number: int):
        self._call("reportReady", page_number)

    @pyqtSlot(int, float, float, float, float, str)
    def confirmText(self, page_number: int, left: float, bottom: float, right: float, top: float, text: str):
        self._call("confirmText", page_number, left, bottom, right, top, text)

    @pyqtSlot()
    def cancelEdit(self):
        self._call("cancelEdit")


class _InlineImageBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int)
    def reportReady(self, page_number: int):
        self._call("reportReady", page_number)

    @pyqtSlot(int, float, float, float, float)
    def confirmImage(self, page_number: int, left: float, bottom: float, right: float, top: float):
        self._call("confirmImage", page_number, left, bottom, right, top)

    @pyqtSlot()
    def cancelEdit(self):
        self._call("cancelEdit")


class _ObjectActionBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(float)
    def reportRotation(self, angle: float):
        self._call("reportRotation", angle)

    @pyqtSlot()
    def reportDelete(self):
        self._call("reportDelete")

    @pyqtSlot()
    def reportEdit(self):
        self._call("reportEdit")

    @pyqtSlot()
    def reportMove(self):
        self._call("reportMove")

    @pyqtSlot()
    def reportDismiss(self):
        self._call("reportDismiss")

    @pyqtSlot()
    def reportRetry(self):
        self._call("reportRetry")

    @pyqtSlot(float, float, float, float)
    def reportDragMove(self, l: float, b: float, r: float, t: float):
        self._call("reportDragMove", l, b, r, t)

    @pyqtSlot(float, float, float, float, float)
    def reportResize(self, l: float, b: float, r: float, t: float, scale: float):
        self._call("reportResize", l, b, r, t, scale)


class _ExistingTextBridgeProxy(_BridgeProxyBase):
    @pyqtSlot(int, float, float, float, float, str, str)
    def reportExistingTextClick(self, page_number: int, left: float, bottom: float, right: float, top: float, text: str, styles: str):
        self._call("reportExistingTextClick", page_number, left, bottom, right, top, text, styles)


_PROXY_TYPES = {
    "pageStateBridge": _PageStateBridgeProxy,
    "noteToolsBridge": _NoteToolsBridgeProxy,
    "areaPickBridge": _AreaPickBridgeProxy,
    "sigPickBridge": _SignaturePickBridgeProxy,
    "sigPreviewBridge": _SignaturePreviewBridgeProxy,
    "signatureInfoBridge": _SignatureInfoBridgeProxy,
    "inlineTextBridge": _InlineTextBridgeProxy,
    "inlineImageBridge": _InlineImageBridgeProxy,
    "objectActionBridge": _ObjectActionBridgeProxy,
    "editExistingTextBridge": _ExistingTextBridgeProxy,
}

_SHORT_LIVED_BRIDGES = {
    "areaPickBridge",
    "sigPickBridge",
    "sigPreviewBridge",
    "inlineTextBridge",
    "inlineImageBridge",
    "objectActionBridge",
    "editExistingTextBridge",
}


def _ensure_shared_webchannel(web_view):
    channel = getattr(web_view, "_3t_shared_webchannel", None)
    proxies = getattr(web_view, "_3t_shared_webchannel_proxies", None)
    if channel is not None and isinstance(proxies, dict):
        return channel, proxies

    channel = QWebChannel(web_view)
    proxies = {}
    for name, proxy_type in _PROXY_TYPES.items():
        proxy = proxy_type(channel)
        proxies[name] = proxy
        channel.registerObject(name, proxy)
    setattr(web_view, "_3t_shared_webchannel", channel)
    setattr(web_view, "_3t_shared_webchannel_proxies", proxies)
    web_view.page().setWebChannel(channel)
    return channel, proxies


def register_webchannel_object(web_view, parent, name: str, bridge):
    """Register/update a Qt bridge target without replacing the viewer channel.

    QWebChannel clients in PDF.js are long-lived. Replacing page.setWebChannel()
    after JS already holds channel objects leaves stale callbacks on the JS side.
    We therefore expose stable proxy objects once per viewer and only swap their
    Python targets for short-lived tools such as note/sign/area-pick.
    """
    channel, proxies = _ensure_shared_webchannel(web_view)
    objects = getattr(web_view, "_3t_shared_webchannel_objects", None)
    if objects is None:
        objects = {}
        setattr(web_view, "_3t_shared_webchannel_objects", objects)

    objects[name] = bridge
    proxy = proxies.get(name)
    if proxy is None:
        # Unknown bridge names are not supported after JS initialization. Keep
        # this explicit so new tools add a proxy instead of reviving channel
        # replacement.
        raise KeyError(f"Unknown webchannel bridge name: {name}")
    proxy.set_target(bridge)
    return channel


def unregister_webchannel_object(web_view, name: str | None = None) -> None:
    if web_view is None:
        return
    _channel, proxies = _ensure_shared_webchannel(web_view)
    objects = getattr(web_view, "_3t_shared_webchannel_objects", None)
    if not isinstance(objects, dict):
        return

    if name is None:
        names = list(_SHORT_LIVED_BRIDGES)
    else:
        names = [name]
    for item in names:
        objects.pop(item, None)
        proxy = proxies.get(item)
        if proxy is not None:
            proxy.clear_target()
