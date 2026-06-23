import json
import locale
import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import subprocess

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

import requests

from packages.qt_compat.QtCore import QObject, Qt, QUrl, pyqtSignal
from packages.qt_compat.QtGui import QDesktopServices
from packages.qt_compat.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QSpinBox,
)


_OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
_OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
_MAX_TTS_CHARS = 3500
_OFFLINE_MODE = "offline"
_OPENAI_MODE = "openai"
_PIPER_MODE = "piper"
_LANGUAGE_CHOICES = [
    ("auto", "Tu nhan dien"),
    ("vi", "Tieng Viet"),
    ("en", "English"),
    ("fr", "Francais"),
    ("zh", "中文"),
    ("ko", "한국어"),
    ("th", "ไทย"),
]
_OPENAI_VOICES = [
    ("alloy", "Alloy"),
    ("ash", "Ash"),
    ("ballad", "Ballad"),
    ("coral", "Coral"),
    ("echo", "Echo"),
    ("fable", "Fable"),
    ("nova", "Nova"),
    ("onyx", "Onyx"),
    ("sage", "Sage"),
    ("shimmer", "Shimmer"),
    ("verse", "Verse"),
    ("marin", "Marin"),
    ("cedar", "Cedar"),
]
_VOICE_SETTINGS_URL = "ms-settings:speech"
_LANGUAGE_SETTINGS_URL = "ms-settings:regionlanguage"
_SPEAK_ASYNC = 1
_SPEAK_PURGE = 2


@dataclass
class _OfflineVoice:
    id: str
    name: str
    languages: list[str]
    backend: str = "pyttsx3"


class _TTSBridge(QObject):
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    audioReady = pyqtSignal(str)


def _clean_text(text: str, max_chars: int = _MAX_TTS_CHARS) -> str:
    text = str(text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "... (Văn bản quá dài, đã bị cắt bớt)"
    return text


def _contains_vietnamese(text: str) -> bool:
    return bool(
        re.search(
            r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
            text,
        )
    )


def _guess_language_code(text: str) -> str:
    sample = (text or "")[:600]
    if _contains_vietnamese(sample):
        return "vi"
    if re.search(r"[\u4e00-\u9fff]", sample):
        return "zh"
    if re.search(r"[\uac00-\ud7af]", sample):
        return "ko"
    if re.search(r"[\u0e00-\u0e7f]", sample):
        return "th"
    return "en"


def _language_label(code: str) -> str:
    for key, label in _LANGUAGE_CHOICES:
        if key == code:
            return label
    return "English"


def _normalize_voice_language(raw) -> str:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            raw = str(raw)
    raw = str(raw or "").strip().lower().replace("_", "-")
    if raw.startswith("\x05"):
        raw = raw[1:]
    return raw


def _voice_languages(voice) -> list[str]:
    langs = []
    for raw in getattr(voice, "languages", []) or []:
        norm = _normalize_voice_language(raw)
        if norm:
            langs.append(norm)
    if not langs:
        voice_id = str(getattr(voice, "id", "")).lower()
        name = str(getattr(voice, "name", "")).lower()
        for code in ("vi", "en", "fr", "zh", "ko", "th"):
            if f"-{code}" in voice_id or f"_{code}" in voice_id or f" {code}" in name:
                langs.append(code)
                break
    return langs


def _voice_matches_language(voice, language_code: str) -> bool:
    if language_code == "auto":
        return True
    langs = _voice_languages(voice)
    if not langs:
        return language_code == "en"
    return any(lang == language_code or lang.startswith(f"{language_code}-") for lang in langs)


def _voice_label(voice) -> str:
    langs = _voice_languages(voice)
    suffix = f" [{', '.join(langs)}]" if langs else ""
    return f"{voice.name}{suffix}"


def _lcid_hex_to_bcp47(raw: str) -> str:
    raw = str(raw or "").strip().split(";")[0]
    if not raw:
        return ""
    try:
        return locale.windows_locale.get(int(raw, 16), "").replace("_", "-").lower()
    except Exception:
        return ""


def _windows_sapi_voices() -> list[_OfflineVoice]:
    if os.name != "nt":
        return []
    try:
        import win32com.client
    except Exception:
        return []

    roots = [
        r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
        r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",
    ]
    voices: list[_OfflineVoice] = []
    seen: set[str] = set()
    for root in roots:
        try:
            category = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
            category.SetId(root, False)
            tokens = category.EnumerateTokens()
        except Exception:
            continue
        for index in range(getattr(tokens, "Count", 0)):
            try:
                token = tokens.Item(index)
                token_id = str(token.Id)
            except Exception:
                continue
            if token_id in seen:
                continue
            seen.add(token_id)
            try:
                name = str(token.GetDescription())
            except Exception:
                name = token_id.rsplit("\\", 1)[-1]
            languages = []
            try:
                language_attr = token.GetAttribute("Language")
                normalized = _lcid_hex_to_bcp47(language_attr)
                if normalized:
                    languages.append(normalized)
            except Exception:
                pass
            voices.append(_OfflineVoice(id=token_id, name=name, languages=languages, backend="sapi"))
    return voices


def _safe_pyttsx3_voices() -> list[_OfflineVoice]:
    if pyttsx3 is None:
        return []
    try:
        engine = pyttsx3.init()
        try:
            return [
                _OfflineVoice(
                    id=str(getattr(voice, "id", "")),
                    name=str(getattr(voice, "name", "")),
                    languages=_voice_languages(voice),
                    backend="pyttsx3",
                )
                for voice in engine.getProperty("voices")
            ]
        finally:
            try:
                engine.stop()
            except Exception:
                pass
    except Exception:
        return []


def _macos_say_voices() -> list[_OfflineVoice]:
    if sys.platform != "darwin":
        return []
    try:
        res = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        voices = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("#")
            voice_info = parts[0].strip()
            tokens = voice_info.split()
            if len(tokens) >= 2:
                locale_str = tokens[-1]
                name_full = " ".join(tokens[:-1])
                name_clean = name_full.split("(")[0].strip()
                lang = locale_str.split("_")[0].lower()
                voices.append(_OfflineVoice(id=name_clean, name=name_full, languages=[lang], backend="say"))
        return voices
    except Exception:
        return []


def _load_offline_voices() -> list[_OfflineVoice]:
    if sys.platform == "darwin":
        mac_voices = _macos_say_voices()
        if mac_voices:
            return mac_voices
    windows_voices = _windows_sapi_voices()
    if windows_voices:
        return windows_voices
    return _safe_pyttsx3_voices()


def _rate_instruction(rate: int) -> str:
    if rate <= 105:
        return "Speak slowly and clearly."
    if rate <= 145:
        return "Speak at a calm, clear pace."
    if rate <= 185:
        return "Speak at a natural pace."
    if rate <= 230:
        return "Speak slightly faster, while staying clear."
    return "Speak quickly but remain understandable."


_afplay_proc = None


def _start_async_wav(path: str) -> None:
    if sys.platform == "darwin":
        global _afplay_proc
        _stop_wav_playback()
        _afplay_proc = subprocess.Popen(["afplay", path])
    elif os.name == "nt":
        import winsound

        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
        raise RuntimeError("AI TTS playback hien chua ho tro tren he dieu hanh nay.")


def _stop_wav_playback() -> None:
    if sys.platform == "darwin":
        global _afplay_proc
        if _afplay_proc is not None:
            try:
                _afplay_proc.terminate()
            except Exception:
                pass
            _afplay_proc = None
    elif os.name == "nt":
        import winsound

        winsound.PlaySound(None, winsound.SND_PURGE)


class TTSDialog(QDialog):
    def __init__(self, parent=None, page_text="", selected_text="", pages_text=None, current_page=1):
        super().__init__(parent)
        self.setWindowTitle(self._t("tts.title", "Đọc sách bằng AI (TTS)"))
        self.pages_text = pages_text or []
        self.current_page = current_page
        self.page_text = _clean_text(page_text)
        self.selected_text = _clean_text(selected_text)
        self.full_text = _clean_text("\n\n".join(self.pages_text))
        self.text_to_speak = self.selected_text if self.selected_text else self.page_text
        self.setMinimumSize(520, 280)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)

        self.engine = None
        self.voices = _load_offline_voices()
        self._engine_run = None
        self._speaker_run = None
        self._thread = None
        self._stop_requested = threading.Event()
        self._offline_voice_missing = False
        self._bridge = _TTSBridge(self)
        self._bridge.status.connect(self._set_status)
        self._bridge.finished.connect(self._on_finished)
        self._bridge.audioReady.connect(self._on_audio_ready)

        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        except ImportError:
            self._media_player = None

        self._build_ui()
        self._refresh_voice_options()

    def _t(self, key: str, fallback: str) -> str:
        from app.language_manager import get_selected_language, get_translation
        return get_translation(get_selected_language(), key, fallback)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        scope_layout = QHBoxLayout()
        scope_layout.addWidget(QLabel(self._t("tts.scope", "Phạm vi:")))
        self.scope_cb = QComboBox()
        self.scope_cb.addItem(self._t("tts.scope_selection", "Đoạn văn bản bôi đen"), "selection")
        self.scope_cb.addItem(self._t("tts.scope_page", "Toàn bộ trang hiện tại"), "page")
        self.scope_cb.addItem(self._t("tts.scope_doc", "Toàn bộ tài liệu"), "document")
        self.scope_cb.addItem(self._t("tts.scope_custom", "Trang tuỳ chọn"), "custom")
        if not self.selected_text:
            self.scope_cb.setCurrentIndex(1)
            self.scope_cb.setEnabled(True)
        self.scope_cb.currentIndexChanged.connect(self._on_scope_changed)
        scope_layout.addWidget(self.scope_cb)

        self.page_from_spin = QSpinBox()
        self.page_from_spin.setRange(1, max(1, len(self.pages_text)))
        self.page_from_spin.setValue(self.current_page)
        self.page_from_spin.setVisible(False)
        self.page_to_spin = QSpinBox()
        self.page_to_spin.setRange(1, max(1, len(self.pages_text)))
        self.page_to_spin.setValue(min(len(self.pages_text), self.current_page + 1))
        self.page_to_spin.setVisible(False)
        self.page_dash_lbl = QLabel("-")
        self.page_dash_lbl.setVisible(False)
        
        self.page_from_spin.valueChanged.connect(self._update_custom_pages_text)
        self.page_to_spin.valueChanged.connect(self._update_custom_pages_text)

        scope_layout.addWidget(self.page_from_spin)
        scope_layout.addWidget(self.page_dash_lbl)
        scope_layout.addWidget(self.page_to_spin)

        layout.addLayout(scope_layout)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel(self._t("tts.mode", "Chế độ:")))
        self.mode_cb = QComboBox()
        self.mode_cb.addItem("Piper TTS (AI Offline Mượt)", _PIPER_MODE)
        self.mode_cb.addItem("Offline (Giọng máy)", _OFFLINE_MODE)
        self.mode_cb.addItem("AI Key (OpenAI TTS)", _OPENAI_MODE)
        self.mode_cb.currentIndexChanged.connect(self._refresh_voice_options)
        mode_layout.addWidget(self.mode_cb)
        layout.addLayout(mode_layout)

        language_layout = QHBoxLayout()
        language_layout.addWidget(QLabel(self._t("tts.language", "Ngôn ngữ:")))
        self.language_cb = QComboBox()
        for code, label in _LANGUAGE_CHOICES:
            self.language_cb.addItem(label, code)
        self.language_cb.currentIndexChanged.connect(self._refresh_voice_options)
        language_layout.addWidget(self.language_cb)
        layout.addLayout(language_layout)

        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel(self._t("tts.voice", "Giọng đọc:")))
        self.voice_cb = QComboBox()
        voice_layout.addWidget(self.voice_cb)
        layout.addLayout(voice_layout)

        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel(self._t("tts.rate", "Tốc độ:")))
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(50, 250)
        self.rate_slider.setValue(150)
        self.rate_slider.valueChanged.connect(self._on_rate_changed)
        rate_layout.addWidget(self.rate_slider)
        self.rate_value_lbl = QLabel("1.0x")
        self.rate_value_lbl.setMinimumWidth(40)
        rate_layout.addWidget(self.rate_value_lbl)
        layout.addLayout(rate_layout)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color:#6b7280;font-size:12px;")
        layout.addWidget(self.status_lbl)

        helper_layout = QHBoxLayout()
        self.btn_install_voice = QPushButton(self._t("tts.install_voice", "Tải/Cài giọng"))
        self.btn_install_voice.clicked.connect(self._open_voice_install)
        self.btn_refresh_voices = QPushButton(self._t("tts.refresh_voices", "Làm mới giọng"))
        self.btn_refresh_voices.clicked.connect(self._reload_voices)

        self.btn_piper_mgr = QPushButton(self._t("tts.voice_store", "Cửa hàng Giọng AI..."))
        self.btn_piper_mgr.clicked.connect(self._open_piper_manager)
        self.btn_piper_mgr.setVisible(False)
        
        helper_layout.addWidget(self.btn_piper_mgr)
        helper_layout.addWidget(self.btn_install_voice)
        helper_layout.addWidget(self.btn_refresh_voices)
        helper_layout.addStretch()
        layout.addLayout(helper_layout)

        btn_layout = QHBoxLayout()
        self.btn_play = QPushButton(self._t("tts.play", "Phát"))
        self.btn_stop = QPushButton(self._t("tts.stop", "Dừng"))
        self.btn_stop.setEnabled(False)
        self.btn_play.clicked.connect(self._play)
        self.btn_stop.clicked.connect(self._stop)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_play)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

    def _on_rate_changed(self, value: int):
        ratio = max(0.2, min(3.0, value / 150.0))
        if hasattr(self, 'rate_value_lbl'):
            self.rate_value_lbl.setText(f"{ratio:.1f}x")
        if self._media_player is not None:
            self._media_player.setPlaybackRate(ratio)

    def _on_audio_ready(self, audio_path: str):
        if self._media_player is not None:
            self._media_player.setSource(QUrl.fromLocalFile(audio_path))
            self._on_rate_changed(self.rate_slider.value())
            self._media_player.play()
        else:
            _start_async_wav(audio_path)

    def _on_media_status_changed(self, status):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                if getattr(self, "_is_playing", False):
                    self._bridge.finished.emit(True, "Doc xong.")
        except ImportError:
            pass

    def _on_scope_changed(self):
        data = self.scope_cb.currentData()
        is_custom = (data == "custom")
        self.page_from_spin.setVisible(is_custom)
        self.page_dash_lbl.setVisible(is_custom)
        self.page_to_spin.setVisible(is_custom)

        if data == "selection":
            self.text_to_speak = self.selected_text
            if not self.text_to_speak:
                self._set_status("Khong co van ban nao dang duoc boi den.")
        elif data == "document":
            self.text_to_speak = self.full_text
            if not self.text_to_speak:
                self._set_status("Khong the lay van ban toan bo tai lieu.")
        elif data == "custom":
            self._update_custom_pages_text()
        else:
            self.text_to_speak = self.page_text

    def _update_custom_pages_text(self):
        if not self.pages_text:
            return
        start = self.page_from_spin.value() - 1
        end = self.page_to_spin.value()
        if start > end - 1:
            start = end - 1
        texts = self.pages_text[max(0, start):max(1, end)]
        self.text_to_speak = _clean_text("\n\n".join(texts))

    def _selected_language(self) -> str:
        code = self.language_cb.currentData()
        return _guess_language_code(self.text_to_speak) if code == "auto" else code

    def _set_status(self, text: str):
        self.status_lbl.setText(text)

    def _reload_voices(self):
        self.voices = _load_offline_voices()
        self._refresh_voice_options()

    def _sync_play_button_state(self):
        if self.btn_stop.isEnabled():
            return
        mode = self.mode_cb.currentData()
        if mode == _OPENAI_MODE:
            self.btn_play.setEnabled(bool(os.environ.get("OPENAI_API_KEY")))
        elif mode == _PIPER_MODE:
            self.btn_play.setEnabled(self.voice_cb.count() > 0)
        else:
            self.btn_play.setEnabled((not self._offline_voice_missing) and self.voice_cb.count() > 0)

    def _refresh_voice_options(self):
        mode = self.mode_cb.currentData()
        self.voice_cb.blockSignals(True)
        self.voice_cb.clear()
        self._offline_voice_missing = False
        self.btn_install_voice.setVisible(False)
        self.btn_install_voice.setEnabled(False)
        self.btn_piper_mgr.setVisible(False)

        if mode == _OPENAI_MODE:
            for voice_id, label in _OPENAI_VOICES:
                self.voice_cb.addItem(label, voice_id)
            self.voice_cb.setCurrentIndex(max(0, self.voice_cb.findData("marin")))
            if os.environ.get("OPENAI_API_KEY"):
                self._set_status("Dung OPENAI_API_KEY da luu de doc giong AI.")
            else:
                self._set_status("Chua co OPENAI_API_KEY. Vao AI > Cai dat AI de nhap key.")
        elif mode == _PIPER_MODE:
            from app.actions.piper_tts_manager import fetch_available_piper_voices, has_local_piper_engine
            piper_voices = [v for v in fetch_available_piper_voices() if v.is_downloaded]
            target_lang = self.language_cb.currentData()
            matching = [v for v in piper_voices if v.language == target_lang or target_lang == "auto"]
            
            if target_lang == "auto" and len(piper_voices) > 0:
                self.voice_cb.addItem("⭐ Tự động chọn giọng theo văn bản", "auto_piper")
                
            for voice in matching:
                self.voice_cb.addItem(voice.name, voice)
            self.btn_piper_mgr.setVisible(True)
            self._offline_voice_missing = len(matching) == 0 and target_lang != "auto"
            if not has_local_piper_engine():
                self._set_status("Chua co Piper engine trong piper_bin. Can bo sung piper.exe truoc khi doc.")
            elif len(piper_voices) > 0:
                self._set_status(f"Piper TTS da san sang cho {_language_label(target_lang)}.")
            else:
                self._set_status(f"Chua co giong Piper local cho {_language_label(target_lang)}. Dat model vao piper_bin/models hoac bam 'Cửa hàng Giọng AI' de tai them.")
        else:
            target_lang = self._selected_language()
            matching = [voice for voice in self.voices if _voice_matches_language(voice, target_lang)]
            for voice in matching:
                self.voice_cb.addItem(_voice_label(voice), voice)
            if matching:
                self._set_status(
                    f"Offline dung giong Windows cho {_language_label(target_lang)}. "
                    "Neu doc sai tieng, hay doi sang giong dung ngon ngu."
                )
            else:
                self._offline_voice_missing = True
                self.btn_install_voice.setVisible(True)
                self.btn_install_voice.setEnabled(True)
                self._set_status(
                    f"Windows chua co giong offline cho {_language_label(target_lang)}. "
                    "Bam 'Tai/Cai giong' de mo cai dat, cai xong quay lai bam 'Lam moi giong'."
                )

        self.voice_cb.blockSignals(False)
        self._sync_play_button_state()

    def _open_piper_manager(self):
        from app.actions.piper_tts_manager import PiperVoiceManagerDialog
        dlg = PiperVoiceManagerDialog(self)
        dlg.exec()
        self._refresh_voice_options()

    def _open_voice_install(self):
        lang = self._selected_language()
        opened = False
        opened = QDesktopServices.openUrl(QUrl(_VOICE_SETTINGS_URL)) or opened
        opened = QDesktopServices.openUrl(QUrl(_LANGUAGE_SETTINGS_URL)) or opened
        if opened:
            self._set_status(
                f"Da mo cai dat Windows cho {_language_label(lang)}. "
                "Hay them Speech/Language pack, sau do quay lai bam 'Lam moi giong'."
            )
        else:
            from app.dialogs import show_info

            show_info(
                self,
                "Cai giong offline",
                "Khong mo duoc trang cai dat tu dong. "
                "Hay vao Windows Settings > Speech hoac Language & region de cai them voice.",
            )

    def _set_playing(self, playing: bool):
        self._is_playing = playing
        self.btn_play.setEnabled(False if playing else self.btn_play.isEnabled())
        self.btn_stop.setEnabled(playing)
        self.mode_cb.setEnabled(not playing)
        self.language_cb.setEnabled(not playing)
        self.voice_cb.setEnabled(not playing)
        # Enable the rate slider even when playing so user can dynamically adjust speed!
        self.rate_slider.setEnabled(True)
        self.btn_refresh_voices.setEnabled(not playing)
        self.btn_install_voice.setEnabled((not playing) and self._offline_voice_missing)
        if not playing:
            self._sync_play_button_state()

    def _play(self):
        if not self.text_to_speak.strip():
            from app.dialogs import show_warning

            show_warning(self, "Loi", "Khong tim thay van ban tren trang hien tai.")
            return

        mode = self.mode_cb.currentData()
        if mode == _OFFLINE_MODE and self._offline_voice_missing:
            from app.dialogs import show_warning

            show_warning(
                self,
                "Thieu giong offline",
                "Windows chua co giong offline cho ngon ngu nay. "
                "Bam 'Tai/Cai giong', cai xong roi quay lai bam 'Lam moi giong'.",
            )
            return
        if mode == _OPENAI_MODE and not os.environ.get("OPENAI_API_KEY"):
            from app.dialogs import show_warning

            show_warning(self, "Thieu AI Key", "Chua co OPENAI_API_KEY. Vao AI > Cai dat AI de nhap key.")
            return

        self._stop_requested.clear()
        self._set_playing(True)
        self._bridge.status.emit("Dang chuan bi doc...")
        
        mode = self.mode_cb.currentData()
        voice = self.voice_cb.currentData()
        rate = self.rate_slider.value()
        
        if mode in (_PIPER_MODE, _OPENAI_MODE):
            cache_key = (self.text_to_speak, mode, str(getattr(voice, "id", getattr(voice, "name", voice))), rate)
            cached_path = getattr(self, "_cached_audio_path", None)
            cached_key = getattr(self, "_cached_audio_key", None)
            if cached_key == cache_key and cached_path and os.path.exists(cached_path):
                self._bridge.status.emit("Dang phat lai tu bo nho tam...")
                self._bridge.audioReady.emit(cached_path)
                return
            self._current_cache_key = cache_key
        
        if mode == _PIPER_MODE:
            self._thread = threading.Thread(target=self._run_piper_tts, daemon=True)
        elif mode == _OPENAI_MODE:
            self._thread = threading.Thread(target=self._run_openai_tts, daemon=True)
        else:
            self._thread = threading.Thread(target=self._run_offline_tts, daemon=True)
            
        self._thread.start()

    def _run_piper_tts(self):
        from app.actions.piper_tts_manager import (
            detect_language_for_tts,
            fetch_available_piper_voices,
            has_local_piper_engine,
            synthesize_audio_piper,
        )
        if not has_local_piper_engine():
            self._bridge.finished.emit(False, "Chua co Piper engine trong piper_bin.")
            return
        voice_or_auto = self.voice_cb.currentData()
        if not voice_or_auto:
            self._bridge.finished.emit(False, "Chua chon giong Piper.")
            return
            
        voice = voice_or_auto
        if voice_or_auto == "auto_piper":
            lang_code = detect_language_for_tts(self.text_to_speak)
            piper_voices = [v for v in fetch_available_piper_voices() if v.is_downloaded]
            lang_voices = [v for v in piper_voices if v.language == lang_code]
            if not lang_voices:
                # Fallback to English if not found, or the first downloaded
                if piper_voices:
                    voice = piper_voices[0]
                else:
                    self._bridge.finished.emit(False, f"Chưa tải giọng Piper cho {lang_code}.")
                    return
            else:
                voice = lang_voices[0]
                
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_path = f.name
            
        self._bridge.status.emit(f"Dang tong hop giong Piper ({voice.name})...")
        ok = synthesize_audio_piper(self.text_to_speak, voice.local_onnx_path, audio_path, 100)
        if not ok:
            self._bridge.finished.emit(False, "Loi tao giong Piper.")
            return

        self._cached_audio_key = getattr(self, "_current_cache_key", None)
        self._cached_audio_path = audio_path

        self._bridge.audioReady.emit(audio_path)
        self._bridge.status.emit(f"Dang phat Piper TTS: {voice.name}")

    def _run_offline_tts(self):
        voice = self.voice_cb.currentData()
        rate = self.rate_slider.value()
        try:
            self._bridge.status.emit("Dang doc offline...")
            if isinstance(voice, _OfflineVoice) and voice.backend == "sapi":
                self._run_windows_sapi_tts(voice, rate)
            elif isinstance(voice, _OfflineVoice) and voice.backend == "say":
                self._run_macos_say_tts(voice, rate)
            else:
                self._run_pyttsx3_tts(voice.id if isinstance(voice, _OfflineVoice) else voice, rate)
            self._bridge.finished.emit(True, "Da dung." if self._stop_requested.is_set() else "Doc offline xong.")
        except Exception as exc:
            self._bridge.finished.emit(False, f"Loi doc offline: {exc}")
        finally:
            self._engine_run = None
            self._speaker_run = None

    def _run_macos_say_tts(self, voice: _OfflineVoice, rate: int):
        wpm = str(rate)
        self._speaker_run = subprocess.Popen(["say", "-v", voice.id, "-r", wpm, self.text_to_speak])
        while self._speaker_run.poll() is None:
            if self._stop_requested.is_set():
                self._speaker_run.terminate()
                break
            time.sleep(0.1)

    def _run_pyttsx3_tts(self, voice_id: str, rate: int):
        self._engine_run = pyttsx3.init()
        self._engine_run.setProperty("rate", rate)
        if voice_id:
            self._engine_run.setProperty("voice", voice_id)
        self._engine_run.say(self.text_to_speak)
        self._engine_run.startLoop(False)
        while self._engine_run.isBusy():
            if self._stop_requested.is_set():
                self._engine_run.stop()
                break
            self._engine_run.iterate()
            time.sleep(0.05)
        try:
            self._engine_run.endLoop()
        except Exception:
            pass

    def _run_windows_sapi_tts(self, voice: _OfflineVoice, rate: int):
        import win32com.client

        self._speaker_run = win32com.client.Dispatch("SAPI.SpVoice")
        self._speaker_run.Rate = max(-10, min(10, int(round((rate - 150) / 10))))
        category = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
        root = voice.id.rsplit("\\Tokens\\", 1)[0]
        category.SetId(root, False)
        tokens = category.EnumerateTokens()
        selected = None
        for index in range(getattr(tokens, "Count", 0)):
            token = tokens.Item(index)
            if str(token.Id).lower() == voice.id.lower():
                selected = token
                break
        if selected is None:
            raise RuntimeError("Khong tim thay giong Windows da chon.")
        self._speaker_run.Voice = selected
        self._speaker_run.Speak(self.text_to_speak, _SPEAK_ASYNC)
        while not self._speaker_run.WaitUntilDone(100):
            if self._stop_requested.is_set():
                self._speaker_run.Speak("", _SPEAK_ASYNC | _SPEAK_PURGE)
                break

    def _synthesize_openai_wav(self) -> str:
        voice_id = self.voice_cb.currentData() or "marin"
        rate = self.rate_slider.value()
        language_code = self._selected_language()
        text = _clean_text(self.text_to_speak, max_chars=4000)
        payload = {
            "model": _OPENAI_TTS_MODEL,
            "voice": voice_id,
            "input": text,
            "instructions": f"Read this text naturally in {_language_label(language_code)}. {_rate_instruction(rate)}",
            "response_format": "wav",
        }
        headers = {
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        }
        response = requests.post(_OPENAI_TTS_URL, headers=headers, json=payload, timeout=120)
        if not response.ok:
            message = response.text
            try:
                payload = response.json()
                message = payload.get("error", {}).get("message", message)
            except json.JSONDecodeError:
                pass
            raise RuntimeError(message)

        temp_dir = Path(tempfile.gettempdir()) / "3t_reader_tts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        audio_path = temp_dir / "tts_openai.wav"
        audio_path.write_bytes(response.content)
        return str(audio_path)

    def _run_openai_tts(self):
        try:
            self._bridge.status.emit("Dang tao giong AI tu key da luu...")
            audio_path = self._synthesize_openai_wav()
            if self._stop_requested.is_set():
                self._bridge.finished.emit(True, "Da dung.")
                return
            
            self._cached_audio_key = getattr(self, "_current_cache_key", None)
            self._cached_audio_path = audio_path
            
            self._bridge.audioReady.emit(audio_path)
            self._bridge.status.emit("Dang phat giong AI...")
        except Exception as exc:
            self._bridge.finished.emit(False, f"Loi AI TTS: {exc}")

    def _stop(self):
        self._stop_requested.set()
        try:
            if getattr(self, "_media_player", None) is not None:
                self._media_player.stop()
        except Exception:
            pass
        try:
            if self._engine_run is not None:
                self._engine_run.stop()
        except Exception:
            pass
        try:
            if self._speaker_run is not None:
                self._speaker_run.Speak("", _SPEAK_ASYNC | _SPEAK_PURGE)
        except Exception:
            pass
        try:
            _stop_wav_playback()
        except Exception:
            pass
        self._set_playing(False)
        self._set_status("Da dung.")

    def _on_finished(self, ok: bool, message: str):
        self._set_playing(False)
        self._set_status(message)
        if not ok:
            from app.dialogs import show_warning

            show_warning(self, "Doc sach", message)

    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)


def open_tts_dialog(window):
    existing = getattr(window, "_tts_dialog", None)
    if existing is not None and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return

    viewer = getattr(window, "viewer", None)
    if not viewer:
        from app.dialogs import show_warning

        show_warning(window, "Loi", "Vui long mo mot tep PDF truoc.")
        return

    try:
        from app.actions.ai_actions import load_ai_config
        load_ai_config()
    except Exception:
        pass

    def _on_selection_received(sel_text):
        page_text = ""
        full_texts = []
        page_number = 1
        try:
            import pypdfium2 as pdfium
            pdf_path = getattr(window, "current_path", "") or getattr(viewer, "_path", "")
            if hasattr(viewer, "get_current_page"):
                page_number = max(1, int(viewer.get_current_page() or 1))
            elif hasattr(viewer, "_current_page"):
                page_number = max(1, int(getattr(viewer, "_current_page", 1) or 1))
            if pdf_path and os.path.isfile(pdf_path):
                doc = pdfium.PdfDocument(pdf_path)
                try:
                    if 1 <= page_number <= len(doc):
                        page = doc[page_number - 1]
                        try:
                            textpage = page.get_textpage()
                            try:
                                page_text = (textpage.get_text_range() or "").strip()
                            finally:
                                textpage.close()
                        finally:
                            page.close()
                            
                    full_texts = []
                    for i in range(len(doc)):
                        p = doc[i]
                        tp = p.get_textpage()
                        t = tp.get_text_range() or ""
                        tp.close()
                        p.close()
                        full_texts.append(t.strip())
                finally:
                    doc.close()
        except Exception:
            page_text = ""
            full_texts = []

        sel_text = str(sel_text or "").strip()
        dlg = TTSDialog(window, page_text=page_text, selected_text=sel_text, pages_text=full_texts, current_page=page_number)
        window._tts_dialog = dlg
        dlg.show()

    try:
        from app.actions.annotate import _get_selection_payload_sync
        payload = _get_selection_payload_sync(window)
        sel_text = ""
        if isinstance(payload, dict):
            sel_text = str(payload.get("text") or "").strip()
        _on_selection_received(sel_text)
    except Exception:
        _on_selection_received("")
