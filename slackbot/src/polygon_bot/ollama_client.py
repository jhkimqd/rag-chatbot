"""Ollama client — drop-in replacement for the Anthropic async client interface."""

from __future__ import annotations

import logging

import httpx

from polygon_bot.config import settings

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
        ollama_model = settings.ollama_model

        ollama_messages: list[dict] = []
        if system:
            ollama_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
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
            "options": {"num_predict": max_tokens},
        }

        try:
            resp = await self._http.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            return _OllamaMessage(text)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Ollama API error: %s %s", exc.response.status_code, exc.response.text[:200]
            )
            raise
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            ) from exc

    async def close(self) -> None:
        await self._http.aclose()


class OllamaClient:
    def __init__(self) -> None:
        self.messages = _OllamaMessages(settings.ollama_url)

    async def close(self) -> None:
        await self.messages.close()
