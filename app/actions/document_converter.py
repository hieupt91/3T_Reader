import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import ssl
import urllib.request
import xml.etree.ElementTree as ET

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

def _xml_tag_name(tag: str) -> str:
    return str(tag).split("}", 1)[-1].split(":", 1)[-1]

def _xml_child(node, name: str):
    if node is None:
        return None
    for child in list(node):
        if _xml_tag_name(child.tag) == name:
            return child
    return None

def _xml_children(node, name: str) -> list:
    if node is None:
        return []
    return [child for child in list(node) if _xml_tag_name(child.tag) == name]

def _xml_path(node, *names: str):
    current = node
    for name in names:
        current = _xml_child(current, name)
        if current is None:
            return None
    return current

def _xml_text(node, *names: str) -> str:
    target = _xml_path(node, *names) if names else node
    return (target.text or "").strip() if target is not None else ""

def _fmt_number(value: str) -> str:
    try:
        number = float(str(value).replace(",", ""))
    except Exception:
        return value or ""
    if abs(number - round(number)) < 0.000001:
        return f"{int(round(number)):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")

def _draw_wrapped(c, text: str, x: float, y: float, width: float, font: str, size: float, leading: float) -> float:
    from reportlab.lib.utils import simpleSplit

    lines = simpleSplit(str(text or ""), font, size, width) or [""]
    c.setFont(font, size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y

def convert_xml_to_pdf(xml_path: str) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit
    from app.actions.document_ops import _resolve_reportlab_font

    root = ET.parse(xml_path).getroot()
    out_dir = Path(tempfile.gettempdir()) / "3t_reader_xml"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / (Path(xml_path).stem + ".pdf")

    c = canvas.Canvas(str(out_pdf), pagesize=A4)
    page_w, page_h = A4
    margin = 36
    usable_w = page_w - margin * 2
    y = page_h - margin
    font = _resolve_reportlab_font(False)
    bold = _resolve_reportlab_font(True)

    def new_page():
        nonlocal y
        c.showPage()
        y = page_h - margin

    def ensure(height: float):
        if y - height < margin:
            new_page()

    def section(title: str):
        nonlocal y
        ensure(28)
        y -= 6
        c.setFillColor(colors.HexColor("#eef3ff"))
        c.rect(margin, y - 16, usable_w, 20, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#102a43"))
        c.setFont(bold, 11)
        c.drawString(margin + 6, y - 10, title)
        y -= 28
        c.setFillColor(colors.black)

    def kv(label: str, value: str):
        nonlocal y
        value = str(value or "").strip()
        if not value:
            return
        text = f"{label}: {value}"
        lines = simpleSplit(text, font, 9, usable_w)
        ensure(max(14, len(lines) * 11))
        c.setFont(font, 9)
        for line in lines:
            c.drawString(margin + 4, y, line)
            y -= 11

    def table_header(cols, widths):
        nonlocal y
        ensure(24)
        x = margin
        c.setFillColor(colors.HexColor("#e5e7eb"))
        c.rect(margin, y - 16, sum(widths), 18, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont(bold, 8)
        for col, width in zip(cols, widths):
            c.drawString(x + 3, y - 11, col)
            x += width
        y -= 18

    def table_row(values, widths):
        nonlocal y
        wrapped = [simpleSplit(str(value or ""), font, 8, width - 5) or [""] for value, width in zip(values, widths)]
        row_h = max(18, max(len(lines) for lines in wrapped) * 10 + 6)
        if y - row_h < margin:
            new_page()
            table_header(["STT", "Tên hàng hóa/dịch vụ", "ĐVT", "SL", "Đơn giá", "Thành tiền", "Thuế"], widths)
        x = margin
        c.setFont(font, 8)
        for lines, width in zip(wrapped, widths):
            c.rect(x, y - row_h, width, row_h, fill=0, stroke=1)
            yy = y - 11
            for line in lines:
                c.drawString(x + 3, yy, line)
                yy -= 10
            x += width
        y -= row_h

    dlh = _xml_child(root, "DLHDon") or root
    ttchung = _xml_path(dlh, "TTChung")
    nd = _xml_path(dlh, "NDHDon")
    seller = _xml_path(nd, "NBan")
    buyer = _xml_path(nd, "NMua")
    totals = _xml_path(nd, "TToan")

    title = _xml_text(ttchung, "THDon") or "Tài liệu XML"
    c.setFont(bold, 16)
    c.drawCentredString(page_w / 2, y, title.upper())
    y -= 20
    c.setFont(font, 8)
    c.drawCentredString(page_w / 2, y, f"Nguồn: {xml_path}")
    y -= 18

    section("Thông tin chung")
    for label, value in [
        ("Ký hiệu mẫu số", _xml_text(ttchung, "KHMSHDon")),
        ("Ký hiệu hóa đơn", _xml_text(ttchung, "KHHDon")),
        ("Số hóa đơn", _xml_text(ttchung, "SHDon")),
        ("Ngày lập", _xml_text(ttchung, "NLap")),
        ("Tiền tệ", _xml_text(ttchung, "DVTTe")),
        ("Hình thức thanh toán", _xml_text(ttchung, "HTTToan")),
        ("Mã cơ quan thuế", _xml_text(root, "MCCQT")),
    ]:
        kv(label, value)

    section("Bên bán")
    for label, value in [
        ("Tên", _xml_text(seller, "Ten")),
        ("MST", _xml_text(seller, "MST")),
        ("Địa chỉ", _xml_text(seller, "DChi")),
        ("Điện thoại", _xml_text(seller, "SDThoai")),
        ("Email", _xml_text(seller, "DCTDTu")),
        ("Ngân hàng", _xml_text(seller, "TNHang")),
        ("Số tài khoản", _xml_text(seller, "STKNHang")),
    ]:
        kv(label, value)

    section("Bên mua")
    for label, value in [
        ("Tên", _xml_text(buyer, "Ten")),
        ("MST", _xml_text(buyer, "MST")),
        ("Địa chỉ", _xml_text(buyer, "DChi")),
        ("Mã khách hàng", _xml_text(buyer, "MKHang")),
        ("Người mua hàng", _xml_text(buyer, "HVTNMHang")),
    ]:
        kv(label, value)

    items = _xml_children(_xml_path(nd, "DSHHDVu"), "HHDVu")
    if items:
        section("Hàng hóa / dịch vụ")
        widths = [24, 210, 38, 42, 62, 72, 38]
        table_header(["STT", "Tên hàng hóa/dịch vụ", "ĐVT", "SL", "Đơn giá", "Thành tiền", "Thuế"], widths)
        for item in items:
            table_row(
                [
                    _xml_text(item, "STT"),
                    _xml_text(item, "THHDVu"),
                    _xml_text(item, "DVTinh"),
                    _fmt_number(_xml_text(item, "SLuong")),
                    _fmt_number(_xml_text(item, "DGia")),
                    _fmt_number(_xml_text(item, "ThTien")),
                    _xml_text(item, "TSuat"),
                ],
                widths,
            )

    section("Tổng cộng")
    for label, value in [
        ("Tổng tiền chưa thuế", _fmt_number(_xml_text(totals, "TgTCThue"))),
        ("Tổng tiền thuế", _fmt_number(_xml_text(totals, "TgTThue"))),
        ("Tổng thanh toán", _fmt_number(_xml_text(totals, "TgTTTBSo"))),
        ("Bằng chữ", _xml_text(totals, "TgTTTBChu")),
        ("QR Code", _xml_text(root, "DLQRCode")),
    ]:
        kv(label, value)

    if not ttchung and not nd:
        section("Nội dung XML")
        count = 0
        for elem in root.iter():
            text = (elem.text or "").strip()
            if not text:
                continue
            tag = _xml_tag_name(elem.tag)
            if tag in {"X509Certificate", "SignatureValue", "DigestValue"}:
                text = text[:120] + "..."
            kv(tag, text)
            count += 1
            if count >= 400:
                kv("Ghi chú", "Nội dung XML quá dài, chỉ hiển thị 400 trường đầu.")
                break

    c.save()
    return str(out_pdf)

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

def _find_itaxviewer_exe() -> str:
    if sys.platform != "win32":
        return ""

    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "iTax Viewer" / "iTaxViewer.exe",
        Path(os.environ.get("ProgramFiles", "")) / "iTax Viewer" / "iTaxViewer.exe",
        get_bin_dir() / "itaxviewer" / "iTaxViewer.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    for root in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        if not root:
            continue
        base = Path(root)
        if base.exists():
            for found in base.glob("iTax*/**/iTaxViewer.exe"):
                return str(found)
    return ""

def _open_xml_with_itaxviewer(window, xml_path: str) -> bool:
    exe = _find_itaxviewer_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([exe, xml_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        status = getattr(window, "status", None)
        if status is not None:
            status.showMessage("Đã mở file XML bằng iTaxViewer.", 5000)
        return True
    except Exception as e:
        QMessageBox.warning(window, _t("common.error", "Lỗi"), str(e))
        return False

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

        proc = subprocess.Popen(
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
        progress = QProgressDialog("Đang cài iTaxViewer ở chế độ nền...", "", 0, 0, window)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        while proc.poll() is None:
            QApplication.processEvents()
        progress.close()
        return proc.returncode == 0
    except Exception as e:
        QMessageBox.warning(window, _t("common.error", "Lỗi"), str(e))
        return False

def handle_xml_itax(window, file_path: str):
    if sys.platform != "win32":
        QMessageBox.warning(window, _t("doc.itax.title", "File Thuế XML"), _t("doc.itax.nowin", "Tính năng đọc file Thuế XML (iTaxViewer) trên MacOS đang trong quá trình cập nhật.\nXin vui lòng chờ các phiên bản tiếp theo."))
        return

    if _open_xml_with_itaxviewer(window, file_path):
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
            
        if _run_itax_installer_silent(window, temp_exe):
            if not _open_xml_with_itaxviewer(window, file_path):
                QMessageBox.warning(window, _t("common.error", "Lỗi"), "Đã cài iTaxViewer nhưng chưa tìm thấy iTaxViewer.exe để mở file XML.")

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
        return convert_xml_to_pdf(file_path)
        
    QMessageBox.warning(window, _t("common.error", "Lỗi"), _t("doc.unsupported", f"Định dạng {ext} chưa được hỗ trợ."))
    return ""
