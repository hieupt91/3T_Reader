import sys
import os
import subprocess
import tempfile
import threading
import urllib.request
import json

from app.config import UPDATE_CHANNEL, UPDATE_MANIFEST_URL
from app.version import APP_VERSION, PRODUCT_CODE


def _get_latest_release() -> dict | None:
    """Fetch the signed update manifest from the future VPS update API."""
    if not UPDATE_MANIFEST_URL:
        return None
    url = (
        f"{UPDATE_MANIFEST_URL}?product={PRODUCT_CODE}"
        f"&channel={UPDATE_CHANNEL}&version={APP_VERSION}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "3T-Reader-Updater"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _parse_version(v: str) -> tuple:
    """'1.2.3' → (1, 2, 3)"""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def _pick_manifest_version(data: dict) -> str:
    return (
        data.get("version")
        or data.get("latest_version")
        or data.get("tag_name")
        or ""
    )


def _pick_manifest_url(data: dict) -> str:
    return (
        data.get("url")
        or data.get("download_url")
        or data.get("browser_download_url")
        or ""
    )


def check_and_prompt_update(parent_window):
    """
    Chạy trong thread riêng để không block UI.
    Nếu có bản mới → hiện dialog hỏi user.
    """
    def _worker():
        data = _get_latest_release()
        if not data:
            return

        latest_version = _pick_manifest_version(data)
        if not latest_version:
            return

        if _parse_version(latest_version) <= _parse_version(APP_VERSION):
            return  # Đang dùng bản mới nhất rồi

        installer_url = _pick_manifest_url(data)
        installer_name = data.get("filename") or data.get("name") or ""

        if not installer_url:
            assets = data.get("assets", [])
            for asset in assets:
                name = asset.get("name", "")
                if name.endswith(".exe") and "setup" in name.lower():
                    installer_url = asset.get("browser_download_url")
                    installer_name = name
                    break

        if not installer_name and installer_url:
            installer_name = os.path.basename(installer_url.split("?", 1)[0]) or "3T_Reader_Update.exe"

        if not installer_url:
            return

        # Hiện dialog trên main thread
        from packages.qt_compat.QtCore import QMetaObject, Qt, Q_ARG
        from packages.qt_compat.QtWidgets import QMessageBox

        def _show_dialog():
            reply = QMessageBox.question(
                parent_window,
                "Có bản cập nhật mới",
                f"Phiên bản mới: {latest_version}\n"
                f"Phiên bản hiện tại: {APP_VERSION}\n\n"
                f"Bạn có muốn cập nhật ngay không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                _download_and_run(installer_url, installer_name, parent_window)

        # Gọi dialog từ main thread
        from packages.qt_compat.QtCore import QTimer
        QTimer.singleShot(0, _show_dialog)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _download_and_run(url: str, filename: str, parent_window):
    """Tải installer về temp rồi chạy."""
    from packages.qt_compat.QtWidgets import QProgressDialog, QMessageBox
    from packages.qt_compat.QtCore import Qt

    tmp_dir = tempfile.mkdtemp()
    save_path = os.path.join(tmp_dir, filename)

    progress = QProgressDialog("Đang tải bản cập nhật...", "Hủy", 0, 100, parent_window)
    progress.setWindowTitle("Cập nhật")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.show()

    def _reporthook(block_num, block_size, total_size):
        if progress.wasCanceled():
            raise Exception("Cancelled")
        if total_size > 0:
            percent = min(100, int(block_num * block_size * 100 / total_size))
            progress.setValue(percent)

    try:
        urllib.request.urlretrieve(url, save_path, _reporthook)
        progress.close()
        # Chạy installer và thoát app hiện tại
        subprocess.Popen([save_path], shell=False)
        parent_window.close()
    except Exception as e:
        progress.close()
        if "Cancelled" not in str(e):
            QMessageBox.warning(parent_window, "Lỗi tải xuống", f"Không tải được bản cập nhật:\n{e}")
