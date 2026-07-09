import json
import os
from datetime import datetime

from app.actions._guard import require_document
from app.dialogs import show_info, show_warning


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _run_find(window, query: str, *, find_previous: bool, new_search: bool):
    wv = window._get_webview()
    if not wv:
        show_warning(window, "Chưa sẵn sàng", "Trình xem PDF chưa sẵn sàng để tìm kiếm.")
        return

    payload = {
        "query": query,
        "phraseSearch": True,
        "caseSensitive": False,
        "entireWord": False,
        "highlightAll": True,
        "findPrevious": find_previous,
        "matchDiacritics": False,
        "type": "" if new_search else "again",
    }

    js = f"""
(function() {{
    try {{
        const app = window.PDFViewerApplication;
        if (!app || !app.eventBus) {{
            return "PDF.js chưa khởi tạo xong";
        }}
        window.__3tFindState = 3;
        app.eventBus.dispatch("find", Object.assign({{ source: window }}, {json.dumps(payload)}));
        return "OK";
    }} catch (e) {{
        return String(e);
    }}
}})();
"""

    def _after(result):
        if result == "OK":
            window.status.showMessage(
                f"Đang tìm: '{query}'" + (" (lùi)" if find_previous else ""),
                3000,
            )
            # Schedule not-found check after PDF.js has had time to search
            viewer = window.viewer
            if viewer and new_search:
                viewer.check_find_result(query, delay_ms=700)
        elif result:
            show_warning(window, "Không thể tìm kiếm", str(result))

    wv.page().runJavaScript(js, _after)


def clear_search(window) -> None:
    """Xóa toàn bộ highlight tìm kiếm của PDF.js (TC28).

    Gửi query rỗng + findbarclose, reset findController nếu PDF.js expose API,
    và dọn các class highlight còn sót trong .textLayer. Im lặng khi chưa mở
    PDF (đóng thanh search lúc chưa có tài liệu không phải là lỗi).
    """
    window.search_query = ""
    wv = window._get_webview() if hasattr(window, "_get_webview") else None
    if not wv:
        return
    js = """
(function() {
    try {
        var app = window.PDFViewerApplication;
        if (app && app.eventBus) {
            app.eventBus.dispatch("find", {
                source: window, query: "", phraseSearch: true,
                caseSensitive: false, entireWord: false,
                highlightAll: false, findPrevious: false, type: ""
            });
            app.eventBus.dispatch("findbarclose", { source: window });
        }
        if (app && app.findController && typeof app.findController._reset === "function") {
            app.findController._reset();
        }
        var marked = document.querySelectorAll(
            ".textLayer .highlight, .textLayer .highlight.selected, .textLayer .appended"
        );
        for (var i = 0; i < marked.length; i++) {
            marked[i].classList.remove("highlight", "selected", "appended");
        }
    } catch (e) {}
})();
"""
    try:
        wv.page().runJavaScript(js)
    except Exception:
        pass


def execute_search(window, query: str, *, find_previous: bool = False, new_search: bool = True) -> bool:
    query = (query or "").strip()
    if not query:
        return False
    window.search_query = query
    _run_find(window, query, find_previous=find_previous, new_search=new_search)
    return True


@require_document(show_message=True)
def search_text(window):
    if hasattr(window, "show_search_panel"):
        window.show_search_panel()


def _search_direction(window, *, find_previous: bool):
    """Shared logic for search_next / search_previous."""
    if not window.current_path:
        show_warning(window, "Chưa mở tệp", "Vui lòng mở tệp PDF trước khi tìm kiếm.")
        return

    query = getattr(window, "search_query", "").strip()
    if not query:
        search_text(window)
        return
    execute_search(window, query, find_previous=find_previous, new_search=False)


def search_next(window):
    _search_direction(window, find_previous=False)


def search_previous(window):
    _search_direction(window, find_previous=True)


@require_document(show_message=True)
def show_file_info(window):
    source_path = window.current_path
    display_path = window.get_display_path() if hasattr(window, "get_display_path") else source_path
    try:
        stat = os.stat(source_path)
        size_text = _format_size(stat.st_size)
        modified_text = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
    except OSError as e:
        show_warning(window, "Không đọc được thông tin tệp", str(e))
        return

    page_count = window.viewer.get_page_count() if source_path else 0
    current_page = window.viewer.get_current_page() if source_path else 0

    message = (
        f"Tên tệp: {os.path.basename(display_path)}\n"
        f"Đường dẫn: {display_path}\n"
        f"Dung lượng: {size_text}\n"
        f"Số trang: {page_count}\n"
        f"Trang hiện tại: {current_page}\n"
        f"Cập nhật lần cuối: {modified_text}"
    )
    show_info(window, "Thông tin tệp PDF", message)
