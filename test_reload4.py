import sys, os, urllib.parse
from PySide6.QtWidgets import QApplication
from app.pdf_viewer import PDFViewerWidget
from PySide6.QtCore import QTimer
from app.local_server import LocalPDFJSServer

app = QApplication(sys.argv)
viewer = PDFViewerWidget()
viewer.show()

js = """
window.PDFViewerApplication.eventBus.on('pagerendered', function() {
    console.log('PAGE RENDERED FIRED');
});
"""

def on_ready():
    viewer._web_view.page().runJavaScript(js)
    QTimer.singleShot(2000, app.quit)

viewer.page_ready.connect(on_ready)
viewer.load_pdf(os.path.abspath("real.pdf"))
app.exec()
