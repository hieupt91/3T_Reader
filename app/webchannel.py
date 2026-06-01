from __future__ import annotations

from packages.qt_compat.QtWebChannel import QWebChannel


def register_webchannel_object(web_view, parent, name: str, bridge):
    """Register a Qt bridge without replacing other active viewer bridges."""
    page = web_view.page()
    objects = getattr(web_view, "_3t_shared_webchannel_objects", None)
    if objects is None:
        objects = {}
        setattr(web_view, "_3t_shared_webchannel_objects", objects)

    objects[name] = bridge

    # QWebChannel warns and existing JS clients cannot see objects registered
    # after channel initialization. Rebuild a fresh channel with all active
    # objects registered before exposing it to the page.
    channel = QWebChannel(parent)
    for object_name, object_bridge in objects.items():
        channel.registerObject(object_name, object_bridge)
    setattr(web_view, "_3t_shared_webchannel", channel)
    page.setWebChannel(channel)
    return channel


def unregister_webchannel_object(web_view, name: str | None = None) -> None:
    if web_view is None:
        return
    objects = getattr(web_view, "_3t_shared_webchannel_objects", None)
    if not isinstance(objects, dict):
        return

    names = list(objects) if name is None else [name]
    for item in names:
        objects.pop(item, None)

    channel = QWebChannel(web_view)
    for object_name, object_bridge in objects.items():
        channel.registerObject(object_name, object_bridge)
    setattr(web_view, "_3t_shared_webchannel", channel)
    web_view.page().setWebChannel(channel)
