import sys, os
from PySide6.QtWidgets import QApplication
from app.pdf_viewer import PDFViewerWidget
from PySide6.QtCore import QTimer

app = QApplication(sys.argv)
viewer = PDFViewerWidget()
viewer.show()

def on_ready():
    print("PDF loaded, triggering reload_soft")
    try:
        viewer.reload_soft(viewer._path)
    except Exception as e:
        print("Exception:", e)
    QTimer.singleShot(2000, app.quit)

viewer.page_ready.connect(on_ready)
viewer.load_pdf(os.path.abspath("real.pdf"))
app.exec()
