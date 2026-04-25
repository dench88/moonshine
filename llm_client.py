"""
Unified LLM client that dispatches to Ollama, Anthropic, OpenAI, or DeepSeek.

Model string format: "provider/model-name"
  ollama/gpt-oss:20b
  ollama/qwen3:14b
  ollama/huihui_ai/qwen3-abliterated:14b   (note: slash in model name is fine, only first slash is the provider separator)
  anthropic/claude-sonnet-4-6
  openai/gpt-4o
  deepseek/deepseek-chat

If no provider prefix is given, ollama is assumed (backward compat).
"""
from __future__ import annotations

import logging
import requests

from config import (
    OLLAMA_URL, RETRY_COUNT,
    ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY,
)
from prompts import RESEARCHER_SYSTEM, SYNTHESISER_SYSTEM

logger = logging.getLogger(__name__)

__all__ = ["chat", "RESEARCHER_SYSTEM", "SYNTHESISER_SYSTEM"]


def _parse_model(model_str: str) -> tuple[str, str]:
    """Split 'provider/model' → (provider, model). Defaults to ollama."""
    if "/" in model_str:
        provider, model_name = model_str.split("/", 1)
        known = {"ollama", "anthropic", "openai", "deepseek"}
        if provider.lower() in known:
            return provider.lower(), model_name
    return "ollama", model_str


def _chat_ollama(model_name: str, messages: list[dict]) -> str:
    payload = {"model": model_name, "messages": messages, "stream": False}
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_COUNT + 2):
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Ollama attempt %d/%d failed: %s", attempt, RETRY_COUNT + 1, exc)
    raise RuntimeError(f"Ollama failed after {RETRY_COUNT + 1} attempts: {last_exc}")


def _chat_anthropic(model_name: str, user_message: str, system: str | None) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed — run: pip install anthropic")
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    kwargs: dict = dict(
        model=model_name,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_message}],
    )
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return resp.content[0].text


def _chat_openai(model_name: str, messages: list[dict]) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed — run: pip install openai")
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(model=model_name, messages=messages)
    return resp.choices[0].message.content


def _chat_deepseek(model_name: str, messages: list[dict]) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed — run: pip install openai")
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(model=model_name, messages=messages)
    return resp.choices[0].message.content


def chat(user_message: str, system: str | None = None, model: str | None = None) -> str:
    """
    Send a single-turn chat and return the assistant reply.
    model defaults to RESEARCHER_MODEL if omitted; callers should always pass it explicitly.
    """
    from config import RESEARCHER_MODEL
    model = model or RESEARCHER_MODEL

    provider, model_name = _parse_model(model)
    logger.debug("llm_client: provider=%s model=%s", provider, model_name)

    if provider == "ollama":
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_message})
        return _chat_ollama(model_name, messages)

    elif provider == "anthropic":
        return _chat_anthropic(model_name, user_message, system)

    elif provider == "openai":
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_message})
        return _chat_openai(model_name, messages)

    elif provider == "deepseek":
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_message})
        return _chat_deepseek(model_name, messages)

    else:
        raise ValueError(f"Unknown provider {provider!r}. Use: ollama, anthropic, openai, deepseek.")
