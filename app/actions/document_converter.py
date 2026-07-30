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
        self._cancelled = False

    def cancel(self):
        """Ask run() to stop between chunks instead of force-killing the thread.

        QThread.terminate() kills the thread at whatever instruction it happens
        to be executing (including mid network I/O), which can leave process
        state corrupted or crash outright. Cooperative cancellation checked
        between reads is the safe alternative.
        """
        self._cancelled = True

    def run(self):
        try:
            from packages.net_utils import make_ssl_context

            req = urllib.request.Request(self.url, headers={"User-Agent": "3T_Reader"})
            ssl_ctx = make_ssl_context()
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl_ctx),
            )
            with opener.open(req, timeout=120) as resp, open(self.dest_path, "wb") as out:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                while True:
                    if self._cancelled:
                        self.finished_dl.emit(False, "cancelled")
                        return
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
    
    cancelled = False
    while thread.isRunning():
        QApplication.processEvents()
        if progress_dlg.wasCanceled() and not cancelled:
            cancelled = True
            thread.cancel()

    thread.wait()
    QApplication.processEvents()

    if cancelled:
        try:
            Path(temp_zip).unlink(missing_ok=True)
        except OSError:
            pass
        return False
            
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

    def tax_title(text: str, size: int = 14):
        nonlocal y
        lines = simpleSplit(str(text or ""), bold, size, usable_w) or [""]
        ensure(len(lines) * (size + 3) + 4)
        c.setFont(bold, size)
        for line in lines:
            c.drawCentredString(page_w / 2, y, line)
            y -= size + 3

    def node_values(node) -> dict:
        if node is None:
            return {}
        return {_xml_tag_name(child.tag): _xml_text(child) for child in list(node)}

    def ordered_codes(*groups) -> list:
        codes = []
        seen = set()
        for group in groups:
            if group is None:
                continue
            for child in list(group):
                code = _xml_tag_name(child.tag)
                if code not in seen:
                    seen.add(code)
                    codes.append(code)
        return codes

    balance_labels = {
        "ct110": "Tài sản ngắn hạn",
        "ct120": "Tiền và các khoản tương đương tiền",
        "ct121": "Tiền",
        "ct122": "Các khoản tương đương tiền",
        "ct123": "Đầu tư tài chính ngắn hạn",
        "ct124": "Dự phòng giảm giá đầu tư tài chính ngắn hạn",
        "ct130": "Các khoản phải thu ngắn hạn",
        "ct131": "Phải thu khách hàng",
        "ct132": "Trả trước cho người bán",
        "ct133": "Vốn kinh doanh ở đơn vị trực thuộc",
        "ct134": "Phải thu khác",
        "ct135": "Tài sản thiếu chờ xử lý",
        "ct136": "Dự phòng phải thu ngắn hạn khó đòi",
        "ct140": "Hàng tồn kho",
        "ct141": "Hàng tồn kho",
        "ct142": "Dự phòng giảm giá hàng tồn kho",
        "ct150": "Tài sản ngắn hạn khác",
        "ct151": "Thuế GTGT được khấu trừ",
        "ct152": "Thuế và các khoản khác phải thu Nhà nước",
        "ct160": "Tài sản dài hạn",
        "ct161": "Tài sản cố định",
        "ct162": "Bất động sản đầu tư",
        "ct170": "Các khoản đầu tư tài chính dài hạn",
        "ct180": "Tài sản dài hạn khác",
        "ct181": "Phải thu dài hạn",
        "ct182": "Tài sản dài hạn khác",
        "ct200": "Tổng cộng tài sản",
        "ct300": "Nợ phải trả",
        "ct311": "Phải trả người bán",
        "ct312": "Người mua trả tiền trước",
        "ct313": "Thuế và các khoản phải nộp Nhà nước",
        "ct314": "Phải trả người lao động",
        "ct315": "Phải trả khác",
        "ct316": "Vay và nợ thuê tài chính",
        "ct317": "Dự phòng phải trả",
        "ct318": "Quỹ khen thưởng, phúc lợi",
        "ct319": "Quỹ phát triển khoa học và công nghệ",
        "ct320": "Nợ dài hạn",
        "ct400": "Vốn chủ sở hữu",
        "ct411": "Vốn góp của chủ sở hữu",
        "ct412": "Thặng dư vốn cổ phần",
        "ct413": "Vốn khác của chủ sở hữu",
        "ct414": "Cổ phiếu quỹ",
        "ct415": "Chênh lệch tỷ giá hối đoái",
        "ct416": "Các quỹ thuộc vốn chủ sở hữu",
        "ct417": "Lợi nhuận sau thuế chưa phân phối",
        "ct500": "Tổng cộng nguồn vốn",
    }
    kqhd_labels = {
        "ct01": "Doanh thu bán hàng và cung cấp dịch vụ",
        "ct02": "Các khoản giảm trừ doanh thu",
        "ct10": "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
        "ct11": "Giá vốn hàng bán",
        "ct20": "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
        "ct21": "Doanh thu hoạt động tài chính",
        "ct22": "Chi phí tài chính",
        "ct23": "Trong đó: Chi phí lãi vay",
        "ct24": "Chi phí quản lý kinh doanh",
        "ct30": "Lợi nhuận thuần từ hoạt động kinh doanh",
        "ct31": "Thu nhập khác",
        "ct32": "Chi phí khác",
        "ct40": "Lợi nhuận khác",
        "ct50": "Tổng lợi nhuận kế toán trước thuế",
        "ct51": "Chi phí thuế thu nhập doanh nghiệp",
        "ct60": "Lợi nhuận sau thuế thu nhập doanh nghiệp",
    }
    lctt_labels = {
        "ct01": "Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác",
        "ct02": "Tiền chi trả cho người cung cấp hàng hóa, dịch vụ",
        "ct03": "Tiền chi trả cho người lao động",
        "ct04": "Tiền lãi vay đã trả",
        "ct05": "Thuế thu nhập doanh nghiệp đã nộp",
        "ct06": "Tiền thu khác từ hoạt động kinh doanh",
        "ct07": "Tiền chi khác cho hoạt động kinh doanh",
        "ct20": "Lưu chuyển tiền thuần từ hoạt động kinh doanh",
        "ct21": "Tiền chi để mua sắm, xây dựng TSCĐ và tài sản dài hạn khác",
        "ct22": "Tiền thu từ thanh lý, nhượng bán TSCĐ và tài sản dài hạn khác",
        "ct23": "Tiền chi cho vay, mua công cụ nợ của đơn vị khác",
        "ct24": "Tiền thu hồi cho vay, bán lại công cụ nợ của đơn vị khác",
        "ct25": "Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia",
        "ct30": "Lưu chuyển tiền thuần từ hoạt động đầu tư",
        "ct31": "Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu",
        "ct32": "Tiền trả lại vốn góp cho chủ sở hữu, mua lại cổ phiếu đã phát hành",
        "ct33": "Tiền thu từ đi vay",
        "ct34": "Tiền trả nợ gốc vay và nợ thuê tài chính",
        "ct35": "Cổ tức, lợi nhuận đã trả cho chủ sở hữu",
        "ct40": "Lưu chuyển tiền thuần từ hoạt động tài chính",
        "ct50": "Lưu chuyển tiền thuần trong kỳ",
        "ct60": "Tiền và tương đương tiền đầu kỳ",
        "ct61": "Ảnh hưởng của thay đổi tỷ giá hối đoái",
        "ct70": "Tiền và tương đương tiền cuối kỳ",
    }
    account_labels = {
        "111": "Tiền mặt",
        "1111": "Tiền Việt Nam",
        "1112": "Ngoại tệ",
        "112": "Tiền gửi ngân hàng",
        "1121": "Tiền Việt Nam",
        "1122": "Ngoại tệ",
        "121": "Chứng khoán kinh doanh",
        "128": "Đầu tư nắm giữ đến ngày đáo hạn",
        "1281": "Tiền gửi có kỳ hạn",
        "1288": "Các khoản đầu tư khác nắm giữ đến ngày đáo hạn",
        "131": "Phải thu của khách hàng",
        "133": "Thuế GTGT được khấu trừ",
        "1331": "Thuế GTGT được khấu trừ của hàng hóa, dịch vụ",
        "1332": "Thuế GTGT được khấu trừ của TSCĐ",
        "136": "Phải thu nội bộ",
        "1361": "Vốn kinh doanh ở đơn vị trực thuộc",
        "1368": "Phải thu nội bộ khác",
        "138": "Phải thu khác",
        "1381": "Tài sản thiếu chờ xử lý",
        "1386": "Cầm cố, thế chấp, ký quỹ, ký cược",
        "1388": "Phải thu khác",
        "141": "Tạm ứng",
        "151": "Hàng mua đang đi đường",
        "152": "Nguyên liệu, vật liệu",
        "153": "Công cụ, dụng cụ",
        "154": "Chi phí sản xuất, kinh doanh dở dang",
        "155": "Thành phẩm",
        "156": "Hàng hóa",
        "157": "Hàng gửi đi bán",
        "211": "Tài sản cố định",
        "2111": "Tài sản cố định hữu hình",
        "2112": "Tài sản cố định thuê tài chính",
        "2113": "Tài sản cố định vô hình",
        "214": "Hao mòn tài sản cố định",
        "2141": "Hao mòn TSCĐ hữu hình",
        "2142": "Hao mòn TSCĐ thuê tài chính",
        "2143": "Hao mòn TSCĐ vô hình",
        "2147": "Hao mòn bất động sản đầu tư",
        "217": "Bất động sản đầu tư",
        "228": "Đầu tư góp vốn vào đơn vị khác",
        "2281": "Đầu tư vào công ty liên doanh, liên kết",
        "2288": "Đầu tư khác",
        "229": "Dự phòng tổn thất tài sản",
        "2291": "Dự phòng giảm giá chứng khoán kinh doanh",
        "2292": "Dự phòng tổn thất đầu tư vào đơn vị khác",
        "2293": "Dự phòng phải thu khó đòi",
        "2294": "Dự phòng giảm giá hàng tồn kho",
        "241": "Xây dựng cơ bản dở dang",
        "2411": "Mua sắm TSCĐ",
        "2412": "Xây dựng cơ bản",
        "2413": "Sửa chữa lớn TSCĐ",
        "242": "Chi phí trả trước",
        "331": "Phải trả cho người bán",
        "333": "Thuế và các khoản phải nộp Nhà nước",
        "3331": "Thuế GTGT phải nộp",
        "33311": "Thuế GTGT đầu ra",
        "33312": "Thuế GTGT hàng nhập khẩu",
        "3332": "Thuế tiêu thụ đặc biệt",
        "3333": "Thuế xuất, nhập khẩu",
        "3334": "Thuế thu nhập doanh nghiệp",
        "3335": "Thuế thu nhập cá nhân",
        "3336": "Thuế tài nguyên",
        "3337": "Thuế nhà đất, tiền thuê đất",
        "3338": "Thuế bảo vệ môi trường và các loại thuế khác",
        "33381": "Thuế bảo vệ môi trường",
        "33382": "Các loại thuế khác",
        "3339": "Phí, lệ phí và các khoản phải nộp khác",
        "334": "Phải trả người lao động",
        "335": "Chi phí phải trả",
        "336": "Phải trả nội bộ",
        "3361": "Phải trả nội bộ về vốn kinh doanh",
        "3368": "Phải trả nội bộ khác",
        "338": "Phải trả, phải nộp khác",
        "3381": "Tài sản thừa chờ giải quyết",
        "3382": "Kinh phí công đoàn",
        "3383": "Bảo hiểm xã hội",
        "3384": "Bảo hiểm y tế",
        "3385": "Bảo hiểm thất nghiệp",
        "3386": "Nhận ký quỹ, ký cược",
        "3387": "Doanh thu chưa thực hiện",
        "3388": "Phải trả, phải nộp khác",
        "341": "Vay và nợ thuê tài chính",
        "3411": "Các khoản đi vay",
        "3412": "Nợ thuê tài chính",
        "352": "Dự phòng phải trả",
        "3521": "Dự phòng bảo hành sản phẩm, hàng hóa",
        "3522": "Dự phòng bảo hành công trình xây dựng",
        "3524": "Dự phòng phải trả khác",
        "353": "Quỹ khen thưởng, phúc lợi",
        "3531": "Quỹ khen thưởng",
        "3532": "Quỹ phúc lợi",
        "3533": "Quỹ phúc lợi đã hình thành TSCĐ",
        "3534": "Quỹ thưởng ban quản lý điều hành công ty",
        "356": "Quỹ phát triển khoa học và công nghệ",
        "3561": "Quỹ phát triển khoa học và công nghệ",
        "3562": "Quỹ phát triển khoa học và công nghệ đã hình thành TSCĐ",
        "411": "Vốn đầu tư của chủ sở hữu",
        "4111": "Vốn góp của chủ sở hữu",
        "4112": "Thặng dư vốn cổ phần",
        "4118": "Vốn khác",
        "413": "Chênh lệch tỷ giá hối đoái",
        "418": "Các quỹ thuộc vốn chủ sở hữu",
        "419": "Cổ phiếu quỹ",
        "421": "Lợi nhuận sau thuế chưa phân phối",
        "4211": "Lợi nhuận sau thuế chưa phân phối năm trước",
        "4212": "Lợi nhuận sau thuế chưa phân phối năm nay",
        "511": "Doanh thu bán hàng và cung cấp dịch vụ",
        "5111": "Doanh thu bán hàng hóa",
        "5112": "Doanh thu bán thành phẩm",
        "5113": "Doanh thu cung cấp dịch vụ",
        "5118": "Doanh thu khác",
        "515": "Doanh thu hoạt động tài chính",
        "611": "Mua hàng",
        "631": "Giá thành sản xuất",
        "632": "Giá vốn hàng bán",
        "635": "Chi phí tài chính",
        "642": "Chi phí quản lý kinh doanh",
        "6421": "Chi phí bán hàng",
        "6422": "Chi phí quản lý doanh nghiệp",
        "711": "Thu nhập khác",
        "811": "Chi phí khác",
        "821": "Chi phí thuế thu nhập doanh nghiệp",
        "911": "Xác định kết quả kinh doanh",
    }

    def tax_table_header(cols, widths):
        nonlocal y
        ensure(26)
        x = margin
        c.setFillColor(colors.HexColor("#dbeafe"))
        c.rect(margin, y - 18, sum(widths), 20, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont(bold, 7.5)
        for col, width in zip(cols, widths):
            lines = simpleSplit(str(col or ""), bold, 7.5, width - 6) or [""]
            yy = y - 8
            for line in lines[:2]:
                c.drawString(x + 3, yy, line)
                yy -= 8
            x += width
        y -= 20

    def tax_table_row(values, widths, numeric_cols=None, strong=False):
        nonlocal y
        numeric_cols = set(numeric_cols or [])
        row_font = bold if strong else font
        wrapped = [simpleSplit(str(value or ""), row_font, 7.5, width - 6) or [""] for value, width in zip(values, widths)]
        row_h = max(18, max(len(lines) for lines in wrapped) * 9 + 6)
        if y - row_h < margin:
            new_page()
            return False
        x = margin
        c.setFont(row_font, 7.5)
        for idx, (lines, width) in enumerate(zip(wrapped, widths)):
            c.rect(x, y - row_h, width, row_h, fill=0, stroke=1)
            yy = y - 10
            for line in lines:
                if idx in numeric_cols:
                    c.drawRightString(x + width - 3, yy, line)
                else:
                    c.drawString(x + 3, yy, line)
                yy -= 9
            x += width
        y -= row_h
        return True

    def draw_tax_table(title, headers, widths, rows, numeric_cols=None, total_codes=None):
        section(title)
        tax_table_header(headers, widths)
        total_codes = set(total_codes or [])
        for row in rows:
            while not tax_table_row(row, widths, numeric_cols, strong=str(row[0]) in total_codes):
                tax_table_header(headers, widths)

    def format_tax_value(value: str) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        return _fmt_number(value)

    def render_group_table(title, parent, group_names, headers, labels, show_all=True):
        groups = [_xml_child(parent, name) for name in group_names]
        values_by_group = [node_values(group) for group in groups]
        rows = []
        for code in ordered_codes(*groups):
            vals = [format_tax_value(values.get(code, "")) for values in values_by_group]
            if not show_all and not any(v and v != "0" for v in vals):
                continue
            rows.append([code, labels.get(code, code), *vals])
        if rows:
            widths = [38, 190, 48, 116, 116] if len(group_names) == 3 else [42, 230, 118, 118]
            draw_tax_table(title, headers, widths, rows, numeric_cols=range(3, len(headers)), total_codes={"ct110", "ct200", "ct300", "ct400", "ct500", "ct10", "ct20", "ct30", "ct40", "ct50", "ct60", "ct70"})

    def render_cdtk_table(pluc):
        cdtk = _xml_child(pluc, "PL_CDTK")
        if cdtk is None:
            return
        groups = [
            (_xml_path(cdtk, "SoDuDauKy", "No"), _xml_path(cdtk, "SoDuDauKy", "Co")),
            (_xml_path(cdtk, "SoPhatSinh", "No"), _xml_path(cdtk, "SoPhatSinh", "Co")),
            (_xml_path(cdtk, "SoDuCuoiKy", "No"), _xml_path(cdtk, "SoDuCuoiKy", "Co")),
        ]
        code_groups = [item for pair in groups for item in pair]
        value_maps = [(node_values(no), node_values(co)) for no, co in groups]
        rows = []
        for code in ordered_codes(*code_groups):
            vals = []
            for no_vals, co_vals in value_maps:
                vals.extend([format_tax_value(no_vals.get(code, "")), format_tax_value(co_vals.get(code, ""))])
            if any(v and v != "0" for v in vals):
                if code == "tongCong":
                    rows.append(["Tổng cộng", "", *vals])
                    continue
                account_no = code[2:] if code.startswith("ct") else code
                rows.append([account_no, account_labels.get(account_no, f"Tài khoản {account_no}"), *vals])
        if rows:
            headers = ["TK", "Tên tài khoản", "Đầu kỳ Nợ", "Đầu kỳ Có", "Phát sinh Nợ", "Phát sinh Có", "Cuối kỳ Nợ", "Cuối kỳ Có"]
            widths = [34, 120, 58, 58, 62, 62, 58, 58]
            draw_tax_table("Bảng cân đối tài khoản", headers, widths, rows, numeric_cols=range(2, 8), total_codes={"Tổng cộng"})

    def render_tax_declaration() -> bool:
        nonlocal y
        hoso = _xml_child(root, "HSoKhaiThue") if _xml_tag_name(root.tag) != "HSoKhaiThue" else root
        if hoso is None:
            return False

        tkhai = _xml_path(hoso, "TTinChung", "TTinTKhaiThue", "TKhaiThue")
        nnt = _xml_path(hoso, "TTinChung", "TTinTKhaiThue", "NNT")
        ctieu = _xml_child(hoso, "CTieuTKhaiChinh")
        pluc = _xml_child(hoso, "PLuc")

        title = _xml_text(tkhai, "tenTKhai") or "Tờ khai thuế"
        tax_title(title.upper(), 14)
        subtitle = _xml_text(tkhai, "moTaBMau")
        if subtitle:
            tax_title(subtitle, 8)
        y -= 4

        period = _xml_text(tkhai, "KyKKhaiThue", "kyKKhai")
        date_from = _xml_text(tkhai, "KyKKhaiThue", "kyKKhaiTuNgay")
        date_to = _xml_text(tkhai, "KyKKhaiThue", "kyKKhaiDenNgay")
        if date_from or date_to:
            period = f"{date_from} - {date_to}".strip(" -")

        section("Thông tin tờ khai")
        for label, value in [
            ("Mã tờ khai", _xml_text(tkhai, "maTKhai")),
            ("Kỳ kê khai", period),
            ("Loại tờ khai", _xml_text(tkhai, "loaiTKhai")),
            ("Lần nộp", _xml_text(tkhai, "soLan")),
            ("Cơ quan thuế", _xml_text(tkhai, "tenCQTNoiNop")),
            ("Ngày lập tờ khai", _xml_text(tkhai, "ngayLapTKhai")),
            ("Ngày ký", _xml_text(tkhai, "ngayKy")),
        ]:
            kv(label, value)

        section("Người nộp thuế")
        for label, value in [
            ("Mã số thuế", _xml_text(nnt, "mst")),
            ("Tên người nộp thuế", _xml_text(nnt, "tenNNT")),
            ("Địa chỉ", _xml_text(nnt, "dchiNNT")),
            ("Tỉnh/Thành phố", _xml_text(nnt, "tenTinhNNT")),
            ("Điện thoại", _xml_text(nnt, "dthoaiNNT")),
            ("Email", _xml_text(nnt, "emailNNT")),
        ]:
            kv(label, value)

        if ctieu is not None:
            render_group_table(
                "Bảng cân đối kế toán",
                ctieu,
                ["ThuyetMinh", "SoCuoiNam", "SoDauNam"],
                ["Mã", "Chỉ tiêu", "TM", "Số cuối năm", "Số đầu năm"],
                balance_labels,
            )
            section("Thông tin lập biểu")
            for label, value in [
                ("BCTC đã kiểm toán", _xml_text(ctieu, "bctcDaKiemToan")),
                ("Người lập biểu", _xml_text(ctieu, "nguoiLapBieu")),
                ("Kế toán trưởng", _xml_text(ctieu, "keToanTruong")),
                ("Ngày lập", _xml_text(ctieu, "ngayLap")),
                ("Người đại diện theo pháp luật", _xml_text(ctieu, "nguoiDaiDienTheoPhapLuat")),
            ]:
                kv(label, value)

        if pluc is not None:
            kqhd = _xml_child(pluc, "PL_KQHDSXKD")
            if kqhd is not None:
                render_group_table(
                    "Kết quả hoạt động sản xuất kinh doanh",
                    kqhd,
                    ["ThuyetMinh", "NamNay", "NamTruoc"],
                    ["Mã", "Chỉ tiêu", "TM", "Năm nay", "Năm trước"],
                    kqhd_labels,
                )
            lctt = _xml_child(pluc, "PL_LCTTTT")
            if lctt is not None:
                render_group_table(
                    "Lưu chuyển tiền tệ",
                    lctt,
                    ["ThuyetMinh", "NamNay", "NamTruoc"],
                    ["Mã", "Chỉ tiêu", "TM", "Năm nay", "Năm trước"],
                    lctt_labels,
                )
            render_cdtk_table(pluc)

        c.save()
        return True

    if render_tax_declaration():
        return str(out_pdf)

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
