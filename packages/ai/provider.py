"""AI provider adapter — hỗ trợ Claude API, OpenAI, Ollama, và 3T AI."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Env var cho Ollama base URL (mặc định localhost)
_OLLAMA_URL_ENV = "OLLAMA_BASE_URL"
_OLLAMA_DEFAULT_URL = "http://localhost:11434"
_OLLAMA_DEFAULT_MODEL = "llama3"

# 3T AI server — bạn cấu hình sau khi có server
_3T_AI_BASE_URL = "https://ai.3treader.vn/v1"


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


def ask_3t_ai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi 3T AI server. Cần 3T_AI_TOKEN (lấy sau khi đăng nhập tài khoản 3T)."""
    try:
        import requests
        token = os.environ.get("3T_AI_TOKEN", "")
        base_url = os.environ.get("3T_AI_BASE_URL", _3T_AI_BASE_URL)
        if not token:
            return AIResponse(text="", error="Chưa đăng nhập tài khoản 3T AI.", success=False)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = requests.post(
            f"{base_url}/chat",
            json={"messages": messages, "max_tokens": max_tokens},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        if resp.status_code == 401:
            return AIResponse(text="", error="Phiên đăng nhập 3T AI hết hạn. Vui lòng đăng nhập lại.", success=False)
        if resp.status_code == 403:
            return AIResponse(text="", error="Tài khoản 3T AI chưa được kích hoạt.", success=False)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("text") or data.get("content") or ""
        return AIResponse(text=text, model="3T AI")
    except Exception as e:
        return AIResponse(text="", error=f"3T AI lỗi: {e}", success=False)


def login_3t_ai(email: str, password: str) -> dict:
    """Đăng nhập tài khoản 3T, trả về {'token': ..., 'email': ..., 'error': ...}."""
    try:
        import requests
        base_url = os.environ.get("3T_AI_BASE_URL", _3T_AI_BASE_URL)
        resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token", "")
            os.environ["3T_AI_TOKEN"] = token
            os.environ["3T_AI_EMAIL"] = email
            return {"token": token, "email": email, "error": None}
        elif resp.status_code == 401:
            return {"token": "", "email": "", "error": "Sai email hoặc mật khẩu."}
        else:
            return {"token": "", "email": "", "error": f"Lỗi server: {resp.status_code}"}
    except Exception as e:
        return {"token": "", "email": "", "error": f"Không kết nối được server 3T: {e}"}


def logout_3t_ai():
    os.environ.pop("3T_AI_TOKEN", None)
    os.environ.pop("3T_AI_EMAIL", None)


def is_3t_ai_logged_in() -> bool:
    return bool(os.environ.get("3T_AI_TOKEN", ""))


def ask_gemini(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi Google Gemini API. Cần GEMINI_API_KEY."""
    try:
        from google import genai
        from google.genai import types
        key = _get_api_key("GEMINI_API_KEY")
        if not key:
            return AIResponse(text="", error="Thiếu GEMINI_API_KEY.", success=False)

        client = genai.Client(api_key=key)
        contents = prompt
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system if system else None,
        )
        for model_name in ("gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-2.0-flash", "gemini-1.5-flash"):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                text = resp.text or ""
                return AIResponse(text=text, model=model_name)
            except Exception as e:
                last_err = str(e)
                if "429" not in last_err and "quota" not in last_err.lower() and "not found" not in last_err.lower():
                    raise
        return AIResponse(text="", error=f"Gemini quota hết: {last_err}", success=False)
    except ImportError:
        return AIResponse(text="", error="Chưa cài google-genai: pip install google-genai", success=False)
    except Exception as e:
        return AIResponse(text="", error=str(e), success=False)


def ask_ai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Tự động chọn provider. Ưu tiên: 3T AI → Claude → OpenAI → Gemini → Ollama → lỗi."""
    mode = os.environ.get("AI_MODE", "personal")
    if mode == "3t_ai":
        return ask_3t_ai(prompt, system, max_tokens)
    if _get_api_key("ANTHROPIC_API_KEY"):
        return ask_claude(prompt, system, max_tokens)
    if _get_api_key("OPENAI_API_KEY"):
        return ask_openai(prompt, system, max_tokens)
    if _get_api_key("GEMINI_API_KEY"):
        return ask_gemini(prompt, system, max_tokens)
    if is_ollama_available():
        return ask_ollama(prompt, system, max_tokens)
    return AIResponse(
        text="",
        error="Chưa cấu hình API key AI. Vào Settings để cài đặt.",
        success=False,
    )


def is_ai_available() -> bool:
    if os.environ.get("AI_MODE") == "3t_ai":
        return is_3t_ai_logged_in()
    return bool(
        _get_api_key("ANTHROPIC_API_KEY")
        or _get_api_key("OPENAI_API_KEY")
        or _get_api_key("GEMINI_API_KEY")
        or is_ollama_available()
    )


def get_active_provider() -> str:
    if os.environ.get("AI_MODE") == "3t_ai":
        email = os.environ.get("3T_AI_EMAIL", "")
        return f"3T AI ({email})" if email else "3T AI"
    if _get_api_key("ANTHROPIC_API_KEY"):
        return "Claude (Anthropic)"
    if _get_api_key("OPENAI_API_KEY"):
        return "OpenAI GPT"
    if _get_api_key("GEMINI_API_KEY"):
        return "Google Gemini"
    if is_ollama_available():
        model = _get_ollama_model()
        return f"Ollama local ({model})"
    return ""
