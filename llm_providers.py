
"""
LLM provider abstraction.

Supported providers:
  - groq   : Groq Cloud (llama-3.3-70b-versatile)
  - monei  : Monei conversational agent (SSE streaming)

Set the active provider via the LLM_PROVIDER env var (default: "monei").
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod

import requests

log = logging.getLogger("monei.llm")

SYSTEM_PROMPT = (
    "You are Monei, a friendly and helpful AI voice assistant. "
    "Keep responses concise (1-3 sentences) since they will be spoken aloud. "
    "Be warm, natural, and conversational."
)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class LLMProvider(ABC):
    @abstractmethod
    def ask(self, user_text: str, chat_history: list[dict]) -> str:
        """Send *user_text* to the LLM and return the assistant reply."""


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------
class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "The 'groq' package is required for the Groq provider. "
                "Install it with: pip install groq"
            )
        self._client = Groq(api_key=api_key)

    def ask(self, user_text: str, chat_history: list[dict]) -> str:
        chat_history.append({"role": "user", "content": user_text})
        if len(chat_history) > 20:
            chat_history[:] = chat_history[-20:]

        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *chat_history,
        ]
        completion = self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            max_tokens=256,
        )
        reply = (completion.choices[0].message.content or "").strip()
        chat_history.append({"role": "assistant", "content": reply})
        return reply


# ---------------------------------------------------------------------------
# Monei
# ---------------------------------------------------------------------------
MONEI_API_URL = "https://api.monei.cc/api/v1/agent/conversations/stream"


class MoneiProvider(LLMProvider):
    def __init__(self) -> None:
        self._api_key = os.getenv("MONEI_API_KEY")
        if not self._api_key:
            raise RuntimeError("MONEI_API_KEY is not set")

    def ask(self, user_text: str, chat_history: list[dict]) -> str:
        chat_history.append({"role": "user", "content": user_text})
        if len(chat_history) > 20:
            chat_history[:] = chat_history[-20:]

        headers = {
            "accept": "text/event-stream",
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }

        resp = requests.post(
            MONEI_API_URL,
            headers=headers,
            json={"message": user_text},
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()

        reply = self._parse_sse(resp)
        chat_history.append({"role": "assistant", "content": reply})
        return reply

    @staticmethod
    def _parse_sse(resp: requests.Response) -> str:
        """Read SSE stream and return the final complete text."""
        full_text = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: "):])
            if payload.get("event") == "complete":
                full_text = payload.get("data", "").strip()
                break
            if payload.get("event") == "token":
                full_text += payload.get("data", "")

        if not full_text:
            raise RuntimeError("Monei API returned an empty response")
        return full_text


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_PROVIDERS: dict[str, type[LLMProvider]] = {
    "groq": GroqProvider,
    "monei": MoneiProvider,
}


def create_provider() -> LLMProvider:
    """Instantiate the provider indicated by the LLM_PROVIDER env var."""
    name = os.getenv("LLM_PROVIDER", "monei").lower().strip()
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{name}'. Choose from: {', '.join(_PROVIDERS)}"
        )
    log.info("Using LLM provider: %s", name)
    return cls()
