"""Slack integration — receives messages and sends Block Kit responses."""

from __future__ import annotations

import logging

from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from src.config import settings
from src.router.protocol_switch import route_input

logger = logging.getLogger(__name__)


def create_slack_app() -> AsyncApp:
    """Create and configure the Slack Bolt app."""
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    @app.event("app_mention")
    async def handle_mention(event: dict, say) -> None:
        text = event.get("text", "").strip()
        user_id = event.get("user", "unknown")
        # Strip the bot mention from the beginning
        if ">" in text:
            text = text.split(">", 1)[1].strip()

        result = await route_input(message=text, user_id=user_id)
        blocks = _build_blocks(result)
        await say(blocks=blocks, text=result["reply"])

    @app.event("message")
    async def handle_dm(event: dict, say) -> None:
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        text = event.get("text", "").strip()
        user_id = event.get("user", "unknown")

        result = await route_input(message=text, user_id=user_id)
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
