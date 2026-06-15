import sys, os, urllib.parse
from PySide6.QtWidgets import QApplication
from app.pdf_viewer import PDFViewerWidget
from PySide6.QtCore import QTimer
from app.local_server import LocalPDFJSServer

app = QApplication(sys.argv)
viewer = PDFViewerWidget()
viewer.show()

def on_ready():
    print("PDF loaded, triggering app.open({url: ...})")
    server = LocalPDFJSServer.get()
    abs_path = server.register_pdf(os.path.abspath("real.pdf"))
    encoded_path = urllib.parse.quote(abs_path)
    cache_key = "123"
    pdf_url = f"http://127.0.0.1:{server._port}/pdf?p={encoded_path}&v={cache_key}"
    js = f"window.PDFViewerApplication.open({{url: '{pdf_url}'}}).then(()=>console.log('OPEN SUCCESS URL:', window.PDFViewerApplication.url)).catch(e=>console.log('OPEN ERROR:', e));"
    viewer._web_view.page().runJavaScript(js)
    QTimer.singleShot(2000, app.quit)

viewer.page_ready.connect(on_ready)
viewer.load_pdf(os.path.abspath("real.pdf"))
app.exec()
