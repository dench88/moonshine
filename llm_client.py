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
from dataclasses import dataclass

from config import (
    OLLAMA_URL, RETRY_COUNT,
    ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY,
)
from prompts import RESEARCHER_SYSTEM, SYNTHESISER_SYSTEM

logger = logging.getLogger(__name__)

__all__ = ["chat", "LLMResponse", "RESEARCHER_SYSTEM", "SYNTHESISER_SYSTEM"]


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


def _parse_model(model_str: str) -> tuple[str, str]:
    """Split 'provider/model' → (provider, model). Defaults to ollama."""
    if "/" in model_str:
        provider, model_name = model_str.split("/", 1)
        known = {"ollama", "anthropic", "openai", "deepseek"}
        if provider.lower() in known:
            return provider.lower(), model_name
    return "ollama", model_str


def _chat_ollama(model_name: str, messages: list[dict], keep_alive: int | None = None) -> LLMResponse:
    payload: dict = {"model": model_name, "messages": messages, "stream": False}
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_COUNT + 2):
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                text=data["message"]["content"],
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
            )
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Ollama attempt %d/%d failed: %s", attempt, RETRY_COUNT + 1, exc)
    raise RuntimeError(f"Ollama failed after {RETRY_COUNT + 1} attempts: {last_exc}")


def _chat_anthropic(model_name: str, user_message: str, system: str | None) -> LLMResponse:
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
    return LLMResponse(
        text=resp.content[0].text,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


def _chat_openai_compat(model_name: str, messages: list[dict], api_key: str,
                         base_url: str | None = None) -> LLMResponse:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed — run: pip install openai")
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(model=model_name, messages=messages)
    return LLMResponse(
        text=resp.choices[0].message.content,
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
    )


def chat(user_message: str, system: str | None = None, model: str | None = None,
         keep_alive: int | None = None) -> LLMResponse:
    """
    Send a single-turn chat and return an LLMResponse with .text and token counts.
    model defaults to RESEARCHER_MODEL if omitted; callers should always pass it explicitly.
    """
    from config import RESEARCHER_MODEL
    model = model or RESEARCHER_MODEL

    provider, model_name = _parse_model(model)
    logger.debug("llm_client: provider=%s model=%s", provider, model_name)

    messages = []
    if system and provider != "anthropic":
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_message})

    if provider == "ollama":
        return _chat_ollama(model_name, messages, keep_alive=keep_alive)

    elif provider == "anthropic":
        return _chat_anthropic(model_name, user_message, system)

    elif provider == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return _chat_openai_compat(model_name, messages, api_key=OPENAI_API_KEY)

    elif provider == "deepseek":
        if not DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        return _chat_openai_compat(model_name, messages, api_key=DEEPSEEK_API_KEY,
                                    base_url="https://api.deepseek.com")

    else:
        raise ValueError(f"Unknown provider {provider!r}. Use: ollama, anthropic, openai, deepseek.")
