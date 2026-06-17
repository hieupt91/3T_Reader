import json
import os
import re
import sys
import tempfile
import urllib.request
import subprocess
from pathlib import Path
from dataclasses import dataclass

# Đường dẫn URL chứa index.json trên VPS
VPS_VOICE_INDEX_URL = "http://127.0.0.1:8080/index.json"

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
    """Tải danh sách các giọng có trên VPS và kiểm tra xem đã tải về máy chưa."""
    voices = []
    try:
        req = urllib.request.Request(VPS_VOICE_INDEX_URL, headers={"User-Agent": "3T_Reader"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
        local_dir = get_piper_voices_dir()
        
        for item in data:
            onnx_path = local_dir / f"{item['id']}.onnx"
            json_path = local_dir / f"{item['id']}.onnx.json"
            
            is_dl = onnx_path.exists() and json_path.exists()
            
            voices.append(PiperVoiceInfo(
                id=item["id"],
                name=item["name"],
                language=item["language"],
                size=item["size"],
                onnx_url=item["onnx_url"],
                json_url=item["json_url"],
                local_onnx_path=str(onnx_path),
                local_json_path=str(json_path),
                is_downloaded=is_dl
            ))
    except Exception as e:
        print(f"Lỗi khi lấy danh sách giọng Piper: {e}")
        local_dir = get_piper_voices_dir()
        for onnx_file in local_dir.glob("*.onnx"):
            json_file = local_dir / f"{onnx_file.stem}.onnx.json"
            if json_file.exists():
                voices.append(PiperVoiceInfo(
                    id=onnx_file.stem,
                    name=onnx_file.stem,
                    language="unknown",
                    size="unknown",
                    onnx_url="",
                    json_url="",
                    local_onnx_path=str(onnx_file),
                    local_json_path=str(json_file),
                    is_downloaded=True
                ))
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
    if os.name == "nt":
        piper_bin_path = os.path.join(os.getcwd(), "piper_bin", "piper.exe")
    else:
        piper_bin_path = os.path.join(os.getcwd(), "venv_piper", "bin", "piper")
        
    if not os.path.exists(piper_bin_path):
        piper_bin_path = "piper" # fallback

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
        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
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
            def _report(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    self.progress.emit(min(percent, 100))
            urllib.request.urlretrieve(self.voice.onnx_url, self.voice.local_onnx_path, reporthook=_report)
            urllib.request.urlretrieve(self.voice.json_url, self.voice.local_json_path)
            self.voice.is_downloaded = True
            self.download_completed.emit(True)
        except Exception as e:
            print(f"Error downloading {self.voice.id}: {e}")
            self.download_completed.emit(False)

class PiperVoiceManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quản lý Giọng đọc (Piper TTS)")
        self.resize(500, 400)
        layout = QVBoxLayout(self)
        
        self.info_lbl = QLabel("Đang tải danh sách giọng từ máy chủ...")
        layout.addWidget(self.info_lbl)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("Tải về / Cập nhật")
        self.btn_download.clicked.connect(self._on_download)
        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)
        
        self.voices = []
        self._load_voices()
        
    def _load_voices(self):
        self.voices = fetch_available_piper_voices()
        self.list_widget.clear()
        if not self.voices:
            self.info_lbl.setText("Không thể lấy danh sách giọng từ máy chủ.")
            return
        self.info_lbl.setText("Danh sách giọng (Vui lòng chọn để tải):")
        for v in self.voices:
            status = "[Đã tải]" if v.is_downloaded else f"[{v.size}]"
            item = QListWidgetItem(f"{status} {v.name} ({v.language})")
            item.setData(Qt.UserRole, v)
            self.list_widget.addItem(item)
            
    def _on_download(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một giọng để tải.")
            return
        voice = item.data(Qt.UserRole)
        
        self.btn_download.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.dl_thread = DownloadThread(voice, self)
        self.dl_thread.progress.connect(self.progress_bar.setValue)
        self.dl_thread.download_completed.connect(self._on_download_finished)
        self.dl_thread.start()
        
    def _on_download_finished(self, success):
        self.btn_download.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, "Thành công", "Đã tải xong gói giọng đọc!")
            self._load_voices()
        else:
            QMessageBox.critical(self, "Lỗi", "Tải thất bại, vui lòng kiểm tra mạng hoặc URL máy chủ.")
