"""
Thin wrapper around the Ollama HTTP API.
Keeps all model-call logic in one place.
"""
from __future__ import annotations

import logging
import requests
from config import OLLAMA_URL, MODEL_NAME, RETRY_COUNT
from prompts import RESEARCHER_SYSTEM, SYNTHESISER_SYSTEM  # re-export for convenience

logger = logging.getLogger(__name__)

# Make system prompts importable from here as a convenience
__all__ = ["chat", "RESEARCHER_SYSTEM", "SYNTHESISER_SYSTEM"]


def chat(user_message: str, system: str | None = None) -> str:
    """
    Send a single-turn chat to Ollama and return the assistant reply as a string.
    Retries up to RETRY_COUNT times on transient errors.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
    }

    last_exc: Exception | None = None
    for attempt in range(1, RETRY_COUNT + 2):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=300,  # 5-minute timeout for long LLM completions
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Ollama request failed (attempt %d/%d): %s", attempt, RETRY_COUNT + 1, exc)

    raise RuntimeError(f"Ollama failed after {RETRY_COUNT + 1} attempts: {last_exc}")
