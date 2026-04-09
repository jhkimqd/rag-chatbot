"""/health command — quick network health summary from RPC."""

from __future__ import annotations

from polygon_bot.commands.registry import register
from polygon_bot.integrations.polygon_rpc import get_chain_status


@register("health")
async def health_check(raw_args: str) -> dict:
    """Return a quick network health summary."""
    status = await get_chain_status()
    if not status:
        return {
            "reply": "Could not reach Polygon RPC to check network health.",
            "source": "command",
        }

    syncing_status = "Synced" if not status["syncing"] else "Syncing..."
    peer_info = f"{status['peer_count']} peers" if status["peer_count"] is not None else "N/A"

    reply = (
        "**Polygon PoS Network Health**\n\n"
        f"- **Latest block:** {status['latest_block']:,}\n"
        f"- **Chain ID:** {status['chain_id']}\n"
        f"- **Sync status:** {syncing_status}\n"
        f"- **Peers:** {peer_info}\n"
        f"- **Gas price:** {status['gas_price_gwei']:.2f} Gwei\n\n"
        "[source: polygon-rpc]"
    )

    return {
        "reply": reply,
        "source": "polygon-rpc",
        "metadata": status,
    }
