import os
import sys
from pathlib import Path

from packages.pdf_engine import get_pdf_engine
from packages.qt_compat import QtCore, QtWebEngineWidgets, QtWidgets, pyqtSignal
from PySide6.QtWebEngineCore import QWebEngineSettings


class PDFViewerWidget(QtWidgets.QWidget):
    """Internal PDF.js/QWebEngine viewer adapter.

    This replaces the GPL `pdfjs-viewer-pyqt6` wrapper at the app boundary.
    It loads the Apache-2.0 PDF.js bundle from `third_party/pdfjs` when
    available. A direct QWebEngine file fallback is kept for Phase 0 dev.
    """

    pdf_loaded = pyqtSignal(dict)
    page_changed = pyqtSignal(int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, preset: str | None = None, parent=None):
        super().__init__(parent)
        self._preset = preset
        self._path = ""
        self._page_count = 0
        self._current_page = 1
        self._zoom = "page-width"

        self._web_view = QtWebEngineWidgets.QWebEngineView(self)

        # Allow PDF.js (a local file:// page) to fetch the PDF (also file://)
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessLocalUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._web_view)

    def load_pdf(self, path: str, zoom: str = "page-width", page: int | None = None, pagemode: str | None = None):
        self._path = path
        self._zoom = zoom
        self._current_page = max(1, int(page or 1))

        try:
            self._page_count = get_pdf_engine().page_count(path)
        except Exception as exc:
            self._page_count = 0
            self.error_occurred.emit(str(exc))

        self._load_web_view(path, zoom=zoom, page=self._current_page, pagemode=pagemode)
        self.pdf_loaded.emit({"filename": os.path.basename(path), "path": path})
        self.page_changed.emit(self._current_page, self._page_count)

    def save_pdf(self):
        if not self._path:
            self.error_occurred.emit("Chưa mở tệp PDF.")

    def goto_page(self, page: int):
        self._current_page = max(1, min(int(page), max(1, self._page_count)))
        js = f"""
(function() {{
  if (window.PDFViewerApplication && PDFViewerApplication.pdfViewer) {{
    PDFViewerApplication.pdfViewer.currentPageNumber = {self._current_page};
  }}
}})();
"""
        self._web_view.page().runJavaScript(js)
        self.page_changed.emit(self._current_page, self._page_count)

    def get_current_page(self) -> int:
        return self._current_page

    def get_page_count(self) -> int:
        return self._page_count

    def findChild(self, child_type, name: str = ""):
        if child_type is QtWebEngineWidgets.QWebEngineView:
            return self._web_view
        return super().findChild(child_type, name)

    def _load_web_view(self, path: str, *, zoom: str, page: int, pagemode: str | None):
        viewer = self._pdfjs_viewer_path()
        pdf_url = QtCore.QUrl.fromLocalFile(os.path.abspath(path)).toString()
        if viewer:
            viewer_url = QtCore.QUrl.fromLocalFile(str(viewer)).toString()
            encoded_pdf = QtCore.QUrl.toPercentEncoding(pdf_url).data().decode()
            target_url = f"{viewer_url}?file={encoded_pdf}#page={page}"
            if zoom:
                target_url += f"&zoom={zoom}"
            if pagemode:
                target_url += f"&pagemode={pagemode}"
            self._web_view.load(QtCore.QUrl(target_url))
            return

        self._web_view.load(QtCore.QUrl.fromLocalFile(os.path.abspath(path)))

    def _pdfjs_viewer_path(self) -> Path | None:
        # Search order: sys._MEIPASS → Contents/MacOS/ → Contents/Resources/ → source root
        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            if hasattr(sys, "_MEIPASS"):
                candidates.append(Path(sys._MEIPASS))
            exe = Path(sys.executable).resolve()
            candidates.append(exe.parent)                       # Contents/MacOS/
            candidates.append(exe.parent.parent / "Resources")  # Contents/Resources/
        else:
            candidates.append(Path(__file__).resolve().parents[1])
        for root in candidates:
            viewer = root / "third_party" / "pdfjs" / "web" / "viewer.html"
            if viewer.exists():
                return viewer
        return None
