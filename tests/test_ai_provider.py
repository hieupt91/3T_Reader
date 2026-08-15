from __future__ import annotations

import sys

import packages.ai.provider as provider


def test_ask_ai_skips_invalid_auth_provider_and_uses_next_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")
    monkeypatch.setenv("OPENAI_API_KEY", "good-key")
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.setattr(provider, "is_ollama_available", lambda: False)
    monkeypatch.setattr(
        provider,
        "ask_claude",
        lambda prompt, system="", max_tokens=2048: provider.AIResponse(
            text="",
            error="Claude API key không hợp lệ hoặc đã bị thu hồi. Hãy mở Cài đặt AI để nhập lại.",
            success=False,
        ),
    )
    monkeypatch.setattr(
        provider,
        "ask_openai",
        lambda prompt, system="", max_tokens=2048: provider.AIResponse(
            text="ok",
            model="gpt-4o-mini",
            success=True,
        ),
    )

    resp = provider.ask_ai("hello")

    assert resp.success is True
    assert resp.text == "ok"
    assert "ANTHROPIC_API_KEY" not in provider.os.environ


def test_ask_ai_returns_clear_message_when_only_auth_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("HF_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.setattr(provider, "is_ollama_available", lambda: False)
    monkeypatch.setattr(
        provider,
        "ask_claude",
        lambda prompt, system="", max_tokens=2048: provider.AIResponse(
            text="",
            error="Claude API key không hợp lệ hoặc đã bị thu hồi. Hãy mở Cài đặt AI để nhập lại.",
            success=False,
        ),
    )

    resp = provider.ask_ai("hello")

    assert resp.success is False
    assert "API key AI không hợp lệ" in resp.error


def test_quota_error_does_not_clear_key_and_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "quota-key")
    monkeypatch.setenv("GROQ_API_KEY", "good-key")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.setattr(provider, "is_ollama_available", lambda: False)
    monkeypatch.setattr(
        provider,
        "ask_gemini",
        lambda prompt, system="", max_tokens=2048: provider.AIResponse(
            text="",
            error="Gemini hết quota hoặc bị giới hạn tốc độ: 429 RESOURCE_EXHAUSTED",
            success=False,
        ),
    )
    monkeypatch.setattr(
        provider,
        "ask_groq",
        lambda prompt, system="", max_tokens=2048: provider.AIResponse(
            text="ok",
            model="llama",
            success=True,
        ),
    )

    resp = provider.ask_ai("hello")

    assert resp.success is True
    assert resp.text == "ok"
    assert provider.os.environ["GEMINI_API_KEY"] == "quota-key"


def test_openai_compatible_auth_error_is_normalized(monkeypatch):
    class _Completions:
        def create(self, **_kwargs):
            raise Exception("401 invalid_api_key")

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

        def __init__(self, **_kwargs):
            pass

    class _OpenAI:
        OpenAI = _Client

    monkeypatch.setitem(sys.modules, "openai", _OpenAI)

    resp = provider._openai_compatible_request(
        api_key="bad",
        base_url="https://example.invalid/v1",
        model="test",
        prompt="hello",
    )

    assert resp.success is False
    assert "không hợp lệ" in resp.error


# --- Unit tests for helper functions ---


def test_is_auth_error_text():
    assert provider._is_auth_error_text("Error 401: Unauthorized") is True
    assert provider._is_auth_error_text("Invalid API key provided") is True
    assert provider._is_auth_error_text("Rate limit exceeded") is False


def test_is_quota_error_text():
    assert provider._is_quota_error_text("Error 429: Too Many Requests") is True
    assert provider._is_quota_error_text("Quota exceeded") is True
    assert provider._is_quota_error_text("Insufficient quota") is True
    assert provider._is_quota_error_text("Invalid API key") is False


def test_normalize_provider_name():
    assert provider._normalize_provider_name("hf") == "huggingface"
    assert provider._normalize_provider_name("ollama") == "ollama"
    assert provider._normalize_provider_name("OpenAI") == "openai"
