"""AI provider adapter — hỗ trợ Claude API, OpenAI, hoặc local LLM."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AIResponse:
    text: str
    model: str = ""
    error: Optional[str] = None
    success: bool = True


def _get_api_key(env_var: str) -> str:
    return os.environ.get(env_var, "")


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


def ask_ai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Tự động chọn provider theo API key có sẵn.
    Ưu tiên: Claude → OpenAI → lỗi."""
    if _get_api_key("ANTHROPIC_API_KEY"):
        return ask_claude(prompt, system, max_tokens)
    if _get_api_key("OPENAI_API_KEY"):
        return ask_openai(prompt, system, max_tokens)
    return AIResponse(
        text="",
        error="Chưa cấu hình AI API key. Đặt ANTHROPIC_API_KEY hoặc OPENAI_API_KEY.",
        success=False,
    )


def is_ai_available() -> bool:
    return bool(_get_api_key("ANTHROPIC_API_KEY") or _get_api_key("OPENAI_API_KEY"))


def get_active_provider() -> str:
    if _get_api_key("ANTHROPIC_API_KEY"):
        return "Claude (Anthropic)"
    if _get_api_key("OPENAI_API_KEY"):
        return "OpenAI GPT"
    return ""
