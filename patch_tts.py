import sys

path = "app/actions/tts_dialog.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Thêm _PIPER_MODE
content = content.replace(
    '_OFFLINE_MODE = "offline"\n_OPENAI_MODE = "openai"',
    '_OFFLINE_MODE = "offline"\n_OPENAI_MODE = "openai"\n_PIPER_MODE = "piper"'
)

# 2. Thêm mode vào combobox
content = content.replace(
    'self.mode_cb.addItem("Offline (giong may)", _OFFLINE_MODE)',
    'self.mode_cb.addItem("Piper TTS (AI Offline Mượt)", _PIPER_MODE)\n        self.mode_cb.addItem("Offline (giong may)", _OFFLINE_MODE)'
)

# 3. Thêm nút btn_piper_mgr
install_btn_code = 'self.btn_install_voice.clicked.connect(self._open_voice_install)'
piper_btn_code = """self.btn_install_voice.clicked.connect(self._open_voice_install)
        
        self.btn_piper_mgr = QPushButton("Cửa hàng Giọng AI...")
        self.btn_piper_mgr.clicked.connect(self._open_piper_manager)
        self.btn_piper_mgr.setVisible(False)
        helper_layout.addWidget(self.btn_piper_mgr)"""
content = content.replace(install_btn_code, piper_btn_code)

# 4. _refresh_voice_options (chèn btn_piper_mgr.setVisible(False))
content = content.replace(
    'self.btn_install_voice.setEnabled(False)\n',
    'self.btn_install_voice.setEnabled(False)\n        if hasattr(self, "btn_piper_mgr"): self.btn_piper_mgr.setVisible(False)\n'
)

# 5. _refresh_voice_options (xử lý _PIPER_MODE)
piper_logic = """
        elif mode == _PIPER_MODE:
            from app.actions.piper_tts_manager import fetch_available_piper_voices
            piper_voices = [v for v in fetch_available_piper_voices() if v.is_downloaded]
            target_lang = self._selected_language()
            matching = [v for v in piper_voices if v.language == target_lang or target_lang == "auto"]
            for voice in matching:
                self.voice_cb.addItem(voice.name, voice)
            if hasattr(self, "btn_piper_mgr"): self.btn_piper_mgr.setVisible(True)
            self._offline_voice_missing = len(matching) == 0
            if matching:
                self._set_status(f"Piper TTS da san sang cho {_language_label(target_lang)}.")
            else:
                self._set_status(f"Chua co giong Piper cho {_language_label(target_lang)}. Bam 'Cua hang Giong AI' de tai them.")
"""
content = content.replace(
    'else:\n            target_lang = self._selected_language()',
    piper_logic.lstrip('\n') + '        else:\n            target_lang = self._selected_language()'
)

# 6. Thêm hàm _open_piper_manager
mgr_func = """
    def _open_piper_manager(self):
        from app.actions.piper_tts_manager import PiperVoiceManagerDialog
        dlg = PiperVoiceManagerDialog(self)
        dlg.exec()
        self._refresh_voice_options()
"""
content = content.replace(
    'def _open_voice_install(self):',
    mgr_func.lstrip('\n') + '\n    def _open_voice_install(self):'
)

# 7. Xử lý Play Piper TTS
run_logic = """
            if mode == _PIPER_MODE:
                from app.actions.piper_tts_manager import synthesize_audio_piper
                voice = self.voice_cb.currentData()
                if not voice:
                    self._bridge.finished.emit(False, "Chua chon giong Piper.")
                    return
                # Ghi ra file tam
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    audio_path = f.name
                self._bridge.status.emit("Dang tong hop giong Piper...")
                ok = synthesize_audio_piper(self.text_to_speak, voice.local_onnx_path, audio_path)
                if not ok:
                    self._bridge.finished.emit(False, "Loi tao giong Piper.")
                    return
                _start_async_wav(audio_path)
                self._bridge.finished.emit(True, "Dang phat Piper TTS.")
                return
"""
content = content.replace(
    'if mode == _OPENAI_MODE:',
    run_logic.lstrip('\n') + '        if mode == _OPENAI_MODE:'
)

# Tắt sync play nếu Piper không có giọng
content = content.replace(
    'self.btn_play.setEnabled((not self._offline_voice_missing) and self.voice_cb.count() > 0)',
    'self.btn_play.setEnabled(self.voice_cb.count() > 0)'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched TTS Dialog successfully!")
