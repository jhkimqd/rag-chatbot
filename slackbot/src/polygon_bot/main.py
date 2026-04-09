"""Slack bot entry point — starts the Slack Bolt app for Polygon ops."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from slack_bolt.async_app import AsyncApp

from polygon_bot.config import settings
from polygon_bot.router import route_input

logger = logging.getLogger(__name__)

_MENTION_PATTERN = re.compile(r"^<@[A-Z0-9]+>\s*")

# Per-user rate limiting
_slack_rate_store: dict[str, list[float]] = {}
_SLACK_RATE_WINDOW = 60.0
_SLACK_RATE_LIMIT = 10


def _slack_rate_check(user_id: str) -> bool:
    now = time.monotonic()
    timestamps = _slack_rate_store.get(user_id, [])
    timestamps = [t for t in timestamps if now - t < _SLACK_RATE_WINDOW]
    if len(timestamps) >= _SLACK_RATE_LIMIT:
        _slack_rate_store[user_id] = timestamps
        return False
    timestamps.append(now)
    _slack_rate_store[user_id] = timestamps
    return True


def _sanitize_input(text: str) -> str:
    text = _MENTION_PATTERN.sub("", text).strip()
    return text[: settings.max_message_length]


def _validate_user_id(user_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "", user_id) or "unknown"


def _build_blocks(result: dict) -> list[dict]:
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
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": " | ".join(context_parts)}],
        })

    return blocks


async def _handle_message(event: dict, say) -> None:
    """Shared handler for mentions and DMs."""
    text = event.get("text", "").strip()
    user_id = _validate_user_id(event.get("user", "unknown"))

    if not _slack_rate_check(user_id):
        await say(text="Rate limit exceeded. Please wait a moment before trying again.")
        return

    text = _sanitize_input(text)
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


def create_app() -> AsyncApp:
    """Create and configure the Slack Bolt app."""
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    @app.event("app_mention")
    async def handle_mention(event: dict, say) -> None:
        await _handle_message(event, say)

    @app.event("message")
    async def handle_dm(event: dict, say) -> None:
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        await _handle_message(event, say)

    return app


def main() -> None:
    """Start the Slack bot."""
    logging.basicConfig(level=settings.log_level.upper())
    logger.info("Starting Polygon Ops Slack Bot (env=%s)", settings.environment)

    app = create_app()

    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

    handler = AsyncSocketModeHandler(app, app_token=settings.slack_app_token)
    asyncio.run(handler.start_async())


if __name__ == "__main__":
    main()
