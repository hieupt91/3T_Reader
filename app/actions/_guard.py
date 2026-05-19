from functools import wraps

from app.dialogs import show_warning


def require_document(show_message=False):
    """Decorator: skip action if no PDF is open."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(window, *args, **kwargs):
            if not window.current_path:
                if show_message:
                    show_warning(window, "Chưa mở tệp", "Vui lòng mở tệp PDF trước.")
                return
            return fn(window, *args, **kwargs)
        return wrapper
    return decorator


def require_webview(fn):
    """Decorator: skip action if no PDF webview available. Implies require_document."""
    @wraps(fn)
    def wrapper(window, *args, **kwargs):
        if not window.current_path:
            return
        wv = window._get_webview()
        if not wv:
            return
        return fn(window, wv, *args, **kwargs)
    return wrapper
