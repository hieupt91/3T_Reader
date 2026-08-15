"""Lỗi ghi chú cũ: "chèn hình thành công nhưng hiển thị lại không ra".

Nguyên nhân: update_ops() gắn hook 'pagerendered'/'scalechanged' vào
eventBus ĐÚNG 1 LẦN (guard window.__3tOpsHooked) để vẽ lại overlay ảnh/chữ
đã chèn. reload_soft() (dùng bởi sign.py, pages.py, edit.py... cho các thao
tác "sửa tại chỗ không nhấp nháy") load lại tài liệu thật qua app.open() -
nếu PDF.js dựng lại eventBus mới, hook cũ trỏ vào eventBus cũ không còn tác
dụng, nhưng __3tOpsHooked vẫn true nên không bao giờ gắn lại được nữa. Ảnh/
chữ đã chèn "biến mất" sau đúng 1 lần soft-reload tiếp theo dù dữ liệu ops
vẫn còn nguyên.

QWebEngineView cần 1 trình duyệt Chromium con thật để chạy JS - không có
sẵn trong bộ test hiện tại (pdf_viewer.py chưa có test nào khác). Test này
kiểm tra ở mức MÃ NGUỒN: 2 phương thức update_ops()/reload_soft() phải
cùng tham chiếu đúng 1 hàm vẽ overlay toàn cục (window.__3tRenderOps),
và reload_soft() phải CHỦ ĐỘNG gọi lại hàm đó ngay sau khi tài liệu load
xong - không được chỉ trông cậy vào hook có thể đã chết."""
from __future__ import annotations

import inspect

from app.pdf_viewer import PDFViewerWidget


def test_update_ops_exposes_render_function_globally_not_only_local_closure():
    source = inspect.getsource(PDFViewerWidget.update_ops)
    assert "window.__3tRenderOps = " in source, (
        "renderOps() phải gán vào window.__3tRenderOps (không chỉ là hàm cục bộ trong "
        "closure của update_ops) để reload_soft() có thể gọi lại từ 1 khối JS tiêm riêng"
    )


def test_reload_soft_explicitly_redraws_ops_after_document_reloads():
    source = inspect.getsource(PDFViewerWidget.reload_soft)
    assert source.count("window.__3tRenderOps()") >= 2, (
        "reload_soft() phải CHỦ ĐỘNG gọi window.__3tRenderOps() sau khi app.open() load "
        "xong tài liệu (trong onRender lẫn nhánh fallback timeout) - không được chỉ trông "
        "cậy vào hook 'pagerendered' cũ (có thể đã chết nếu PDF.js dựng lại eventBus mới), "
        "nếu không ảnh/chữ đã chèn sẽ biến mất sau soft-reload"
    )
