"""AI provider adapter — hỗ trợ nhiều backend AI và fallback tự động."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

# Env var cho Ollama base URL (mặc định localhost)
_OLLAMA_URL_ENV = "OLLAMA_BASE_URL"
_OLLAMA_DEFAULT_URL = "http://localhost:11434"
_OLLAMA_DEFAULT_MODEL = "llama3"

# 3T AI server — bạn cấu hình sau khi có server
_3T_AI_BASE_URL = "https://ai.3treader.vn/v1"

_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
_AI_PROVIDER_ORDER = ("claude", "openai", "groq", "openrouter", "gemini", "huggingface", "ollama")
_GEMINI_MODEL_FALLBACKS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
)
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_HF_DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"


@dataclass
class AIResponse:
    text: str
    model: str = ""
    error: Optional[str] = None
    success: bool = True


def _get_api_key(env_var: str) -> str:
    return os.environ.get(env_var, "")


def _is_auth_error_text(text: str) -> bool:
    """Return True when an error message looks like an auth/key failure."""
    text = (text or "").lower()
    return (
        "invalid x-api-key" in text
        or "invalid api key" in text
        or "api_key_invalid" in text
        or "authentication_error" in text
        or "unauthorized" in text
        or "401" in text
        or "permission denied" in text
        or "invalid_api_key" in text
        or "không hợp lệ" in text
        or "khong hop le" in text
    )


def _is_quota_error_text(text: str) -> bool:
    text = (text or "").lower()
    return (
        "quota" in text
        or "rate limit" in text
        or "rate_limit" in text
        or "too many requests" in text
        or "429" in text
        or "insufficient_quota" in text
        or "resource_exhausted" in text
        or "hết quota" in text
        or "het quota" in text
    )


def _friendly_error(provider: str, error: str) -> str:
    if _is_auth_error_text(error):
        return f"{provider}: API key không hợp lệ hoặc đã hết quyền truy cập."
    if _is_quota_error_text(error):
        return f"{provider}: hết quota hoặc bị giới hạn tốc độ, app đã thử provider fallback nếu có."
    return f"{provider}: {error}"


def _clear_ai_key(env_var: str) -> None:
    """Remove a stale AI key from the process and persisted config."""
    os.environ.pop(env_var, None)
    try:
        from packages.platform import get_app_data_dir
        import json

        config_path = os.path.join(get_app_data_dir(), "ai_config.json")
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        if env_var in data:
            data.pop(env_var, None)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _get_ollama_url() -> str:
    return os.environ.get(_OLLAMA_URL_ENV, _OLLAMA_DEFAULT_URL).rstrip("/")


def _get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL)


def _normalize_provider_name(name: str) -> str:
    name = (name or "").strip().lower()
    aliases = {
        "anthropic": "claude",
        "claude": "claude",
        "openai": "openai",
        "groq": "groq",
        "openrouter": "openrouter",
        "gemini": "gemini",
        "google": "gemini",
        "huggingface": "huggingface",
        "hf": "huggingface",
        "ollama": "ollama",
        "auto": "auto",
        "default": "auto",
        "": "auto",
    }
    return aliases.get(name, name)


def _provider_attempts() -> list[tuple[str, str, Callable[[str, str, int], AIResponse]]]:
    return [
        ("Claude", "ANTHROPIC_API_KEY", ask_claude),
        ("OpenAI", "OPENAI_API_KEY", ask_openai),
        ("Groq", "GROQ_API_KEY", ask_groq),
        ("OpenRouter", "OPENROUTER_API_KEY", ask_openrouter),
        ("Gemini", "GEMINI_API_KEY", ask_gemini),
        ("HuggingFace", "HF_API_KEY", ask_huggingface),
        ("Ollama", "", ask_ollama),
    ]


def _preferred_provider() -> str:
    return _normalize_provider_name(os.environ.get("AI_PROVIDER", "auto"))


def _openai_compatible_request(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 2048,
    extra_headers: Optional[dict] = None,
) -> AIResponse:
    try:
        import openai

        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        return AIResponse(text=text, model=resp.model)
    except ImportError:
        return AIResponse(text="", error="Chưa cài openai: pip install openai", success=False)
    except Exception as e:
        msg = str(e)
        if _is_auth_error_text(msg):
            return AIResponse(text="", error="API key không hợp lệ hoặc chưa có quyền truy cập provider này.", success=False)
        if _is_quota_error_text(msg):
            return AIResponse(text="", error="Provider hết quota hoặc bị giới hạn tốc độ.", success=False)
        return AIResponse(text="", error=msg, success=False)


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
        msg = str(e)
        if _is_auth_error_text(msg):
            return AIResponse(
                text="",
                error="Claude API key không hợp lệ hoặc đã bị thu hồi. Hãy mở Cài đặt AI để nhập lại.",
                success=False,
            )
        if _is_quota_error_text(msg):
            return AIResponse(text="", error="Claude hết quota hoặc bị giới hạn tốc độ.", success=False)
        return AIResponse(text="", error=msg, success=False)


def ask_openai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi OpenAI API. Cần OPENAI_API_KEY."""
    key = _get_api_key("OPENAI_API_KEY")
    if not key:
        return AIResponse(text="", error="Thiếu OPENAI_API_KEY.", success=False)
    return _openai_compatible_request(
        api_key=key,
        base_url="https://api.openai.com/v1",
        model=os.environ.get("OPENAI_MODEL", _OPENAI_DEFAULT_MODEL),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
    )


def ask_groq(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi Groq OpenAI-compatible API."""
    key = _get_api_key("GROQ_API_KEY")
    if not key:
        return AIResponse(text="", error="Thiếu GROQ_API_KEY.", success=False)
    return _openai_compatible_request(
        api_key=key,
        base_url=os.environ.get("GROQ_BASE_URL", _GROQ_BASE_URL),
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
    )


def ask_openrouter(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi OpenRouter OpenAI-compatible API."""
    key = _get_api_key("OPENROUTER_API_KEY")
    if not key:
        return AIResponse(text="", error="Thiếu OPENROUTER_API_KEY.", success=False)
    return _openai_compatible_request(
        api_key=key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", _OPENROUTER_BASE_URL),
        model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        extra_headers={
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://reader.3tcomputer.com"),
            "X-Title": os.environ.get("OPENROUTER_APP_NAME", "3T Reader"),
        },
    )


def ask_huggingface(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Gọi HuggingFace Inference API."""
    try:
        from huggingface_hub import InferenceClient

        token = _get_api_key("HF_API_KEY")
        if not token:
            return AIResponse(text="", error="Thiếu HF_API_KEY.", success=False)

        model = os.environ.get("HF_MODEL", _HF_DEFAULT_MODEL)
        client = InferenceClient(model=model, token=token)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            messages=messages,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        return AIResponse(text=text, model=model)
    except ImportError:
        return AIResponse(text="", error="Chưa cài huggingface_hub: pip install huggingface_hub", success=False)
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


def _save_3t_token(token: str, email: str) -> None:
    """Persist 3T AI token securely (encrypted at rest)."""
    try:
        from packages.platform import get_app_data_dir, save_secure_config, load_secure_config
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")
        data = load_secure_config(config_path) if os.path.exists(config_path) else {}
        data["3T_AI_TOKEN"] = token
        data["3T_AI_EMAIL"] = email
        save_secure_config(config_path, data)
    except Exception:
        pass


def _clear_3t_token() -> None:
    """Remove 3T AI token from secure storage."""
    try:
        from packages.platform import get_app_data_dir, save_secure_config, load_secure_config
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")
        data = load_secure_config(config_path) if os.path.exists(config_path) else {}
        data.pop("3T_AI_TOKEN", None)
        data.pop("3T_AI_EMAIL", None)
        save_secure_config(config_path, data)
    except Exception:
        pass


def _load_3t_token() -> tuple[str, str]:
    """Load 3T AI token from secure storage. Returns (token, email)."""
    try:
        from packages.platform import get_app_data_dir, load_secure_config
        config_path = os.path.join(get_app_data_dir(), "ai_config.json")
        if os.path.exists(config_path):
            data = load_secure_config(config_path)
            return data.get("3T_AI_TOKEN", ""), data.get("3T_AI_EMAIL", "")
    except Exception:
        pass
    return "", ""


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
            # Store in env var for runtime use + persist encrypted to disk
            os.environ["3T_AI_TOKEN"] = token
            os.environ["3T_AI_EMAIL"] = email
            _save_3t_token(token, email)
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
    _clear_3t_token()


def is_3t_ai_logged_in() -> bool:
    # Check env var first (runtime), then secure storage (persisted)
    if os.environ.get("3T_AI_TOKEN"):
        return True
    token, _ = _load_3t_token()
    if token:
        os.environ["3T_AI_TOKEN"] = token
        return True
    return False


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
        last_err = ""
        for model_name in _GEMINI_MODEL_FALLBACKS:
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
                if _is_auth_error_text(last_err):
                    return AIResponse(
                        text="",
                        error="Gemini API key không hợp lệ hoặc chưa bật quyền Generative Language API.",
                        success=False,
                    )
                continue
        if _is_quota_error_text(last_err):
            return AIResponse(text="", error=f"Gemini hết quota hoặc bị giới hạn tốc độ: {last_err}", success=False)
        return AIResponse(text="", error=f"Gemini lỗi: {last_err}", success=False)
    except ImportError:
        return AIResponse(text="", error="Chưa cài google-genai: pip install google-genai", success=False)
    except Exception as e:
        return AIResponse(text="", error=str(e), success=False)


def ask_ai(prompt: str, system: str = "", max_tokens: int = 2048) -> AIResponse:
    """Tự động chọn provider. Ưu tiên theo cấu hình và fallback cho tới khi thành công."""
    mode = os.environ.get("AI_MODE", "personal")
    if mode == "3t_ai":
        return ask_3t_ai(prompt, system, max_tokens)
    preferred = _preferred_provider()
    attempts: list[tuple[str, str, Callable[[str, str, int], AIResponse]]] = []
    for provider_name, key_name, fn in _provider_attempts():
        if key_name and not _get_api_key(key_name):
            continue
        if provider_name == "Ollama" and not is_ollama_available():
            continue
        attempts.append((provider_name, key_name, fn))

    if preferred != "auto" and attempts:
        idx = next((i for i, (name, _, _) in enumerate(attempts) if _normalize_provider_name(name) == preferred), None)
        if idx is not None and idx > 0:
            attempts = [attempts[idx]] + attempts[:idx] + attempts[idx + 1 :]

    if not attempts:
        return AIResponse(
            text="",
            error="Chưa cấu hình API key AI. Vào Settings để cài đặt.",
            success=False,
        )

    errors = []
    auth_errors = []
    quota_errors = []
    for provider_name, key_name, fn in attempts:
        resp = fn(prompt, system, max_tokens)
        if resp.success and resp.text.strip():
            return resp
        if resp.error:
            if key_name and _is_auth_error_text(resp.error):
                auth_errors.append(provider_name)
                _clear_ai_key(key_name)
                continue
            if _is_quota_error_text(resp.error):
                quota_errors.append(provider_name)
            errors.append(_friendly_error(provider_name, resp.error))

    if auth_errors and not errors:
        return AIResponse(
            text="",
            error="API key AI không hợp lệ. Mở Cài đặt AI để cập nhật key hoặc chọn provider khác.",
            success=False,
        )
    if quota_errors and not errors:
        return AIResponse(
            text="",
            error="Các provider AI đang hết quota hoặc bị giới hạn tốc độ. Hãy cấu hình thêm Gemini/Groq/OpenRouter/Ollama để fallback.",
            success=False,
        )
    return AIResponse(
        text="",
        error=" | ".join(errors[-3:]) if errors else "Không có provider AI khả dụng.",
        success=False,
    )


def is_ai_available() -> bool:
    if os.environ.get("AI_MODE") == "3t_ai":
        return is_3t_ai_logged_in()
    return bool(
        _get_api_key("ANTHROPIC_API_KEY")
        or _get_api_key("OPENAI_API_KEY")
        or _get_api_key("GROQ_API_KEY")
        or _get_api_key("OPENROUTER_API_KEY")
        or _get_api_key("GEMINI_API_KEY")
        or _get_api_key("HF_API_KEY")
        or is_ollama_available()
    )


def get_active_provider() -> str:
    if os.environ.get("AI_MODE") == "3t_ai":
        email = os.environ.get("3T_AI_EMAIL", "")
        return f"3T AI ({email})" if email else "3T AI"
    preferred = _preferred_provider()
    if preferred != "auto":
        preferred_label = {
            "claude": "Claude (Anthropic)",
            "openai": "OpenAI GPT",
            "groq": f"Groq ({os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')})",
            "openrouter": f"OpenRouter ({os.environ.get('OPENROUTER_MODEL', 'openai/gpt-4o-mini')})",
            "gemini": "Google Gemini 2.5 Flash",
            "huggingface": f"HuggingFace ({os.environ.get('HF_MODEL', _HF_DEFAULT_MODEL)})",
            "ollama": f"Ollama local ({_get_ollama_model()})",
        }.get(preferred, "")
        if preferred_label:
            if preferred == "claude" and _get_api_key("ANTHROPIC_API_KEY"):
                return preferred_label
            if preferred == "openai" and _get_api_key("OPENAI_API_KEY"):
                return preferred_label
            if preferred == "groq" and _get_api_key("GROQ_API_KEY"):
                return preferred_label
            if preferred == "openrouter" and _get_api_key("OPENROUTER_API_KEY"):
                return preferred_label
            if preferred == "gemini" and _get_api_key("GEMINI_API_KEY"):
                return preferred_label
            if preferred == "huggingface" and _get_api_key("HF_API_KEY"):
                return preferred_label
            if preferred == "ollama" and is_ollama_available():
                return preferred_label
    if _get_api_key("ANTHROPIC_API_KEY"):
        return "Claude (Anthropic)"
    if _get_api_key("OPENAI_API_KEY"):
        return "OpenAI GPT"
    if _get_api_key("GROQ_API_KEY"):
        return f"Groq ({os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')})"
    if _get_api_key("OPENROUTER_API_KEY"):
        return f"OpenRouter ({os.environ.get('OPENROUTER_MODEL', 'openai/gpt-4o-mini')})"
    if _get_api_key("GEMINI_API_KEY"):
        return "Google Gemini 2.5 Flash"
    if _get_api_key("HF_API_KEY"):
        return f"HuggingFace ({os.environ.get('HF_MODEL', _HF_DEFAULT_MODEL)})"
    if is_ollama_available():
        model = _get_ollama_model()
        return f"Ollama local ({model})"
    return ""
