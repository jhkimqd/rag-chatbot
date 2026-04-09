"""LLM client factory — returns the right client based on LLM_BACKEND config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anthropic

from polygon_bot.config import settings

if TYPE_CHECKING:
    from polygon_bot.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

_DEV_REPLY = (
    "**[DEV MODE]** No LLM backend configured — returning a mock response.\n\n"
    "Set `LLM_BACKEND=ollama` in your `.env` to use a local model, or set "
    "`ANTHROPIC_API_KEY` to use the Anthropic API."
)


def make_client() -> anthropic.AsyncAnthropic | OllamaClient | _MockAnthropicClient:
    """Return the appropriate LLM client based on configuration."""
    if settings.llm_backend == "ollama":
        from polygon_bot.ollama_client import OllamaClient

        return OllamaClient()

    if settings.anthropic_api_key:
        return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    if settings.environment == "production":
        raise RuntimeError(
            "No LLM backend configured for production. Set ANTHROPIC_API_KEY "
            "or use LLM_BACKEND=ollama."
        )
    return _MockAnthropicClient()


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
        return _MockMessage(_DEV_REPLY)


class _MockAnthropicClient:
    def __init__(self) -> None:
        self.messages = _MockMessages()

    async def close(self) -> None:
        pass
