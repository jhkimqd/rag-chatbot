"""Interactive CLI for testing the Slack bot routing locally — no Slack needed.

Routes through the same `route_input` function used by the real Slack bot,
so slash commands, ops agent, and tool-calling all work the same way.

Usage:
    python -m polygon_bot.cli                # uses LLM_BACKEND from .env
    LLM_BACKEND=ollama python -m polygon_bot.cli
"""

from __future__ import annotations

import asyncio
import logging

from polygon_bot.config import settings
from polygon_bot.router import route_input

logger = logging.getLogger(__name__)


async def main_loop() -> None:
    """Interactive REPL that routes queries through the bot's router."""
    print(f"Polygon Ops Bot CLI (backend: {settings.llm_backend})")
    print("Commands: /health, /gas-usage [N], /help")
    print("Or ask a natural language question. Type 'quit' to exit.\n")

    if settings.llm_backend == "ollama":
        print(
            "NOTE: Ollama does not support tool-calling. Natural language queries\n"
            "will get a text response without live Datadog/Incident.io/RPC data.\n"
            "Slash commands (/health, /gas-usage) work normally.\n"
        )

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not message:
            continue
        if message.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        try:
            result = await asyncio.wait_for(
                route_input(message=message, user_id="cli-user"),
                timeout=settings.request_timeout_seconds,
            )
        except asyncio.TimeoutError:
            print("\n[timeout] Request timed out.\n")
            continue

        route = result.get("route", "?")
        source = result.get("source", "?")
        print(f"\n[route: {route} | source: {source}]")
        print(result["reply"])
        print()


def main() -> None:
    logging.basicConfig(level=settings.log_level.upper())
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
