#!/usr/bin/env python3
"""Interactive CLI to test the MCP server tools with a local Ollama model.

Simulates what Claude Code / Claude Desktop would do: take a question,
search docs via MCP tools, send context + question to Ollama, print response.

Usage:
    python test_cli.py                          # default: llama3.2
    python test_cli.py --model qwen2.5:7b       # specific model
    OLLAMA_URL=http://host:11434 python test_cli.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx

from polygon_mcp.docs import build_index
from polygon_mcp.rpc import get_chain_status, get_recent_blocks

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
RPC_URL = os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")

SYSTEM_PROMPT = """You are a Polygon blockchain assistant. Answer questions using ONLY \
the context provided. If the context doesn't contain enough info, say so. \
Be precise and technical. Cite sources using [source: name] tags."""

_index = build_index()


async def call_ollama(model: str, system: str, user_msg: str) -> str:
    """Send a chat completion to Ollama."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")


async def handle_query(query: str, model: str) -> None:
    """Process a user query: search docs, optionally get live data, ask Ollama."""
    query_lower = query.lower()

    # Check if the query is about live data
    live_keywords = ["status", "health", "gas price", "block", "syncing", "peers", "gas usage"]
    wants_live_data = any(kw in query_lower for kw in live_keywords)

    # Search docs
    results = _index.search(query, top_k=5)
    context_parts = []

    if results:
        doc_context = "\n\n".join(
            f"[Source: {r.source}]\n{r.text}" for r in results
        )
        context_parts.append(f"Documentation:\n{doc_context}")

    # Get live data if relevant
    if wants_live_data:
        print("  Fetching live chain data...")
        status = await get_chain_status(rpc_url=RPC_URL)
        if status:
            sync_val = status["syncing"]
            syncing = "Unknown" if sync_val is None else ("Syncing" if sync_val else "Synced")
            live = (
                f"Live Chain Status:\n"
                f"- Latest block: {status['latest_block']:,}\n"
                f"- Chain ID: {status['chain_id']}\n"
                f"- Gas price: {status['gas_price_gwei']:.2f} Gwei\n"
                f"- Sync: {syncing}\n"
                f"- Peers: {status['peer_count']}"
            )
            context_parts.append(live)

        if "gas usage" in query_lower or "utilization" in query_lower:
            blocks = await get_recent_blocks(count=5, rpc_url=RPC_URL)
            if blocks:
                rows = []
                for b in blocks:
                    pct = (b["gas_used"] / b["gas_limit"] * 100) if b["gas_limit"] else 0
                    rows.append(f"  Block {b['number']}: {pct:.1f}% utilization")
                context_parts.append("Recent Gas Usage:\n" + "\n".join(rows))

    if not context_parts:
        print("  No relevant context found.\n")
        return

    user_message = (
        f"<context>\n{chr(10).join(context_parts)}\n</context>\n\n"
        f"<question>\n{query}\n</question>"
    )

    print("  Asking Ollama...")
    response = await call_ollama(model, SYSTEM_PROMPT, user_message)
    print(f"\n{response}\n")


async def main_loop(model: str) -> None:
    """Interactive REPL."""
    print(f"Polygon MCP Test CLI (model: {model}, ollama: {OLLAMA_URL})")
    n_sources = len(set(c.source for c in _index.chunks))
    print(f"Indexed {len(_index.chunks)} doc chunks from {n_sources} files")
    print("Type a question, or 'quit' to exit.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        await handle_query(query, model)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MCP tools with Ollama")
    parser.add_argument("--model", default="llama3.2", help="Ollama model name")
    args = parser.parse_args()

    # Quick check that Ollama is reachable
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to Ollama at {OLLAMA_URL}")
        print("Start Ollama with: ollama serve")
        print("Or run: docker compose -f ../slackbot/docker-compose.yml up -d")
        sys.exit(1)

    asyncio.run(main_loop(args.model))


if __name__ == "__main__":
    main()
