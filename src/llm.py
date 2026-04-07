"""LLM client factory — returns a real or mock Anthropic client based on config."""

from __future__ import annotations

import logging

import anthropic

from src.config import settings

logger = logging.getLogger(__name__)

_DEV_REPLY = (
    "**[DEV MODE]** No `ANTHROPIC_API_KEY` configured — returning a mock response.\n\n"
    "Set `ANTHROPIC_API_KEY` in your `.env` file to get real answers."
)


def is_dev_mode() -> bool:
    """True when no real Anthropic API key is configured."""
    return not settings.anthropic_api_key


def make_client() -> anthropic.AsyncAnthropic | _MockAnthropicClient:
    """Return a real Anthropic client, or a mock client in dev mode."""
    if is_dev_mode():
        logger.debug("Dev mode: using mock Anthropic client")
        return _MockAnthropicClient()
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


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
