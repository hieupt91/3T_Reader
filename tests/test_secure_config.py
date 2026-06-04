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
    def test_save_and_load(self, tmp_path):
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
