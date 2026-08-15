from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import threading
import time

from app.local_server import LocalPDFJSServer


_UNSET = object()


def _same_path(a: str | None, b: str | None) -> bool:
    """So sánh 2 đường dẫn có trỏ tới CÙNG 1 file thật hay không, bỏ qua khác
    biệt vô hại (hoa/thường, dấu / và \\, tương đối/tuyệt đối). So sánh chuỗi
    thô (==) trước đây khiến eligibility check của soft-reload
    (replace_document_with_staged) trượt oan cho các file có 2 cách viết
    đường dẫn khác nhau nhưng CÙNG 1 file - rơi xuống hard reload (nhấp
    nháy + nhảy trang) dù đáng lẽ soft-reload được (lỗi thật: "đánh số
    trang / xóa số trang trình xem vẫn bị reload")."""
    if not a or not b:
        return a == b
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except Exception:
        return a == b


STALE_TEMP_MAX_AGE_SECONDS = 24 * 60 * 60
_EDIT_TEMP_DIR_NAME = "reader_pdf_edit"
_SIGN_TEMP_DIR_NAME = "reader_pdf_sig"
_EDIT_TEMP_PREFIXES = ("base_", "work_", "op_", "img_")
_SIGN_TEMP_PREFIXES = ("sig_",)
_STAGED_PDF_PREFIXES = (
    ".3t_stage_",
    ".3t_existing_sig_",
    ".3t_sigfields_",
    ".3t_pfx_signed_",
    ".3t_signed_",
    ".3t_handwritten_",
)


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


def _normalise_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except OSError:
        return None


def _active_path_set(paths) -> set[str]:
    active: set[str] = set()
    for path in paths or []:
        norm = _normalise_path(path)
        if norm:
            active.add(norm)
    return active


def _add_state_temp_paths(paths: set[str], state) -> None:
    if not isinstance(state, dict):
        return
    for key in ("source_path", "display_path", "temp_path"):
        value = state.get(key)
        if value:
            paths.add(str(value))

    edit_state = state.get("_pdf_edit_state")
    if not isinstance(edit_state, dict):
        return
    for key in ("original_path", "base_snapshot", "working_file"):
        value = edit_state.get(key)
        if value:
            paths.add(str(value))
    for op in edit_state.get("ops") or []:
        if isinstance(op, dict):
            image_path = op.get("image_path")
            if image_path:
                paths.add(str(image_path))


def collect_active_pdf_temp_paths(window) -> set[str]:
    """Collect paths currently referenced by tabs/edit sessions to avoid pruning them."""
    paths: set[str] = set()
    try:
        current_path = getattr(window, "current_path", None)
        if current_path:
            paths.add(str(current_path))
    except Exception:
        pass

    try:
        _add_state_temp_paths(paths, getattr(window, "_global_state", None))
    except Exception:
        pass

    try:
        active_state = window._active_state() if hasattr(window, "_active_state") else None
        _add_state_temp_paths(paths, active_state)
    except Exception:
        pass

    try:
        tabs_data = getattr(window, "_tabs_data", None)
        if isinstance(tabs_data, dict):
            for state in tabs_data.values():
                _add_state_temp_paths(paths, state)
    except Exception:
        pass

    try:
        session_paths = getattr(window, "_session_temp_paths", None)
        if isinstance(session_paths, set):
            for path in session_paths:
                if path:
                    paths.add(str(path))
    except Exception:
        pass
    return paths


def _prune_stale_files_in_dir(
    directory: str,
    *,
    prefixes: tuple[str, ...],
    active_paths: set[str],
    max_age_seconds: int,
    now: float,
    suffixes: tuple[str, ...] | None = None,
) -> int:
    try:
        directory = os.path.abspath(directory)
    except OSError:
        return 0
    if not os.path.isdir(directory):
        return 0

    removed = 0
    try:
        names = os.listdir(directory)
    except OSError:
        return 0

    max_age_seconds = max(0, int(max_age_seconds))
    for name in names:
        lower_name = name.lower()
        if not lower_name.startswith(prefixes):
            continue
        if suffixes and not lower_name.endswith(suffixes):
            continue
        path = os.path.join(directory, name)
        norm = _normalise_path(path)
        if not norm or norm in active_paths:
            continue
        try:
            if not os.path.isfile(path):
                continue
            if now - os.path.getmtime(path) < max_age_seconds:
                continue
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed


def prune_stale_staged_pdf_files(
    target_or_directory: str,
    *,
    active_paths=None,
    max_age_seconds: int = STALE_TEMP_MAX_AGE_SECONDS,
) -> int:
    """Remove old `.3t_*` staged PDFs from the target directory only."""
    if not target_or_directory:
        return 0
    target = os.path.abspath(str(target_or_directory))
    directory = target if os.path.isdir(target) else os.path.dirname(target)
    if not directory:
        return 0
    return _prune_stale_files_in_dir(
        directory,
        prefixes=_STAGED_PDF_PREFIXES,
        suffixes=(".pdf",),
        active_paths=_active_path_set(active_paths),
        max_age_seconds=max_age_seconds,
        now=time.time(),
    )


def prune_stale_app_temp_files(
    *,
    active_paths=None,
    max_age_seconds: int = STALE_TEMP_MAX_AGE_SECONDS,
    stage_dirs=None,
) -> int:
    """Prune stale app-owned temp files without touching currently referenced paths."""
    active = _active_path_set(active_paths)
    temp_root = tempfile.gettempdir()
    now = time.time()
    removed = 0
    removed += _prune_stale_files_in_dir(
        os.path.join(temp_root, _EDIT_TEMP_DIR_NAME),
        prefixes=_EDIT_TEMP_PREFIXES,
        active_paths=active,
        max_age_seconds=max_age_seconds,
        now=now,
    )
    removed += _prune_stale_files_in_dir(
        os.path.join(temp_root, _SIGN_TEMP_DIR_NAME),
        prefixes=_SIGN_TEMP_PREFIXES,
        active_paths=active,
        max_age_seconds=max_age_seconds,
        now=now,
    )
    for entry in stage_dirs or []:
        removed += prune_stale_staged_pdf_files(
            str(entry),
            active_paths=active,
            max_age_seconds=max_age_seconds,
        )
    return removed


def make_staged_pdf_path(target_path: str, *, prefix: str = ".3t_stage_", suffix: str = ".pdf") -> str:
    directory = os.path.dirname(os.path.abspath(target_path)) or os.getcwd()
    os.makedirs(directory, exist_ok=True)
    prune_stale_staged_pdf_files(directory, active_paths=[target_path])
    fd, staged_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    os.close(fd)
    return staged_path


def atomic_copy_file(source_path: str, target_path: str, *, window=None) -> None:
    staged_path = make_staged_pdf_path(target_path)
    try:
        shutil.copy2(source_path, staged_path)
        replace_file_with_retry(staged_path, target_path, window=window)
    except Exception:
        remove_path_quietly(staged_path)
        raise


_pumping_events = False


def _pump_qt_events() -> None:
    """Bơm event loop Qt 1 lần - CHẶN bơm lồng nhau (tái nhập cùng thread).

    Windows fatal exception 0x8001010d (COM RPC_E_CANTCALLOUT_ININPUTSYNCCALL)
    đã ghi nhận lặp lại trong app_log.txt, bắt nguồn từ đúng kiểu bơm
    processEvents() lồng nhau này: 1 lần ghi PDF (rotate/sign/xoá trang...)
    đang giữ pdf_write_slot và tự bơm event loop (vd. qua
    wait_for_thumbnail_idle/release_viewer_file_lock) có thể khiến 1 timer
    khác (autosave chú thích 350ms) chạy luôn trong lúc đó, gọi lại
    pdf_write_slot cho CÙNG file và tự bơm tiếp - bơm lồng bên trong bơm là
    kịch bản COM reentrancy kinh điển trên Windows. Lệnh gọi ngoài cùng vẫn
    bơm bình thường; lệnh gọi tái nhập chỉ no-op và để vòng lặp gọi hàm này
    tự time.sleep() rồi thử lại - lần ghi đang giữ slot không cần được bơm
    hộ mới xong việc (pikepdf/ghi đĩa không phụ thuộc event loop)."""
    global _pumping_events
    if _pumping_events:
        return
    _pumping_events = True
    try:
        from packages.qt_compat.QtWidgets import QApplication

        QApplication.processEvents()
    except Exception:
        pass
    finally:
        _pumping_events = False


def _retry_viewer_load_if_blank(window, source_path: str, *, page: int, zoom: str, delay_ms: int = 1200) -> None:
    try:
        from packages.qt_compat.QtCore import QTimer
    except Exception:
        return

    viewer = getattr(window, "viewer", None)
    if viewer is None:
        return

    def _retry() -> None:
        current_viewer = getattr(window, "viewer", None)
        if current_viewer is None or current_viewer is not viewer:
            return
        if getattr(current_viewer, "_path", "") != source_path:
            return
        if getattr(current_viewer, "_page_count", 0) > 0:
            return
        current_viewer.load_pdf(source_path, page=page, zoom=zoom)

    QTimer.singleShot(max(0, int(delay_ms)), _retry)


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


def _thumbnail_sidebar_is_loading(window, target_path: str) -> bool:
    sidebar = getattr(window, "sidebar", None)
    is_loading = getattr(sidebar, "is_loading", None)
    try:
        return bool(callable(is_loading) and is_loading(target_path))
    except Exception:
        return False


def wait_for_thumbnail_idle(window, target_path: str | None, *, timeout_s: float = 6.0) -> None:
    """Block until ThumbnailSidebar is done rendering `target_path` (or `timeout_s` elapses).

    pypdfium2 can hard-crash the whole process (native access violation, not a
    catchable Python exception) if a document's file on disk is replaced while
    ThumbnailLoader (app/sidebar.py) still holds a document handle open on it.
    Every path that overwrites the currently-open PDF funnels through
    replace_file_with_retry/replace_document_with_staged, so this is called
    from there rather than at each call site.
    """
    if window is None or not target_path:
        return
    deadline = time.monotonic() + max(0.0, timeout_s)
    while _thumbnail_sidebar_is_loading(window, target_path) and time.monotonic() < deadline:
        _pump_qt_events()
        time.sleep(0.1)


_active_pdf_writes: set[str] = set()
_pdf_write_owners: dict[str, int] = {}
_pdf_write_depths: dict[str, int] = {}


def _acquire_pdf_write_slot(target_path: str | None, *, timeout_s: float = 20.0) -> str:
    """Chờ tới khi `target_path` rảnh rồi đánh dấu bận - nửa "acquire" của
    pdf_write_slot(), tách riêng để dùng được cho thao tác chạy nền (acquire
    trên main thread TRƯỚC khi spawn worker, release trên main thread SAU
    khi worker xong - xem _rotate_page). Luôn gọi trên main thread, giống
    hệt như pdf_write_slot() vẫn luôn được dùng, để _active_pdf_writes chỉ
    bị mutate từ 1 thread duy nhất (không cần khóa thread-safe riêng)."""
    norm = _normalise_path(target_path) or target_path or ""
    if not norm:
        return ""
    owner = threading.get_ident()
    if norm in _active_pdf_writes and _pdf_write_owners.get(norm) == owner:
        _pdf_write_depths[norm] = _pdf_write_depths.get(norm, 1) + 1
        return norm
    deadline = time.monotonic() + max(0.0, timeout_s)
    while norm in _active_pdf_writes and time.monotonic() < deadline:
        # Qt event pumping can re-enter a writer on the GUI thread.  Preserve
        # the historical bounded, non-deadlocking behaviour for that one
        # thread; a different OS thread must never race through the lock.
        _pump_qt_events()
        time.sleep(0.05)
    if norm in _active_pdf_writes:
        raise TimeoutError("PDF dang duoc mot tac vu khac ghi; vui long thu lai sau.")
    _active_pdf_writes.add(norm)
    _pdf_write_owners[norm] = owner
    _pdf_write_depths[norm] = 1
    return norm


def _release_pdf_write_slot(norm: str) -> None:
    if norm:
        depth = _pdf_write_depths.get(norm, 1) - 1
        if depth > 0:
            _pdf_write_depths[norm] = depth
            return
        _pdf_write_depths.pop(norm, None)
        _pdf_write_owners.pop(norm, None)
        _active_pdf_writes.discard(norm)


@contextlib.contextmanager
def pdf_write_slot(target_path: str | None, *, timeout_s: float = 20.0):
    """Serialize the full read-modify-write sequence (open PDF, mutate,
    save-to-staged, atomic replace) for a given file across every writer
    (save/sign/OCR/pages/annotate/watermark...), so two writers never both
    read the same on-disk state and silently lose one side's change
    (last-replace-wins).

    Deliberately NOT a threading.Lock: several writers already pump the Qt
    event loop while they run (wait_for_thumbnail_idle above,
    release_viewer_file_lock's processEvents in replace_document_with_staged)
    - pumping can re-enter another writer for the SAME file on the SAME
    thread (e.g. the debounced annotation-autosave QTimer firing while a
    page-delete's write is still in flight). A plain Lock is not reentrant:
    the outer call would deadlock the whole UI trying to wait on a lock it
    already holds on that thread, with no other thread able to release it.
    Polling + pumping events while "busy" instead means a reentrant call
    just keeps waiting (bounded by timeout_s) without blocking the event
    loop, so it always resolves - either the busy writer finishes and
    releases the slot, or, in the extreme case, the wait times out and this
    call proceeds anyway rather than hanging forever.
    """
    norm = _acquire_pdf_write_slot(target_path, timeout_s=timeout_s)
    try:
        yield
    finally:
        _release_pdf_write_slot(norm)


def replace_file_with_retry(staged_path: str, target_path: str, *, attempts: int = 8, window=None) -> None:
    wait_for_thumbnail_idle(window, target_path)
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
    else:
        window.viewer.load_pdf(source_path, page=target_page, zoom=target_zoom)
        _retry_viewer_load_if_blank(window, source_path, page=target_page, zoom=target_zoom)


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

    wait_for_thumbnail_idle(window, resolved_target)

    target_page = page if page is not None else (current_viewer_page(window) if keep_page else 1)
    
    use_soft_reload = False
    if (
        soft_reload
        and hasattr(window, "viewer")
        and hasattr(window.viewer, "reload_soft")
        and _same_path(getattr(window.viewer, "_path", None), resolved_target)
    ):
        use_soft_reload = True

    try:
        if not use_soft_reload:
            release_viewer_file_lock(window)
        
        try:
            replace_file_with_retry(staged_path, resolved_target)
            try:
                LocalPDFJSServer.get().invalidate_pdf_cache(resolved_target)
            except Exception:
                pass
        except PermissionError:
            # If soft reload was attempted but file is locked, fallback to hard reload
            if use_soft_reload:
                use_soft_reload = False
                release_viewer_file_lock(window)
                replace_file_with_retry(staged_path, resolved_target, attempts=15)
                try:
                    LocalPDFJSServer.get().invalidate_pdf_cache(resolved_target)
                except Exception:
                    pass
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
        # reload_soft() (app/pdf_viewer.py) hoãn tải lại tối đa 4s nếu người
        # dùng đang giữ 1 vùng bôi đen (tránh phá selection đang thao tác dở -
        # xem comment __3tWaitThenReload trong reload_soft). Trong lúc chờ đó,
        # trang vẫn hiện đúng y nguyên nội dung TRƯỚC khi sửa/xoay (chưa kịp
        # nạp lại) mà không có dấu hiệu nào đang tải - dễ hiểu lầm là thao tác
        # không có tác dụng hoặc bị mất (phát hiện live 2026-08-14: xoay + chèn
        # chữ xong, màn hình đứng yên y hệt bản gốc suốt vài giây). Báo trạng
        # thái để người dùng biết đang xử lý, tự ẩn khi xong hoặc hết hạn.
        # Trì hoãn 1 nhịp event-loop: hầu hết caller (vd _RotatePageRelay) tự
        # show message "Đã xoay trang..." NGAY sau khi hàm này return - gọi
        # showMessage() đồng bộ ở đây sẽ bị đè mất tức khắc.
        status = getattr(window, "status", None)
        if status is not None:
            try:
                from packages.qt_compat.QtCore import QTimer

                QTimer.singleShot(150, lambda: status.showMessage("Đang cập nhật lại trang...", 8000))
            except Exception:
                pass
        # For soft reload, we just call the viewer directly to avoid redundant reload_document logic
        window.viewer.reload_soft(resolved_target, page=target_page, zoom=str(zoom or current_viewer_zoom(window)))

    return resolved_target
