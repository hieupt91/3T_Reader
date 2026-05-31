from __future__ import annotations

import os
import shutil
import tempfile


_UNSET = object()


def current_viewer_page(window, default: int = 1) -> int:
    try:
        return max(1, int(window.viewer.get_current_page()))
    except Exception:
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
        os.replace(staged_path, target_path)
    except Exception:
        remove_path_quietly(staged_path)
        raise


def reload_document(
    window,
    source_path: str,
    *,
    page: int | None = None,
    zoom: str = "page-width",
    display_path=_UNSET,
    temp_path=_UNSET,
) -> None:
    state = window._state_or_global() if hasattr(window, "_state_or_global") else None
    old_temp_path = state.get("temp_path") if isinstance(state, dict) else None

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
    window.viewer.load_pdf(source_path, page=target_page, zoom=zoom)


def replace_document_with_staged(
    window,
    staged_path: str,
    *,
    target_path: str | None = None,
    keep_page: bool = True,
    page: int | None = None,
    display_path=_UNSET,
    temp_path=_UNSET,
) -> str:
    if not staged_path:
        raise ValueError("Missing staged PDF path.")

    resolved_target = target_path or window.current_path
    if not resolved_target:
        raise ValueError("Missing target PDF path.")

    target_page = page if page is not None else (current_viewer_page(window) if keep_page else 1)
    try:
        os.replace(staged_path, resolved_target)
    except Exception:
        remove_path_quietly(staged_path)
        raise

    reload_document(
        window,
        resolved_target,
        page=target_page,
        display_path=display_path,
        temp_path=temp_path,
    )
    return resolved_target
