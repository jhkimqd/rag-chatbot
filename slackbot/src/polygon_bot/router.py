"""Router — dispatches Slack messages to commands or the ops agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from polygon_bot.commands.registry import execute_command, has_command
from polygon_bot.ops.agent import run_ops_agent
from polygon_bot.synthesis.response import format_response

logger = logging.getLogger(__name__)

# --- Regex Dispatcher ---

_COMMAND_PATTERN = re.compile(
    r"^/(?P<command>[a-z][a-z0-9_-]*)(?:\s+(?P<args>.+))?$", re.IGNORECASE
)


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    raw_args: str


def try_parse_command(message: str) -> ParsedCommand | None:
    """Return a ParsedCommand if the message is a slash command, else None."""
    message = message.strip()
    match = _COMMAND_PATTERN.match(message)
    if not match:
        return None
    return ParsedCommand(
        name=match.group("command").lower(),
        raw_args=(match.group("args") or "").strip(),
    )


# --- Main Router ---

async def route_input(
    message: str,
    user_id: str = "anonymous",
) -> dict:
    """Route user input: slash commands first, then ops agent for everything else."""

    # Layer 0: Slash commands (deterministic, no LLM)
    parsed = try_parse_command(message)
    if parsed is not None:
        if has_command(parsed.name):
            result = await execute_command(parsed.name, parsed.raw_args)
            return {
                "reply": result["reply"],
                "source": result.get("source", "command"),
                "route": "command",
                "metadata": result.get("metadata"),
            }
        return {
            "reply": f"Unknown command `/{parsed.name}`. Type `/help` for available commands.",
            "source": "system",
            "route": "command",
        }

    # Everything else goes to the ops agent
    ops_result = await run_ops_agent(message)
    return format_response(ops_result, route="ops")
