from __future__ import annotations

import os
import shutil
import tempfile
import time


_UNSET = object()


def current_viewer_page(window, default: int = 1) -> int:
    try:
        return max(1, int(window.viewer.get_current_page()))
    except Exception:
        return default


def current_viewer_zoom(window, default: str = "100") -> str:
    try:
        zoom = getattr(window.viewer, "_zoom", None)
        if zoom:
            return str(zoom)
    except Exception:
        pass
    return default


def remove_path_quietly(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def make_staged_pdf_path(target_path: str, *, prefix: str = ".3t_stage_", suffix: str = ".pdf") -> str:
    directory = os.path.dirname(os.path.abspath(target_path)) or os.getcwd()
    os.makedirs(directory, exist_ok=True)
    fd, staged_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    os.close(fd)
    return staged_path


def atomic_copy_file(source_path: str, target_path: str) -> None:
    staged_path = make_staged_pdf_path(target_path)
    try:
        shutil.copy2(source_path, staged_path)
        replace_file_with_retry(staged_path, target_path)
    except Exception:
        remove_path_quietly(staged_path)
        raise


def _pump_qt_events() -> None:
    try:
        from packages.qt_compat.QtWidgets import QApplication

        QApplication.processEvents()
    except Exception:
        pass


def release_viewer_file_lock(window) -> None:
    """Move QWebEngine away from the PDF before replacing the file on Windows."""
    try:
        from packages.qt_compat.QtCore import QUrl
    except Exception:
        return

    try:
        getter = getattr(window, "_get_webview", None)
        web_view = getter() if callable(getter) else None
        if web_view is None:
            return
        web_view.load(QUrl("about:blank"))
        _pump_qt_events()
        time.sleep(0.08)
        _pump_qt_events()
    except Exception:
        pass


def replace_file_with_retry(staged_path: str, target_path: str, *, attempts: int = 8) -> None:
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            os.replace(staged_path, target_path)
            return
        except PermissionError as exc:
            last_error = exc
            _pump_qt_events()
            time.sleep(0.08 * (attempt + 1))
    if last_error is not None:
        raise last_error
    os.replace(staged_path, target_path)


def reload_document(
    window,
    source_path: str,
    *,
    page: int | None = None,
    zoom: str | None = None,
    display_path=_UNSET,
    temp_path=_UNSET,
    soft_reload: bool = False,
) -> None:
    state = window._state_or_global() if hasattr(window, "_state_or_global") else None
    old_temp_path = state.get("temp_path") if isinstance(state, dict) else None
    target_zoom = str(zoom or current_viewer_zoom(window))

    window.current_path = source_path
    if isinstance(state, dict):
        if display_path is not _UNSET:
            state["display_path"] = display_path or source_path
        elif not state.get("display_path"):
            state["display_path"] = source_path

        if temp_path is not _UNSET:
            state["temp_path"] = temp_path

    new_temp_path = state.get("temp_path") if isinstance(state, dict) else None
    if old_temp_path and old_temp_path != new_temp_path and old_temp_path != source_path:
        remove_path_quietly(old_temp_path)

    target_page = max(1, int(page if page is not None else current_viewer_page(window)))
    
    if soft_reload and hasattr(window.viewer, "reload_soft"):
        window.viewer.reload_soft(source_path, zoom=target_zoom, page=target_page)
    elif hasattr(window.viewer, "reload_soft") and window.viewer._path == source_path and target_page == current_viewer_page(window):
        window.viewer.reload_soft(source_path, zoom=target_zoom, page=target_page)
    else:
        window.viewer.load_pdf(source_path, page=target_page, zoom=target_zoom)


def replace_document_with_staged(
    window,
    staged_path: str,
    *,
    target_path: str | None = None,
    keep_page: bool = True,
    page: int | None = None,
    display_path=_UNSET,
    temp_path=_UNSET,
    zoom: str | None = None,
    soft_reload: bool = True,
) -> str:
    if not staged_path:
        raise ValueError("Missing staged PDF path.")

    resolved_target = target_path or window.current_path
    if not resolved_target:
        raise ValueError("Missing target PDF path.")

    target_page = page if page is not None else (current_viewer_page(window) if keep_page else 1)
    
    use_soft_reload = False
    if (
        soft_reload
        and hasattr(window, "viewer")
        and hasattr(window.viewer, "reload_soft")
        and window.viewer._path == resolved_target
        and target_page == current_viewer_page(window)
    ):
        use_soft_reload = True

    try:
        if not use_soft_reload:
            release_viewer_file_lock(window)
        
        try:
            replace_file_with_retry(staged_path, resolved_target)
        except PermissionError:
            # If soft reload was attempted but file is locked, fallback to hard reload
            if use_soft_reload:
                use_soft_reload = False
                release_viewer_file_lock(window)
                replace_file_with_retry(staged_path, resolved_target, attempts=15)
            else:
                raise
    except Exception:
        remove_path_quietly(staged_path)
        raise

    if not use_soft_reload:
        reload_document(
            window,
            resolved_target,
            page=target_page,
            zoom=zoom,
            display_path=display_path,
            temp_path=temp_path,
            soft_reload=soft_reload,
        )
    else:
        # For soft reload, we just call the viewer directly to avoid redundant reload_document logic
        window.viewer.reload_soft(resolved_target, page=target_page, zoom=str(zoom or current_viewer_zoom(window)))
        
    return resolved_target
