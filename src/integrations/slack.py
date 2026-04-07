"""Slack integration — receives messages and sends Block Kit responses."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from src.config import settings
from src.router.protocol_switch import route_input

logger = logging.getLogger(__name__)

_MENTION_PATTERN = re.compile(r"^<@[A-Z0-9]+>\s*")

# Per-user rate limiting for Slack
_slack_rate_store: dict[str, list[float]] = {}
_SLACK_RATE_WINDOW = 60.0
_SLACK_RATE_LIMIT = 10


def _slack_rate_check(user_id: str) -> bool:
    """Return True if the Slack user is within rate limits."""
    now = time.monotonic()
    timestamps = _slack_rate_store.get(user_id, [])
    timestamps = [t for t in timestamps if now - t < _SLACK_RATE_WINDOW]
    if len(timestamps) >= _SLACK_RATE_LIMIT:
        _slack_rate_store[user_id] = timestamps
        return False
    timestamps.append(now)
    _slack_rate_store[user_id] = timestamps
    return True


def _sanitize_slack_input(text: str) -> str:
    """Strip bot mention and enforce message length limit."""
    text = _MENTION_PATTERN.sub("", text).strip()
    return text[: settings.max_message_length]


def _validate_user_id(user_id: str) -> str:
    """Sanitize Slack user ID to alphanumeric characters."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "", user_id) or "unknown"


def create_slack_app() -> AsyncApp:
    """Create and configure the Slack Bolt app."""
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    @app.event("app_mention")
    async def handle_mention(event: dict, say) -> None:
        text = event.get("text", "").strip()
        user_id = _validate_user_id(event.get("user", "unknown"))

        if not _slack_rate_check(user_id):
            await say(text="Rate limit exceeded. Please wait a moment before trying again.")
            return

        text = _sanitize_slack_input(text)
        if not text:
            return

        try:
            result = await asyncio.wait_for(
                route_input(message=text, user_id=user_id),
                timeout=settings.request_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await say(text="Request timed out. Please try a simpler question.")
            return

        blocks = _build_blocks(result)
        await say(blocks=blocks, text=result["reply"])

    @app.event("message")
    async def handle_dm(event: dict, say) -> None:
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return

        text = event.get("text", "").strip()
        user_id = _validate_user_id(event.get("user", "unknown"))

        if not _slack_rate_check(user_id):
            await say(text="Rate limit exceeded. Please wait a moment before trying again.")
            return

        text = _sanitize_slack_input(text)
        if not text:
            return

        try:
            result = await asyncio.wait_for(
                route_input(message=text, user_id=user_id),
                timeout=settings.request_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await say(text="Request timed out. Please try a simpler question.")
            return

        blocks = _build_blocks(result)
        await say(blocks=blocks, text=result["reply"])

    return app


def create_slack_handler(app: AsyncApp) -> AsyncSlackRequestHandler:
    return AsyncSlackRequestHandler(app)


def _build_blocks(result: dict) -> list[dict]:
    """Convert a chatbot response into Slack Block Kit blocks."""
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": result["reply"][:3000]},
        }
    ]

    source = result.get("source", "")
    route = result.get("route", "")
    if source or route:
        context_parts = []
        if route:
            context_parts.append(f"Route: `{route}`")
        if source:
            context_parts.append(f"Source: `{source}`")
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": " | ".join(context_parts)},
                ],
            }
        )

    return blocks
