"""/help command — lists available commands."""

from __future__ import annotations

from polygon_bot.commands.registry import register


@register("help")
async def show_help(raw_args: str) -> dict:
    """Show available slash commands."""
    reply = (
        "**Available Commands**\n\n"
        "| Command | Description |\n"
        "|---------|-------------|\n"
        "| `/gas-usage [count]` | Gas utilization for recent blocks (default 10) |\n"
        "| `/health` | Quick network health summary |\n"
        "| `/help` | Show this message |\n\n"
        "You can also ask me natural-language questions about Polygon network "
        "operations, incidents, and monitoring."
    )
    return {"reply": reply, "source": "system"}
