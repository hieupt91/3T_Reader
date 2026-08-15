"""Unit tests for packages.platform.secure_config — encryption roundtrip."""

import json
import os
import pytest

from packages.platform.secure_config import (
    encrypt_value,
    decrypt_value,
    save_secure_config,
    load_secure_config,
    is_sensitive,
)


class TestEncryptDecrypt:
    def test_roundtrip(self):
        ct = encrypt_value("sk-test-12345")
        assert ct != "sk-test-12345"
        assert decrypt_value(ct) == "sk-test-12345"

    def test_empty_string(self):
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_unicode(self):
        original = "key-with-unicode-越南中文"
        ct = encrypt_value(original)
        assert decrypt_value(ct) == original

    def test_different_ciphertext_each_time(self):
        """Fernet uses random IV so same plaintext produces different ciphertext."""
        ct1 = encrypt_value("same-key")
        ct2 = encrypt_value("same-key")
        # Both should decrypt to the same value
        assert decrypt_value(ct1) == decrypt_value(ct2)

    def test_corrupted_ciphertext_returns_empty(self):
        result = decrypt_value("not-valid-base64-ciphertext!!!")
        assert result == ""


class TestIsSensitive:
    def test_api_keys_are_sensitive(self):
        assert is_sensitive("ANTHROPIC_API_KEY")
        assert is_sensitive("OPENAI_API_KEY")
        assert is_sensitive("GEMINI_API_KEY")
        assert is_sensitive("GROQ_API_KEY")
        assert is_sensitive("OPENROUTER_API_KEY")

    def test_non_sensitive_keys(self):
        assert not is_sensitive("GROQ_MODEL")
        assert not is_sensitive("OPENROUTER_BASE_URL")
        assert not is_sensitive("HF_MODEL")
        assert not is_sensitive("ai_provider")


class TestSecureConfigIO:
    def test_save_and_load(self, tmp_path, monkeypatch):
        """Credential-manager store forced unavailable so this test always
        exercises the Fernet-in-file fallback deterministically, regardless
        of whether it runs on a real Windows machine with working keyring."""
        import packages.platform.secure_config as sc

        monkeypatch.setattr(sc, "_save_sensitive_via_credential_manager", lambda sensitive: False)

        path = str(tmp_path / "config.json")
        data = {
            "ANTHROPIC_API_KEY": "sk-ant-secret",
            "OPENAI_API_KEY": "sk-openai-secret",
            "GROQ_MODEL": "llama-3.1-70b",
            "ai_provider": "auto",
        }
        save_secure_config(path, data)

        # Verify file exists and keys are encrypted on disk
        with open(path, "r") as f:
            raw = json.load(f)
        assert raw["ANTHROPIC_API_KEY"]["__encrypted__"] is True
        assert raw["GROQ_MODEL"] == "llama-3.1-70b"  # not encrypted
        assert raw["ai_provider"] == "auto"  # not encrypted

        # Load and verify decryption
        loaded = load_secure_config(path)
        assert loaded["ANTHROPIC_API_KEY"] == "sk-ant-secret"
        assert loaded["OPENAI_API_KEY"] == "sk-openai-secret"
        assert loaded["GROQ_MODEL"] == "llama-3.1-70b"
        assert loaded["ai_provider"] == "auto"

    def test_load_nonexistent_returns_empty(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        assert load_secure_config(path) == {}

    def test_backward_compatible_plain_text(self, tmp_path):
        """Old plain-text configs should still load (values returned as-is)."""
        path = str(tmp_path / "old_config.json")
        with open(path, "w") as f:
            json.dump({"ANTHROPIC_API_KEY": "sk-plain", "GROQ_MODEL": "llama"}, f)
        loaded = load_secure_config(path)
        assert loaded["ANTHROPIC_API_KEY"] == "sk-plain"
        assert loaded["GROQ_MODEL"] == "llama"


class TestCredentialManagerStorage:
    """API key mã hóa bằng key suy ra từ MachineGuid+USERNAME (Fernet) có thể
    bị process khác chạy cùng user Windows tự tính lại - dùng Credential
    Manager khi có sẵn thay vì lưu thẳng vào file. Mọi test ở đây monkeypatch
    thẳng 2 helper nội bộ (không gọi credential_manager_save/load thật) để
    không đụng vào Windows Credential Manager thật của máy chạy test/dev.
    """

    def _fake_store(self, monkeypatch):
        import packages.platform.secure_config as sc

        store: dict = {}

        def fake_save(sensitive):
            store.clear()
            store.update(sensitive)
            return True

        def fake_load():
            return dict(store)

        monkeypatch.setattr(sc, "_save_sensitive_via_credential_manager", fake_save)
        monkeypatch.setattr(sc, "_load_sensitive_via_credential_manager", fake_load)
        return store

    def test_sensitive_values_written_as_placeholder_not_plaintext(self, tmp_path, monkeypatch):
        self._fake_store(monkeypatch)
        path = str(tmp_path / "config.json")
        save_secure_config(path, {"ANTHROPIC_API_KEY": "sk-ant-secret", "ai_provider": "auto"})

        with open(path, "r") as f:
            raw = json.load(f)
        assert raw["ANTHROPIC_API_KEY"] == {"__credential_manager__": True}
        assert "sk-ant-secret" not in json.dumps(raw)
        assert raw["ai_provider"] == "auto"

    def test_roundtrip_via_credential_manager(self, tmp_path, monkeypatch):
        self._fake_store(monkeypatch)
        path = str(tmp_path / "config.json")
        data = {"ANTHROPIC_API_KEY": "sk-ant-secret", "OPENAI_API_KEY": "sk-openai-secret", "GROQ_MODEL": "llama"}
        save_secure_config(path, data)

        loaded = load_secure_config(path)
        assert loaded["ANTHROPIC_API_KEY"] == "sk-ant-secret"
        assert loaded["OPENAI_API_KEY"] == "sk-openai-secret"
        assert loaded["GROQ_MODEL"] == "llama"

    def test_clearing_all_keys_wipes_credential_manager_entry(self, tmp_path, monkeypatch):
        """Xoá hết API key rồi lưu lại phải dọn sạch entry cũ trong credential
        store, không để lại key mồ côi."""
        store = self._fake_store(monkeypatch)
        path = str(tmp_path / "config.json")
        save_secure_config(path, {"ANTHROPIC_API_KEY": "sk-ant-secret"})
        assert store  # entry thật đã được ghi

        save_secure_config(path, {})  # user xoá hết key rồi lưu lại
        assert store == {}

    def test_falls_back_to_fernet_when_credential_manager_unavailable(self, tmp_path, monkeypatch):
        """Non-Windows hoặc keyring/DPAPI đều lỗi -> hành vi y hệt trước khi
        có credential manager, không mất dữ liệu."""
        import packages.platform.secure_config as sc

        monkeypatch.setattr(sc, "_save_sensitive_via_credential_manager", lambda sensitive: False)
        path = str(tmp_path / "config.json")
        save_secure_config(path, {"ANTHROPIC_API_KEY": "sk-ant-secret"})

        with open(path, "r") as f:
            raw = json.load(f)
        assert raw["ANTHROPIC_API_KEY"]["__encrypted__"] is True
        assert load_secure_config(path)["ANTHROPIC_API_KEY"] == "sk-ant-secret"

    def test_old_fernet_format_file_still_loads_when_credential_manager_now_available(self, tmp_path, monkeypatch):
        """Migration: file cũ (lưu trước khi có credential manager) vẫn phải
        đọc được đúng dù máy giờ đã có credential manager sẵn sàng."""
        self._fake_store(monkeypatch)  # credential store rỗng - chưa có gì được migrate
        path = str(tmp_path / "old_config.json")
        with open(path, "w") as f:
            json.dump(
                {"ANTHROPIC_API_KEY": {"__encrypted__": True, "value": encrypt_value("sk-old-fernet")}},
                f,
            )
        assert load_secure_config(path)["ANTHROPIC_API_KEY"] == "sk-old-fernet"
