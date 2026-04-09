"""/gas-usage command — fetches recent blocks and computes gas utilization."""

from __future__ import annotations

from polygon_bot.commands.registry import register
from polygon_bot.integrations.polygon_rpc import get_recent_blocks


@register("gas-usage")
async def gas_usage(raw_args: str) -> dict:
    """Compute gas utilization for recent Polygon PoS blocks."""
    block_count = 10
    if raw_args:
        try:
            block_count = int(raw_args.split()[0])
            block_count = min(max(block_count, 1), 100)
        except ValueError:
            return {
                "reply": "Usage: `/gas-usage [block_count]` — "
                "block_count must be a number (1-100).",
                "source": "command",
            }

    blocks = await get_recent_blocks(count=block_count)
    if not blocks:
        return {
            "reply": "Could not fetch block data from Polygon RPC. Try again later.",
            "source": "command",
        }

    rows: list[str] = []
    total_used = 0
    total_limit = 0
    for b in blocks:
        gas_used = b["gas_used"]
        gas_limit = b["gas_limit"]
        pct = (gas_used / gas_limit * 100) if gas_limit else 0
        total_used += gas_used
        total_limit += gas_limit
        rows.append(f"| {b['number']} | {gas_used:,} | {gas_limit:,} | {pct:.1f}% |")

    avg_pct = (total_used / total_limit * 100) if total_limit else 0

    table = (
        "| Block | Gas Used | Gas Limit | Utilization |\n"
        "|-------|----------|-----------|-------------|\n"
        + "\n".join(rows)
    )

    reply = (
        f"**Gas Utilization — Last {len(blocks)} Blocks**\n\n"
        f"{table}\n\n"
        f"**Average utilization: {avg_pct:.1f}%**\n\n"
        f"[source: polygon-rpc]"
    )

    return {
        "reply": reply,
        "source": "polygon-rpc",
        "metadata": {
            "block_count": len(blocks),
            "avg_utilization_pct": round(avg_pct, 2),
        },
    }
