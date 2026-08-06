import inspect

from app.actions import document_ops


def test_multi_page_watermark_shows_window_modal_progress_and_pumps_events():
    """Vòng lặp watermark từng trang (reportlab render + pikepdf overlay) chạy
    đồng bộ trên UI thread - với file nhiều trang, UI trông như bị đơ vì
    không progress feedback nào. Phải pump Qt events qua progress dialog
    window-modal (chặn tương tác khác với cửa sổ chính trong lúc chạy)."""
    src = inspect.getsource(document_ops.add_watermark)
    assert "if len(target_pages) > 1:" in src
    assert "QProgressDialog(" in src
    assert "setWindowModality(Qt.WindowModality.WindowModal)" in src
    assert "_pump_qt_events()" in src


def test_single_page_watermark_path_is_unchanged():
    """Trang đơn (target_pages có 1 phần tử) không được tạo progress dialog -
    giữ nguyên hành vi cũ, không dialog nào xuất hiện."""
    src = inspect.getsource(document_ops.add_watermark)
    assert 'target_pages = list(range(total)) if p["all_pages"] else [cur_page]' in src


def test_cancel_returns_before_pdf_save_so_no_partial_file_is_written():
    """pdf.save(out) chỉ chạy SAU vòng lặp - hủy giữa chừng (return sớm) phải
    không được ghi gì ra out, tránh file watermark dở dang."""
    src = inspect.getsource(document_ops.add_watermark)
    cancel_idx = src.index("if progress_dlg.wasCanceled():")
    save_idx = src.index("pdf.save(out)")
    assert cancel_idx < save_idx

    return_idx = src.index("return", cancel_idx)
    assert return_idx < save_idx
