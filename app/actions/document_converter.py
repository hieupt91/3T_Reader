import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import ssl
import urllib.request

from packages.qt_compat.QtWidgets import QMessageBox, QProgressDialog, QApplication
from packages.qt_compat.QtCore import Qt, QThread, pyqtSignal, QUrl
from packages.qt_compat.QtGui import QDesktopServices

from app.config import VPS_LICENSE_BASE_URL

MODULES_BASE_URL = f"{VPS_LICENSE_BASE_URL.rstrip('/')}/downloads/modules"

def _t(key: str, default: str) -> str:
    from app.language_manager import get_selected_language, get_translation
    return get_translation(get_selected_language(), key, default)

def get_bin_dir() -> Path:
    from packages.platform import get_app_data_dir
    return Path(get_app_data_dir()) / "modules"

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished_dl = pyqtSignal(bool, str)

    def __init__(self, url, dest_path):
        super().__init__()
        self.url = url
        self.dest_path = dest_path

    def run(self):
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(self.url, headers={"User-Agent": "3T_Reader"})
            context = ssl._create_unverified_context()
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=context),
            )
            with opener.open(req, timeout=120) as resp, open(self.dest_path, "wb") as out:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.progress.emit(int(downloaded * 100 / total))
            self.finished_dl.emit(True, "")
        except Exception as e:
            self.finished_dl.emit(False, str(e))

def download_and_extract_libreoffice(window) -> bool:
    is_win = sys.platform == "win32"
    zip_name = "libreoffice_win.zip" if is_win else "libreoffice_mac.zip"
    import time
    url = f"{MODULES_BASE_URL}/{zip_name}?v={int(time.time())}"
    
    # We will download it to temp, then extract to get_bin_dir() / "libreoffice"
    temp_zip = Path(tempfile.gettempdir()) / zip_name
    
    progress_dlg = QProgressDialog(_t("doc.dl.lo", "Đang tải bộ xử lý Word/Excel (LibreOffice)..."), _t("common.cancel", "Hủy"), 0, 100, window)
    progress_dlg.setWindowTitle(_t("doc.dl.title", "Tải Module Mở Rộng"))
    progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
    progress_dlg.setAutoClose(True)
    progress_dlg.show()
    
    thread = DownloadThread(url, temp_zip)
    thread.progress.connect(progress_dlg.setValue)
    
    success = False
    error_msg = ""
    
    def on_finished(ok, err):
        nonlocal success, error_msg
        success = ok
        error_msg = err
        
    thread.finished_dl.connect(on_finished)
    thread.start()
    
    while thread.isRunning():
        QApplication.processEvents()
        if progress_dlg.wasCanceled():
            thread.terminate()
            return False
            
    thread.wait()
    QApplication.processEvents()
            
    if not success:
        QMessageBox.warning(window, _t("common.error", "Lỗi"), _t("doc.dl.fail", "Tải thất bại: ") + error_msg)
        return False
        
    # Extract
    progress_dlg.setLabelText(_t("doc.dl.extract", "Đang giải nén bộ xử lý..."))
    progress_dlg.setRange(0, 0)
    progress_dlg.show()
    QApplication.processEvents()
    
    try:
        import subprocess
        dest_dir = get_bin_dir() / "libreoffice"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        if sys.platform == "win32":
            import zipfile
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
        else:
            subprocess.run(["unzip", "-q", "-o", str(temp_zip), "-d", str(dest_dir)], check=True)
            
        temp_zip.unlink(missing_ok=True)
    except Exception as e:
        QMessageBox.warning(window, _t("common.error", "Lỗi"), _t("doc.dl.extract_fail", "Giải nén thất bại: ") + str(e))
        progress_dlg.close()
        return False
        
    progress_dlg.close()
    return True

def get_libreoffice_bin() -> str:
    bin_dir = get_bin_dir() / "libreoffice"
    if sys.platform == "win32":
        path = bin_dir / "App" / "libreoffice" / "program" / "soffice.exe"
        if not path.exists():
            path = bin_dir / "program" / "soffice.exe"
    else:
        path = bin_dir / "Contents" / "MacOS" / "soffice"
        
    if path.exists():
        return str(path)
    if bin_dir.exists():
        exe_name = "soffice.exe" if sys.platform == "win32" else "soffice"
        for found in bin_dir.rglob(exe_name):
            if found.parent.name in {"program", "MacOS"}:
                return str(found)
        
    # Fallback to system wide
    if sys.platform == "win32":
        for p in [r"C:\Program Files\LibreOffice\program\soffice.exe"]:
            if os.path.exists(p): return p
    elif sys.platform == "darwin":
        if os.path.exists("/Applications/LibreOffice.app/Contents/MacOS/soffice"):
            return "/Applications/LibreOffice.app/Contents/MacOS/soffice"

    return ""

def convert_image_to_pdf(img_path: str) -> str:
    from PIL import Image
    out_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    img = Image.open(img_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(out_pdf, "PDF", resolution=100.0)
    return out_pdf

def _validate_pdf(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 5:
        return False
    with open(path, "rb") as fh:
        return fh.read(4) == b"%PDF"

def convert_office_to_pdf(window, file_path: str) -> str:
    # 1. Check for LibreOffice
    lo_bin = get_libreoffice_bin()
    if not lo_bin:
        ans = QMessageBox.question(
            window, 
            _t("doc.lo.missing", "Thiếu Bộ Xử Lý"),
            _t("doc.lo.prompt", "Để đọc file Word/Excel chính xác 100%, ứng dụng cần tải thêm Module LibreOffice (~150MB).\n\nBạn có muốn tải và cài đặt tự động không?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            if download_and_extract_libreoffice(window):
                lo_bin = get_libreoffice_bin()
            else:
                return ""
        else:
            return ""
            
    if not lo_bin:
        return ""
        
    # Show converting progress
    progress_dlg = QProgressDialog(_t("doc.conv.doing", "Đang chuyển đổi hiển thị (sẽ mất vài giây)..."), "", 0, 0, window)
    progress_dlg.setWindowTitle(_t("doc.conv.title", "Xử lý tài liệu"))
    progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
    progress_dlg.setCancelButton(None)
    progress_dlg.show()
    QApplication.processEvents()
    
    out_dir = Path(tempfile.gettempdir()) / "3t_reader_docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    expected_pdf = out_dir / (Path(file_path).stem + ".pdf")
    expected_pdf.unlink(missing_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix="3t_lo_profile_"))
    
    try:
        # Optimize cold start speed by disabling all UI, locks, and recovery checks
        cmd = [
            lo_bin, "--headless", "--invisible", "--nodefault", 
            "--nofirststartwizard", "--nolockcheck", "--nologo", "--norestore", 
            f"-env:UserInstallation={profile_dir.as_uri()}",
            "--convert-to", "pdf", "--outdir", str(out_dir), file_path
        ]
        
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=180,
            )
        else:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        
        progress_dlg.close()
        
        if _validate_pdf(expected_pdf):
            return str(expected_pdf)
        QMessageBox.warning(
            window,
            _t("common.error", "Lỗi"),
            _t("doc.conv.fail", "Chuyển đổi thất bại: ") + "LibreOffice không tạo được PDF hợp lệ.",
        )
    except Exception as e:
        progress_dlg.close()
        QMessageBox.warning(window, _t("common.error", "Lỗi"), _t("doc.conv.fail", "Chuyển đổi thất bại: ") + str(e))
        
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    return ""

def _run_itax_installer_silent(window, installer_path: Path) -> bool:
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs = {
            "startupinfo": startupinfo,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        subprocess.Popen(
            [
                str(installer_path),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/SP-",
            ],
            **kwargs,
        )
        status = getattr(window, "status", None)
        if status is not None:
            status.showMessage("Đang cài iTaxViewer ở chế độ nền...", 5000)
        return True
    except Exception as e:
        QMessageBox.warning(window, _t("common.error", "Lỗi"), str(e))
        return False

def handle_xml_itax(window):
    if sys.platform != "win32":
        QMessageBox.warning(window, _t("doc.itax.title", "File Thuế XML"), _t("doc.itax.nowin", "Tính năng đọc file Thuế XML (iTaxViewer) trên MacOS đang trong quá trình cập nhật.\nXin vui lòng chờ các phiên bản tiếp theo."))
        return

    ans = QMessageBox.question(
        window,
        _t("doc.itax.title", "File Thuế XML"),
        _t("doc.itax.prompt", "Để đọc định dạng XML đặc thù của Thuế, bạn cần cài đặt phần mềm iTaxViewer.\n\nBạn có muốn tải bản cài đặt chuẩn từ máy chủ 3T Reader không?"),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if ans == QMessageBox.StandardButton.Yes:
        import time
        url = f"{MODULES_BASE_URL}/itaxviewer_installer.exe?v={int(time.time())}"
        temp_exe = get_bin_dir() / "itaxviewer" / "itaxviewer_installer.exe"
        temp_exe.parent.mkdir(parents=True, exist_ok=True)
        
        progress_dlg = QProgressDialog(_t("doc.itax.dl", "Đang tải iTaxViewer..."), _t("common.cancel", "Hủy"), 0, 100, window)
        progress_dlg.setWindowTitle(_t("doc.dl.title", "Tải Module Mở Rộng"))
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setAutoClose(True)
        progress_dlg.show()
        
        thread = DownloadThread(url, temp_exe)
        thread.progress.connect(progress_dlg.setValue)
        
        success = False
        error_msg = ""
        
        def on_finished(ok, err):
            nonlocal success, error_msg
            success = ok
            error_msg = err
            
        thread.finished_dl.connect(on_finished)
        thread.start()
        
        while thread.isRunning():
            QApplication.processEvents()
            if progress_dlg.wasCanceled():
                thread.terminate()
                return
                
        thread.wait()
        QApplication.processEvents()
                
        if not success:
            QMessageBox.warning(window, _t("common.error", "Lỗi"), _t("doc.dl.fail", "Tải thất bại: ") + error_msg)
            return
            
        _run_itax_installer_silent(window, temp_exe)

def process_file_and_open(window, file_path: str):
    """
    Called from dropEvent or open action to convert non-PDFs to PDF.
    Returns path to PDF to open, or empty if handled or failed.
    """
    ext = Path(file_path).suffix.lower()
    
    if ext == ".pdf":
        return file_path
        
    if ext in (".png", ".jpg", ".jpeg", ".bmp"):
        return convert_image_to_pdf(file_path)
        
    if ext in (".doc", ".docx", ".xls", ".xlsx"):
        return convert_office_to_pdf(window, file_path)
        
    if ext == ".xml":
        handle_xml_itax(window)
        return ""
        
    QMessageBox.warning(window, _t("common.error", "Lỗi"), _t("doc.unsupported", f"Định dạng {ext} chưa được hỗ trợ."))
    return ""
