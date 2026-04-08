"""LLM client factory — returns the right client based on LLM_BACKEND config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anthropic

from src.config import settings

if TYPE_CHECKING:
    from src.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

_DEV_REPLY = (
    "**[DEV MODE]** No LLM backend configured — returning a mock response.\n\n"
    "Set `LLM_BACKEND=ollama` in your `.env` to use a local model, or set "
    "`ANTHROPIC_API_KEY` to use the Anthropic API."
)


def is_dev_mode() -> bool:
    """True when no usable LLM backend is configured."""
    if settings.llm_backend == "ollama":
        return False
    return not settings.anthropic_api_key


def make_client() -> anthropic.AsyncAnthropic | OllamaClient | _MockAnthropicClient:
    """Return the appropriate LLM client based on configuration.

    - LLM_BACKEND=ollama  → OllamaClient (local, no API key needed)
    - LLM_BACKEND=anthropic + key set → real Anthropic client
    - LLM_BACKEND=anthropic + no key  → mock client (dev only)

    Raises RuntimeError in production if no usable backend is configured.
    """
    if settings.llm_backend == "ollama":
        from src.ollama_client import OllamaClient

        logger.debug("Using Ollama backend at %s", settings.ollama_url)
        return OllamaClient()

    if settings.anthropic_api_key:
        return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # No backend available — mock or fail
    if settings.environment == "production":
        raise RuntimeError(
            "No LLM backend configured for production. Set ANTHROPIC_API_KEY "
            "or use LLM_BACKEND=ollama."
        )
    logger.debug("Dev mode: using mock client")
    return _MockAnthropicClient()


# ---------------------------------------------------------------------------
# Mock client — mimics the anthropic.AsyncAnthropic interface for local dev
# ---------------------------------------------------------------------------


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _MockMessage:
    stop_reason = "end_turn"

    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _MockMessages:
    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list,
        system: str = "",
        tools: list | None = None,
        **_kwargs: object,
    ) -> _MockMessage:
        # Input guard classifier (max_tokens=10, system mentions ON_TOPIC)
        if max_tokens <= 10 and "ON_TOPIC" in system:
            return _MockMessage("ON_TOPIC")

        # Intent classifier (max_tokens=10, system mentions DOCS/OPS/HYBRID)
        if max_tokens <= 10 and "DOCS" in system:
            return _MockMessage("DOCS")

        # Everything else (RAG answer, ops agent response)
        return _MockMessage(_DEV_REPLY)


class _MockAnthropicClient:
    """Drop-in mock for ``anthropic.AsyncAnthropic`` used in development."""

    def __init__(self) -> None:
        self.messages = _MockMessages()

    async def close(self) -> None:
        pass
