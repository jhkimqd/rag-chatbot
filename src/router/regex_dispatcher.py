"""Layer 0: Regex Dispatcher — detects slash commands and routes to the Command Registry."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches /command-name optionally followed by arguments
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
