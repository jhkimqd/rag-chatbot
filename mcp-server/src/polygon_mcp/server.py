"""MCP server for Polygon blockchain knowledge.

Exposes Polygon documentation as searchable tools and resources so users
can query Polygon knowledge using their own AI (Claude, GPT, etc.).

Usage:
    polygon-mcp                     # stdio transport (default)
    python -m polygon_mcp.server    # same
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from polygon_mcp.docs import build_index, load_docs
from polygon_mcp.rpc import get_chain_status, get_recent_blocks

# Cache loaded docs and index at startup (avoids re-reading filesystem per request)
_docs_cache: list[dict] = load_docs()
_index = build_index()

mcp = FastMCP(
    "polygon-knowledge",
    instructions=(
        "Polygon blockchain knowledge server. Use search_polygon_docs to find "
        "information about Polygon PoS, CDK, AggLayer, smart contracts, bridging, "
        "gas fees, validators, and RPC endpoints. Use get_chain_status and "
        "get_gas_usage for live network data."
    ),
)

_RPC_URL = os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")


@mcp.tool()
def search_polygon_docs(query: str, top_k: int = 5) -> str:
    """Search Polygon documentation for relevant information.

    Use this tool to find answers about Polygon PoS, CDK, AggLayer,
    smart contract deployment, bridging, gas fees, validators, nodes,
    and RPC endpoints.

    Args:
        query: Natural language search query about Polygon.
        top_k: Number of results to return (default 5, max 10).
    """
    top_k = min(max(top_k, 1), 10)
    results = _index.search(query, top_k=top_k)

    if not results:
        return (
            "No relevant documentation found. Try rephrasing your query, "
            "or check the official Polygon docs at https://docs.polygon.technology"
        )

    sections = []
    for i, chunk in enumerate(results, 1):
        sections.append(f"--- Result {i} [source: {chunk.source}] ---\n{chunk.text}")

    return "\n\n".join(sections)


@mcp.tool()
async def get_polygon_chain_status() -> str:
    """Get the current status of the Polygon PoS network.

    Returns the latest block number, chain ID, gas price, sync status,
    and peer count from a public Polygon RPC endpoint.
    """
    status = await get_chain_status(rpc_url=_RPC_URL)
    if not status:
        return "Error: Could not reach Polygon RPC endpoint."

    sync_val = status["syncing"]
    syncing = "Unknown" if sync_val is None else ("Syncing..." if sync_val else "Synced")
    peers = str(status["peer_count"]) if status["peer_count"] is not None else "N/A"

    return (
        f"Polygon PoS Network Status:\n"
        f"- Latest block: {status['latest_block']:,}\n"
        f"- Chain ID: {status['chain_id']}\n"
        f"- Gas price: {status['gas_price_gwei']:.2f} Gwei\n"
        f"- Sync status: {syncing}\n"
        f"- Peers: {peers}"
    )


@mcp.tool()
async def get_gas_usage(block_count: int = 10) -> str:
    """Get gas utilization for recent Polygon PoS blocks.

    Shows gas used vs gas limit for each block and the average utilization.

    Args:
        block_count: Number of recent blocks to analyze (default 10, max 50).
    """
    block_count = min(max(block_count, 1), 50)
    blocks = await get_recent_blocks(count=block_count, rpc_url=_RPC_URL)

    if not blocks:
        return "Could not fetch block data from Polygon RPC."

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

    return f"Gas Utilization — Last {len(blocks)} Blocks\n\n{table}\n\nAverage: {avg_pct:.1f}%"


@mcp.resource("docs://polygon/list")
def list_available_docs() -> str:
    """List all available Polygon documentation topics."""
    if not _docs_cache:
        return "No documentation files found."
    lines = [f"- {doc['source']} ({len(doc['text'])} chars)" for doc in _docs_cache]
    return "Available Polygon documentation:\n" + "\n".join(lines)


@mcp.resource("docs://polygon/{doc_name}")
def get_doc(doc_name: str) -> str:
    """Get the full text of a specific Polygon documentation file."""
    for doc in _docs_cache:
        if doc["source"] == doc_name:
            return doc["text"]
    available = [doc["source"] for doc in _docs_cache]
    return f"Document '{doc_name}' not found. Available: {', '.join(available)}"


def main() -> None:
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
