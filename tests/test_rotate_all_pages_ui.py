from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_rotate_pages_action_is_exposed_from_page_ui():
    # Nút ribbon "Xoay tất cả" (self._act_rall) và menu "Xoay trang..."
    # (act_rotate_all) cùng gọi rotate_pages_action - tên biến đổi khi
    # window.py chuyển sang helper _set(name, i18n_key, fallback) cho toàn
    # bộ action đăng ký (hoà giải piper-vps-sync 2026-08-05), hành vi UI
    # không đổi.
    window_source = _read("app/window.py")

    assert "from app.actions.pages import merge_pdfs_action, rotate_pages_action, split_pdf_action" in window_source
    assert "self._act_rall = make(" in window_source
    assert "lambda: rotate_pages_action(self)" in window_source
    assert "self.g_rot.add(make_action_btn(self._act_rall, \"Xoay tất cả\"))" in window_source
    assert 'act_rotate_all = menu_pages.addAction("Xoay trang… (chọn / tất cả)")' in window_source


def test_rotate_pages_dialog_keeps_all_pages_entry_point():
    pages_source = _read("app/actions/pages.py")

    assert "apply_all = QPushButton(\"Xoay TẤT CẢ trang\")" in pages_source
    assert "rotations = {pn: deg for pn in range(1, total + 1)}" in pages_source


def test_rotate_pages_writes_synchronously_then_reloads():
    # Rotate xoay THẬT (ghi /Rotate qua pdf engine) rồi reload mềm ngay -
    # không còn dùng CSS-transform JS + thumbnail QTransform hack tạm thời
    # (code cũ dùng biến js_code chưa từng định nghĩa -> NameError khi chạy,
    # đã bị loại bỏ khi hoà giải piper-vps-sync 2026-08-05).
    pages_source = _read("app/actions/pages.py")

    assert "get_pdf_engine().rotate_pages(path, tmp, rotations)" in pages_source
    assert "replace_document_with_staged(window, tmp, target_path=path," in pages_source
    assert "findChild(QWebEngineView)" not in pages_source
    assert "preview_rotations = rotations" not in pages_source
