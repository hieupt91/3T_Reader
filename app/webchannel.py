from __future__ import annotations

from packages.qt_compat.QtWebChannel import QWebChannel


def register_webchannel_object(web_view, parent, name: str, bridge):
    """Register a Qt bridge without replacing other active viewer bridges."""
    page = web_view.page()
    channel = getattr(web_view, "_3t_shared_webchannel", None)
    objects = getattr(web_view, "_3t_shared_webchannel_objects", None)
    if channel is None or objects is None:
        channel = QWebChannel(parent)
        objects = {}
        setattr(web_view, "_3t_shared_webchannel", channel)
        setattr(web_view, "_3t_shared_webchannel_objects", objects)
        page.setWebChannel(channel)

    old = objects.get(name)
    if old is not None:
        try:
            channel.deregisterObject(old)
        except Exception:
            pass

    channel.registerObject(name, bridge)
    objects[name] = bridge
    return channel


def unregister_webchannel_object(web_view, name: str | None = None) -> None:
    if web_view is None:
        return
    channel = getattr(web_view, "_3t_shared_webchannel", None)
    objects = getattr(web_view, "_3t_shared_webchannel_objects", None)
    if channel is None or not isinstance(objects, dict):
        return

    names = list(objects) if name is None else [name]
    for item in names:
        old = objects.pop(item, None)
        if old is None:
            continue
        try:
            channel.deregisterObject(old)
        except Exception:
            pass
