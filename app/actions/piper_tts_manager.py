import json
import os
import re
import sys
import urllib.request
import subprocess
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import urljoin

from app.config import VPS_LICENSE_BASE_URL

_PIPER_INDEX_ENV = "THREET_PIPER_INDEX_URL"

@dataclass
class PiperVoiceInfo:
    id: str
    name: str
    language: str
    size: str
    onnx_url: str
    json_url: str
    local_onnx_path: str = ""
    local_json_path: str = ""
    is_downloaded: bool = False


def _current_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", os.getcwd()))
    return Path(os.getcwd())


def get_bundled_piper_models_dir() -> Path:
    if os.name == "nt":
        return _current_base_dir() / "bin_win" / "piper_bin" / "models"
    elif sys.platform == "darwin":
        return _current_base_dir() / "bin_mac" / "piper_bin" / "models"
    return _current_base_dir() / "venv_piper" / "models"


def has_local_piper_models() -> bool:
    for base in (get_bundled_piper_models_dir(), get_piper_voices_dir()):
        if any(base.glob("*.onnx")):
            return True
    return False


def get_local_piper_engine_path() -> Path:
    base_dir = _current_base_dir()
    if os.name == "nt":
        candidates = [
            base_dir / "bin_win" / "piper_bin" / "piper.exe",
            base_dir / "bin_win" / "piper_bin" / "piper" / "piper.exe",
            base_dir / "piper_bin" / "piper.exe",
            base_dir / "piper_bin" / "piper" / "piper.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            base_dir / "bin_mac" / "piper_bin" / "piper",
            base_dir / "venv_piper" / "bin" / "piper"
        ]
    else:
        candidates = [base_dir / "venv_piper" / "bin" / "piper"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def has_local_piper_engine() -> bool:
    return get_local_piper_engine_path().exists()


def detect_language_for_tts(text: str) -> str:
    sample = (text or "").strip()[:2000]
    if not sample:
        return "en"
    
    vi_letters = re.findall(r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", sample)
    if len(vi_letters) > 0:
        return "vi"
        
    if re.search(r"[\u4e00-\u9fff]", sample):
        return "zh"
    if re.search(r"[\uac00-\ud7af]", sample):
        return "ko"
    if re.search(r"[\u0e00-\u0e7f]", sample):
        return "th"
        
    return "en"


def _voice_language_from_name(voice_id: str) -> str:
    lowered = voice_id.lower()
    if lowered.startswith("vi_") or "vi_vn" in lowered or "vivos" in lowered:
        return "vi"
    if lowered.startswith("en_") or "en_us" in lowered or "ryan" in lowered:
        return "en"
    return "unknown"


def _voice_display_name(voice_id: str) -> str:
    language = _voice_language_from_name(voice_id)
    if language == "vi":
        return f"{voice_id} [Tieng Viet]"
    if language == "en":
        return f"{voice_id} [English]"
    return voice_id


def _scan_local_piper_voices() -> list[PiperVoiceInfo]:
    voices: list[PiperVoiceInfo] = []
    seen: set[str] = set()
    for base in (get_bundled_piper_models_dir(), get_piper_voices_dir()):
        if not base.exists():
            continue
        for onnx_path in sorted(base.glob("*.onnx")):
            json_path = Path(str(onnx_path) + ".json")
            if not json_path.exists():
                alt_json = onnx_path.with_suffix(".onnx.json")
                json_path = alt_json if alt_json.exists() else json_path
            if not json_path.exists():
                continue
            voice_id = onnx_path.stem
            if voice_id in seen:
                continue
            seen.add(voice_id)
            voices.append(
                PiperVoiceInfo(
                    id=voice_id,
                    name=_voice_display_name(voice_id),
                    language=_voice_language_from_name(voice_id),
                    size=f"{round(onnx_path.stat().st_size / (1024 * 1024), 1)} MB",
                    onnx_url="",
                    json_url="",
                    local_onnx_path=str(onnx_path),
                    local_json_path=str(json_path),
                    is_downloaded=True,
                )
            )
    return voices


def _piper_index_candidates() -> list[str]:
    override = os.environ.get(_PIPER_INDEX_ENV, "").strip()
    if override:
        return [override]
    base = VPS_LICENSE_BASE_URL.rstrip("/")
    return [
        f"{base}/downloads/piper/index.json",
        f"{base}/piper/index.json",
        f"{base}/downloads/voices/index.json",
        f"{base}/voices/index.json",
        f"{base}/index.json",
    ]


def _open_no_proxy(request: urllib.request.Request, timeout: int = 12):
    from packages.net_utils import make_ssl_context
    ssl_context = make_ssl_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_context),
        urllib.request.ProxyHandler({})
    )
    return opener.open(request, timeout=timeout)


def _download_no_proxy(url: str, dest_path: str, progress_cb=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "3T_Reader"})
    with _open_no_proxy(req, timeout=120) as resp, open(dest_path, "wb") as out:
        total_size = int(resp.headers.get("Content-Length", "0") or "0")
        downloaded = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total_size > 0:
                progress_cb(downloaded, total_size)

def get_piper_voices_dir() -> Path:
    """Thư mục chứa các mô hình giọng nói Piper trên máy khách."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "3T_Reader" / "voices"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", "")) / "3T_Reader" / "voices"
    else:
        base = Path.home() / ".3T_Reader" / "voices"
    base.mkdir(parents=True, exist_ok=True)
    return base

def fetch_available_piper_voices() -> list[PiperVoiceInfo]:
    """Tải danh sách các giọng có trên VPS và cập nhật thông tin nếu đã tải."""
    voices = _scan_local_piper_voices()
    voices_by_id = {v.id: v for v in voices}
    
    try:
        data = None
        resolved_index_url = ""
        last_error = None
        for candidate in _piper_index_candidates():
            try:
                req = urllib.request.Request(candidate, headers={"User-Agent": "3T_Reader"})
                with _open_no_proxy(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    resolved_index_url = str(resp.geturl())
                break
            except Exception as exc:
                last_error = exc
        if data is None:
            raise RuntimeError(f"Không tìm thấy voice index public. Lỗi cuối: {last_error}")
            
        local_dir = get_piper_voices_dir()
        
        for item in data:
            v_id = item["id"]
            onnx_path = local_dir / f"{v_id}.onnx"
            json_path = local_dir / f"{v_id}.onnx.json"
            is_dl = onnx_path.exists() and json_path.exists()
            
            raw_onnx = item["onnx_url"]
            raw_json = item["json_url"]
            
            # Hotfix cho trường hợp VPS trả về nhầm URL localhost
            if raw_onnx.startswith("http://127.0.0.1:8080/"):
                raw_onnx = raw_onnx.replace("http://127.0.0.1:8080/", "")
            if raw_json.startswith("http://127.0.0.1:8080/"):
                raw_json = raw_json.replace("http://127.0.0.1:8080/", "")
                
            onnx_url = urljoin(resolved_index_url, raw_onnx)
            json_url = urljoin(resolved_index_url, raw_json)
            
            if v_id in voices_by_id:
                # Update existing local voice with full info from VPS
                v = voices_by_id[v_id]
                v.name = item["name"]
                v.language = item["language"]
                v.size = item["size"]
                v.onnx_url = onnx_url
                v.json_url = json_url
                v.is_downloaded = is_dl
            else:
                # Add new voice from VPS
                v = PiperVoiceInfo(
                    id=v_id,
                    name=item["name"],
                    language=item["language"],
                    size=item["size"],
                    onnx_url=onnx_url,
                    json_url=json_url,
                    local_onnx_path=str(onnx_path),
                    local_json_path=str(json_path),
                    is_downloaded=is_dl
                )
                voices.append(v)
                voices_by_id[v_id] = v
                
    except Exception as e:
        print(f"Lỗi khi lấy danh sách giọng Piper: {e}")
        
    return voices

def preprocess_text_for_piper(text: str) -> str:
    """Ép nhịp thở, chống hụt hơi cho Piper."""
    def _split_long_sentences(match):
        sentence = match.group(0)
        if len(sentence) > 150 and ',' not in sentence:
            sentence = re.sub(r'\s+(và|hoặc|thì|là|mà|rằng)\s+', r', \1 ', sentence)
        return sentence
    text = re.sub(r'[^.?!]+[.?!]', _split_long_sentences, text)
    return text.strip()

def synthesize_audio_piper(text: str, model_path: str, output_wav_path: str, speed_val: int = 100) -> bool:
    """Tạo file WAV sử dụng thư viện piper-tts."""
    text = preprocess_text_for_piper(text)
    piper_bin_path = str(get_local_piper_engine_path())
    if not os.path.exists(piper_bin_path):
        piper_bin_path = "piper"  # fallback

    # Calculate length_scale from speed_val (50 to 200, default 100)
    # length_scale > 1 is slower, < 1 is faster. 
    length_scale = max(0.1, 100.0 / speed_val)

    try:
        cmd = [
            piper_bin_path, 
            "--model", model_path, 
            "--output_file", output_wav_path,
            "--sentence_silence", "0.5",
            "--length_scale", str(length_scale)
        ]
        popen_kwargs = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
        }
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            popen_kwargs["startupinfo"] = startupinfo
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(cmd, **popen_kwargs)
        out, err = process.communicate(input=text.encode('utf-8'))
        
        if process.returncode != 0:
            print(f"Piper error: {err.decode('utf-8')}")
            return False
            
        return os.path.exists(output_wav_path)
    except Exception as e:
        print(f"Lỗi tạo audio Piper: {e}")
        return False

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QProgressBar, QMessageBox
)
from packages.qt_compat.QtCore import Qt, QThread, pyqtSignal

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    download_completed = pyqtSignal(bool)
    
    def __init__(self, voice, parent=None):
        super().__init__(parent)
        self.voice = voice

    def run(self):
        try:
            def _report(done_bytes, total_size):
                if total_size > 0:
                    percent = int(done_bytes * 100 / total_size)
                    self.progress.emit(min(percent, 100))
            _download_no_proxy(self.voice.onnx_url, self.voice.local_onnx_path, progress_cb=_report)
            _download_no_proxy(self.voice.json_url, self.voice.local_json_path)
            self.voice.is_downloaded = True
            self.download_completed.emit(True)
        except Exception as e:
            print(f"Error downloading {self.voice.id}: {e}")
            self.download_completed.emit(False)

class PiperVoiceManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_voices()

    def _t(self, key: str, fallback: str) -> str:
        from app.language_manager import get_selected_language, get_translation
        return get_translation(get_selected_language(), key, fallback)

    def _setup_ui(self):
        self.setWindowTitle(self._t("piper.title", "Quản lý Giọng đọc (Piper TTS)"))
        self.resize(500, 400)
        layout = QVBoxLayout(self)
        
        self.info_lbl = QLabel(self._t("piper.loading", "Đang tải danh sách giọng từ máy chủ..."))
        layout.addWidget(self.info_lbl)
        
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_download)
        layout.addWidget(self.list_widget)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton(self._t("piper.btn_download", "Tải về / Cập nhật"))
        self.btn_download.clicked.connect(self._on_download)
        self.btn_close = QPushButton(self._t("piper.btn_close", "Đóng"))
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)
        
    def _load_voices(self):
        self.voices = fetch_available_piper_voices()
        self.list_widget.clear()
        
        if not self.voices:
            self.btn_download.setEnabled(False)
            self.info_lbl.setText(self._t("piper.no_voices", "Không tìm thấy giọng đọc nào."))
            return
            
        self.btn_download.setEnabled(True)
        self.info_lbl.setText(self._t("piper.list_desc", "Danh sách giọng (Vui lòng chọn để tải):"))
        for v in self.voices:
            status = self._t("piper.downloaded", "[Đã tải]") if v.is_downloaded else f"[{v.size}]"
            item = QListWidgetItem(f"{status} {v.name} ({v.language})")
            item.setData(Qt.UserRole, v)
            self.list_widget.addItem(item)
            
    def _on_download(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, self._t("msg.error", "Lỗi"), self._t("piper.select_prompt", "Vui lòng chọn một giọng để tải."))
            return
        voice = item.data(Qt.UserRole)
        
        if not voice.onnx_url:
            QMessageBox.warning(self, self._t("msg.error", "Lỗi"), self._t("piper.no_url_error", "Giọng đọc này không có trên máy chủ để tải/cập nhật."))
            return
        
        self.btn_download.setEnabled(False)
        # Đóng dialog trong lúc dl_thread (QThread thật) đang chạy nền có thể
        # để lại signal progress/download_completed trỏ vào widget đã bị huỷ
        # (self.progress_bar, self._on_download_finished) khi dialog Python bị
        # dọn sau khi accept() - cùng lớp crash libshiboken "C++ object đã bị
        # xoá" đã gặp ở nơi khác trong app. Chưa tái hiện được crash cụ thể để
        # khẳng định chắc chắn, nhưng disable nút Đóng trong lúc tải là an
        # toàn và đúng UX bất kể lý thuyết trên đúng hay không (không cho phép
        # bỏ dở dialog trong khi thread nền vẫn đang ghi file).
        self.btn_close.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.dl_thread = DownloadThread(voice) # Remove 'self' as parent to prevent PySide6 destruction crash
        self.dl_thread.progress.connect(self.progress_bar.setValue)
        self.dl_thread.download_completed.connect(self._on_download_finished)
        self.dl_thread.finished.connect(self.dl_thread.deleteLater) # Auto cleanup
        self.dl_thread.start()
        
    def closeEvent(self, event):
        """Chặn đóng qua nút X / phím Escape trong lúc dl_thread đang chạy -
        nút "Đóng" đã disable ở trên nhưng chỉ chặn được đường click nút,
        không chặn được 2 đường này. Cùng pattern đã dùng đúng ở
        app/ai_translate_dialog.py::closeEvent cho lớp vấn đề tương tự."""
        try:
            if getattr(self, "dl_thread", None) and self.dl_thread.isRunning():
                event.ignore()
                return
        except RuntimeError:
            pass
        super().closeEvent(event)

    def _on_download_finished(self, success):
        self.btn_download.setEnabled(True)
        self.btn_close.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, self._t("msg.success", "Thành công"), self._t("piper.dl_success", "Đã tải xong gói giọng đọc!"))
            self._load_voices()
        else:
            QMessageBox.critical(self, self._t("msg.error", "Lỗi"), self._t("piper.dl_fail", "Tải thất bại, vui lòng kiểm tra mạng hoặc URL máy chủ."))
