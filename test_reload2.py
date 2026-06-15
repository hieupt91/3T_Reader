import sys, os, urllib.parse
from PySide6.QtWidgets import QApplication
from app.pdf_viewer import PDFViewerWidget
from PySide6.QtCore import QTimer
from app.local_server import LocalPDFJSServer

with open("real.pdf", "wb") as f:
    f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 100 100]/Parent 2 0 R>>endobj xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000109 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n")

app = QApplication(sys.argv)
viewer = PDFViewerWidget()
viewer.show()

def on_ready():
    print("PDF loaded, triggering reload_soft")
    server = LocalPDFJSServer.get()
    abs_path = server.register_pdf(os.path.abspath("real.pdf"))
    encoded_path = urllib.parse.quote(abs_path)
    cache_key = "123"
    pdf_url = f"http://127.0.0.1:{server._port}/pdf?p={encoded_path}&v={cache_key}"
    js = f"""
    window.PDFViewerApplication.eventBus.on('pagerendered', function() {{
        console.log('PAGE RENDERED FIRED');
    }});
    fetch('{pdf_url}').then(res => res.arrayBuffer()).then(function(ab) {{
        return window.PDFViewerApplication.open({{ data: new Uint8Array(ab), url: '{pdf_url}', originalUrl: '{pdf_url}' }});
    }}).then(()=>console.log('OPEN SUCCESS')).catch(e=>console.log('OPEN ERROR:', e));
    """
    viewer._web_view.page().runJavaScript(js)
    QTimer.singleShot(2000, app.quit)

viewer.page_ready.connect(on_ready)
viewer.load_pdf(os.path.abspath("real.pdf"))
app.exec()
