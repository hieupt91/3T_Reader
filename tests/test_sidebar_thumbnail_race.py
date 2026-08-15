"""Regression test cho BUG-01 (QA_REPORT/BUG_REPORT.md, tìm ra 15/08/2026 qua
GUI automation thật): thumbnail của trang liền kề trang đang chọn luôn hiện
trắng. Nguyên nhân: app/sidebar.py::ThumbnailSidebar._start_loader() GHI ĐÈ
self._pending_pages thay vì GỘP khi có yêu cầu tải mới trong lúc loader cũ
còn chạy - làm rơi mất trang đã yêu cầu ở lần gọi trước nếu lần tính lại
phạm vi hiển thị sau không còn tính trang đó vào phạm vi."""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, ".")

from packages.qt_compat.QtWidgets import QApplication

from app.sidebar import ThumbnailSidebar


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeRunningLoader:
    def isRunning(self):
        return True

    def requestInterruption(self):
        pass


def test_start_loader_merges_pending_pages_instead_of_overwriting(qapp):
    """Mô phỏng đúng kịch bản lỗi: lần gọi đầu yêu cầu trang 4 (nằm ở biên
    trên của phạm vi hiển thị), lần gọi thứ 2 (do 1 signal khác kích hoạt
    trong lúc loader đầu còn chạy) tính lại phạm vi và KHÔNG còn tính trang 4
    vào - trang 4 phải vẫn còn trong hàng đợi, không được rơi mất."""
    sidebar = ThumbnailSidebar()
    sidebar._pdf_path = "fake.pdf"
    sidebar._loader = _FakeRunningLoader()

    sidebar._start_loader([4, 5, 6, 7, 8])
    assert sidebar._pending_pages == [4, 5, 6, 7, 8]

    # Lần gọi thứ 2: phạm vi tính lại lệch đi, không còn trang 4
    sidebar._start_loader([5, 6, 7, 8, 9])

    assert 4 in sidebar._pending_pages, (
        "Trang 4 (yêu cầu ở lần gọi trước, chưa render) bị rơi mất khi "
        "_pending_pages bị ghi đè thay vì gộp - đúng nguyên nhân BUG-01"
    )
    assert set(sidebar._pending_pages) == {4, 5, 6, 7, 8, 9}


def test_start_loader_drops_already_loaded_pages_from_pending(qapp):
    """Trang đã render xong (trong _loaded_pages) không cần giữ lại trong
    hàng đợi dù có xuất hiện lại ở 1 trong 2 lần yêu cầu."""
    sidebar = ThumbnailSidebar()
    sidebar._pdf_path = "fake.pdf"
    sidebar._loader = _FakeRunningLoader()
    sidebar._loaded_pages = {5}

    sidebar._start_loader([4, 5, 6])
    sidebar._start_loader([5, 6, 7])

    assert sidebar._pending_pages == [4, 6, 7]


def test_start_loader_no_duplicate_pages_in_pending(qapp):
    sidebar = ThumbnailSidebar()
    sidebar._pdf_path = "fake.pdf"
    sidebar._loader = _FakeRunningLoader()

    sidebar._start_loader([4, 5])
    sidebar._start_loader([5, 6])

    assert sidebar._pending_pages == [4, 5, 6]
