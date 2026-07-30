import inspect

from app.sidebar import BookmarkSidebar, _OutlineLoader


def test_load_outline_runs_in_background_not_on_ui_thread():
    """pikepdf.open_outline() đệ quy toàn bộ cây mục lục - với file outline lớn,
    chạy đồng bộ trên UI thread gây lag mỗi lần mở file (B4). load_outline()
    phải giao việc đọc cho _OutlineLoader chạy nền, không gọi _read_outline
    trực tiếp."""
    src = inspect.getsource(BookmarkSidebar.load_outline)
    assert "_OutlineLoader(self._read_outline, pdf_path)" in src
    assert "loader.start()" in src
    assert "self._read_outline(pdf_path)" not in src


def test_stale_outline_result_is_ignored_after_newer_load_or_clear():
    """Nếu user mở file khác (hoặc đóng file) trong lúc loader cũ vẫn đang
    chạy nền, kết quả trả về muộn của loader cũ không được ghi đè lên tree
    của file hiện tại."""
    ready_src = inspect.getsource(BookmarkSidebar._on_outline_ready)
    assert "token != self._outline_token" in ready_src
    assert "self.sender()" in ready_src

    load_src = inspect.getsource(BookmarkSidebar.load_outline)
    assert "self._outline_token += 1" in load_src
    assert "loader.outline_token = self._outline_token" in load_src

    clear_src = inspect.getsource(BookmarkSidebar.clear)
    assert "self._outline_token += 1" in clear_src


def test_outline_loader_emits_from_background_thread_via_bound_method():
    """_OutlineLoader dùng threading.Thread thô (không moveToThread), cùng
    kiểu ThumbnailLoader trong file này - phải emit qua signal để Qt tự lo
    thread affinity, không được gọi thẳng logic Qt (vd _apply_outline) từ
    trong run()."""
    run_src = inspect.getsource(_OutlineLoader.run)
    assert "self.outlineReady.emit(outline)" in run_src
    assert "_apply_outline" not in run_src


def test_apply_outline_builds_tree_from_flat_level_title_page_tuples():
    src = inspect.getsource(BookmarkSidebar._apply_outline)
    assert "stack[-1][1].addChild(item)" in src
    assert "self._tree.addTopLevelItem(item)" in src
    assert "self._page_items.setdefault(int(page), []).append(item)" in src
