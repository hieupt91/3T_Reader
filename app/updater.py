import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

from packages.qt_compat.QtCore import QObject, pyqtSignal

from app.config import UPDATE_MANIFEST_URL
from app.version import APP_VERSION
from packages.updater.update_client import UpdateInfo, download_update


class UpdateCheckWorker(QObject):
    finished = pyqtSignal()
    available = pyqtSignal(object)
    up_to_date = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, base_url: str, current_version: str, channel: str):
        super().__init__()
        self._base_url = base_url
        self._current_version = current_version
        self._channel = channel

    def run(self):
        try:
            from app.config import VPS_LICENSE_BASE_URL
            from app.version import APP_VERSION
            from packages.updater.update_client import check_for_update

            base_url = self._base_url or VPS_LICENSE_BASE_URL
            current_version = self._current_version or APP_VERSION
            platform = "win" if sys.platform == "win32" else "mac"
            info = check_for_update(base_url, current_version, platform=platform)
            if info.available:
                self.available.emit(info)
            else:
                self.up_to_date.emit(info)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


def _get_latest_release() -> dict | None:
    if not UPDATE_MANIFEST_URL:
        return None
    platform = "win" if sys.platform == "win32" else "mac"
    query = urllib.parse.urlencode(
        {
            "platform": platform,
            "current_version": APP_VERSION,
        }
    )
    url = f"{UPDATE_MANIFEST_URL}?{query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "3T-Reader-Updater"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def _pick_manifest_version(data: dict) -> str:
    return data.get("version") or data.get("latest_version") or data.get("tag_name") or ""


def _pick_manifest_url(data: dict) -> str:
    return data.get("url") or data.get("download_url") or data.get("browser_download_url") or ""


def check_and_prompt_update(parent_window):
    def _worker():
        data = _get_latest_release()
        if not data:
            return

        latest_version = _pick_manifest_version(data)
        if not latest_version or _parse_version(latest_version) <= _parse_version(APP_VERSION):
            return

        installer_url = _pick_manifest_url(data)
        if not installer_url:
            assets = data.get("assets", [])
            for asset in assets:
                name = asset.get("name", "")
                if name.endswith(".exe") and "setup" in name.lower():
                    installer_url = asset.get("browser_download_url")
                    break
        if not installer_url:
            return

        info = UpdateInfo(
            available=True,
            current_version=APP_VERSION,
            latest_version=latest_version,
            download_url=installer_url,
            sha256=data.get("sha256", ""),
            signature=data.get("signature", ""),
            release_notes=data.get("release_notes", ""),
        )

        from packages.qt_compat.QtWidgets import QMessageBox
        from packages.qt_compat.QtCore import QTimer
        from app.dialogs import ask_yes_no

        def _show_dialog():
            reply = ask_yes_no(
                parent_window,
                "Co ban cap nhat moi",
                f"Phien ban moi: {latest_version}\n"
                f"Phien ban hien tai: {APP_VERSION}\n\n"
                "Ban co muon cap nhat ngay khong?",
            )
            if reply == QMessageBox.StandardButton.Yes:
                _download_and_run(info, parent_window)

        QTimer.singleShot(0, _show_dialog)

    threading.Thread(target=_worker, daemon=True).start()


def _download_and_run(info: UpdateInfo, parent_window):
    from packages.qt_compat.QtCore import Qt
    from packages.qt_compat.QtWidgets import QMessageBox, QProgressDialog

    progress = QProgressDialog("Dang tai ban cap nhat...", "Huy", 0, 100, parent_window)
    progress.setWindowTitle("Cap nhat")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.show()

    try:
        def _progress(percent: int) -> None:
            if progress.wasCanceled():
                raise RuntimeError("Cancelled")
            progress.setValue(percent)

        result = download_update(info, progress_cb=_progress)
        progress.close()
        if not result.success:
            raise RuntimeError(result.error or "Khong tai duoc ban cap nhat.")
        if sys.platform == "darwin":
            subprocess.Popen(["open", result.path])
        else:
            subprocess.Popen([result.path], shell=False)
        parent_window.close()
    except Exception as exc:
        progress.close()
        if "Cancelled" not in str(exc):
            QMessageBox.warning(parent_window, "Loi tai xuong", f"Khong tai duoc ban cap nhat:\n{exc}")
