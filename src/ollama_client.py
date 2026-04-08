"""Ollama client — drop-in replacement for the Anthropic async client interface.

Translates the ``client.messages.create(...)`` interface used throughout the
codebase into Ollama's ``/api/chat`` HTTP endpoint so the rest of the app
doesn't need to know which backend is active.
"""

from __future__ import annotations

import json
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class _TextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _OllamaMessage:
    stop_reason = "end_turn"

    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)] if text else []


class _OllamaMessages:
    """Implements the ``client.messages.create()`` interface via Ollama."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=120.0)

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list,
        system: str = "",
        tools: list | None = None,
        **_kwargs: object,
    ) -> _OllamaMessage:
        # Map the Anthropic model name to the configured Ollama model.
        # The codebase passes settings.classifier_model or settings.reasoning_model,
        # but Ollama uses its own model names.  We pick based on max_tokens as a
        # heuristic: classifier calls use max_tokens <= 10.
        if max_tokens <= 10:
            ollama_model = settings.ollama_classifier_model
        else:
            ollama_model = settings.ollama_model

        # Build Ollama message list
        ollama_messages: list[dict] = []
        if system:
            ollama_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Anthropic tool_result blocks come as lists — flatten to text
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        parts.append(block.get("content", block.get("text", str(block))))
                    else:
                        parts.append(str(block))
                content = "\n".join(parts)
            ollama_messages.append({"role": role, "content": content})

        payload = {
            "model": ollama_model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        try:
            resp = await self._http.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            return _OllamaMessage(text)
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama API error: %s %s", exc.response.status_code, exc.response.text[:200])
            raise
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )

    async def close(self) -> None:
        await self._http.aclose()


class OllamaClient:
    """Drop-in async replacement for ``anthropic.AsyncAnthropic``."""

    def __init__(self) -> None:
        self.messages = _OllamaMessages(settings.ollama_url)

    async def close(self) -> None:
        await self.messages.close()
