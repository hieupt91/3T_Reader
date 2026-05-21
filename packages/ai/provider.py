"""AI provider adapter — hỗ trợ Claude API, OpenAI, và Ollama (offline local LLM)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Env var cho Ollama base URL (mặc định localhost)
_OLLAMA_URL_ENV = "OLLAMA_BASE_URL"
_OLLAMA_DEFAULT_URL = "http://localhost:11434"
_OLLAMA_DEFAULT_MODEL = "llama3"


@dataclass
class AIResponse:
    text: str
    model: str = ""
    error: Optional[str] = None
    success: bool = True


def _get_api_key(env_var: str) -> str:
    return os.environ.get(env_var, "")


def _get_ollama_url() -> str:
    return os.environ.get(_OLLAMA_URL_ENV, _OLLAMA_DEFAULT_URL).rstrip("/")


def _get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL)


def ask_claude(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi Claude API (Anthropic). Cần ANTHROPIC_API_KEY."""
    try:
        import anthropic
        key = _get_api_key("ANTHROPIC_API_KEY")
        if not key:
            return AIResponse(text="", error="Thiếu ANTHROPIC_API_KEY.", success=False)

        client = anthropic.Anthropic(api_key=key)
        msgs = [{"role": "user", "content": prompt}]
        kwargs = {"model": "claude-haiku-4-5-20251001", "max_tokens": max_tokens, "messages": msgs}
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)
        text = resp.content[0].text if resp.content else ""
        return AIResponse(text=text, model=resp.model)
    except ImportError:
        return AIResponse(text="", error="Chưa cài anthropic: pip install anthropic", success=False)
    except Exception as e:
        return AIResponse(text="", error=str(e), success=False)


def ask_openai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi OpenAI API. Cần OPENAI_API_KEY."""
    try:
        import openai
        key = _get_api_key("OPENAI_API_KEY")
        if not key:
            return AIResponse(text="", error="Thiếu OPENAI_API_KEY.", success=False)

        client = openai.OpenAI(api_key=key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        return AIResponse(text=text, model=resp.model)
    except ImportError:
        return AIResponse(text="", error="Chưa cài openai: pip install openai", success=False)
    except Exception as e:
        return AIResponse(text="", error=str(e), success=False)


def ask_ollama(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi Ollama API (local offline LLM). Không cần internet hay API key.
    Cần Ollama đang chạy tại OLLAMA_BASE_URL (mặc định http://localhost:11434).
    """
    try:
        import requests
        base_url = _get_ollama_url()
        model = _get_ollama_model()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        resp = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return AIResponse(text=text, model=f"ollama/{model}")
    except Exception as e:
        return AIResponse(text="", error=f"Ollama lỗi: {e}", success=False)


def is_ollama_available() -> bool:
    """Kiểm tra Ollama có đang chạy không (ping /api/tags)."""
    try:
        import requests
        resp = requests.get(f"{_get_ollama_url()}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def ask_ai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Tự động chọn provider theo API key / config có sẵn.
    Ưu tiên: Claude → OpenAI → Ollama (local) → lỗi."""
    if _get_api_key("ANTHROPIC_API_KEY"):
        return ask_claude(prompt, system, max_tokens)
    if _get_api_key("OPENAI_API_KEY"):
        return ask_openai(prompt, system, max_tokens)
    if is_ollama_available():
        return ask_ollama(prompt, system, max_tokens)
    return AIResponse(
        text="",
        error=(
            "Chưa cấu hình AI. Đặt ANTHROPIC_API_KEY / OPENAI_API_KEY, "
            "hoặc cài Ollama (ollama.com) để dùng AI offline."
        ),
        success=False,
    )


def is_ai_available() -> bool:
    return bool(
        _get_api_key("ANTHROPIC_API_KEY")
        or _get_api_key("OPENAI_API_KEY")
        or is_ollama_available()
    )


def get_active_provider() -> str:
    if _get_api_key("ANTHROPIC_API_KEY"):
        return "Claude (Anthropic)"
    if _get_api_key("OPENAI_API_KEY"):
        return "OpenAI GPT"
    if is_ollama_available():
        model = _get_ollama_model()
        return f"Ollama local ({model})"
    return ""
