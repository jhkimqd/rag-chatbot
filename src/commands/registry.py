"""Command Registry — plugin system for deterministic slash commands."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

CommandHandler = Callable[[str], Awaitable[dict]]

_registry: dict[str, CommandHandler] = {}


def register(name: str) -> Callable[[CommandHandler], CommandHandler]:
    """Decorator to register a slash command handler."""

    def decorator(fn: CommandHandler) -> CommandHandler:
        _registry[name] = fn
        logger.debug("Registered command: /%s", name)
        return fn

    return decorator


def has_command(name: str) -> bool:
    _ensure_loaded()
    return name in _registry


async def execute_command(name: str, raw_args: str) -> dict:
    _ensure_loaded()
    handler = _registry[name]
    return await handler(raw_args)


def list_commands() -> list[str]:
    _ensure_loaded()
    return sorted(_registry.keys())


_loaded = False


def _ensure_loaded() -> None:
    """Import command modules to trigger registration."""
    global _loaded  # noqa: PLW0603
    if _loaded:
        return
    import src.commands.gas_usage  # noqa: F401
    import src.commands.health  # noqa: F401
    import src.commands.help  # noqa: F401

    _loaded = True
