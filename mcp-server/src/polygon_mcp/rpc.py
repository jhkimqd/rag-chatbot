"""Standalone Polygon JSON-RPC client — no config dependency."""

from __future__ import annotations

import asyncio

import httpx

DEFAULT_RPC_URL = "https://polygon-rpc.com"


async def _rpc_call(
    method: str,
    params: list | None = None,
    rpc_url: str = DEFAULT_RPC_URL,
) -> dict | None:
    """Make a JSON-RPC call to a Polygon PoS node."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            return None
        return data.get("result")
    except (httpx.HTTPError, ValueError, KeyError):
        return None


async def get_chain_status(rpc_url: str = DEFAULT_RPC_URL) -> dict | None:
    """Get a snapshot of the chain's current state."""
    latest_block, gas_price, syncing, chain_id, peer_count = await asyncio.gather(
        _rpc_call("eth_blockNumber", rpc_url=rpc_url),
        _rpc_call("eth_gasPrice", rpc_url=rpc_url),
        _rpc_call("eth_syncing", rpc_url=rpc_url),
        _rpc_call("eth_chainId", rpc_url=rpc_url),
        _rpc_call("net_peerCount", rpc_url=rpc_url),
    )

    if latest_block is None:
        return None

    # eth_syncing returns False when synced, an object when syncing, None on error
    if syncing is None:
        sync_status = None
    else:
        sync_status = syncing is not False

    return {
        "latest_block": int(latest_block, 16),
        "chain_id": int(chain_id, 16) if chain_id else None,
        "gas_price_gwei": int(gas_price, 16) / 1e9 if gas_price else 0,
        "syncing": sync_status,
        "peer_count": int(peer_count, 16) if peer_count else None,
    }


async def get_recent_blocks(
    count: int = 10,
    rpc_url: str = DEFAULT_RPC_URL,
) -> list[dict]:
    """Fetch the most recent N blocks with gas data (concurrent)."""
    latest = await _rpc_call("eth_blockNumber", rpc_url=rpc_url)
    if latest is None:
        return []

    latest_num = int(latest, 16)

    async def _fetch_block(num: int) -> dict | None:
        data = await _rpc_call("eth_getBlockByNumber", [hex(num), False], rpc_url=rpc_url)
        if not data:
            return None
        return {
            "number": num,
            "gas_used": int(data.get("gasUsed", "0x0"), 16),
            "gas_limit": int(data.get("gasLimit", "0x0"), 16),
            "timestamp": int(data.get("timestamp", "0x0"), 16),
            "tx_count": len(data.get("transactions", [])),
        }

    results = await asyncio.gather(*(_fetch_block(latest_num - i) for i in range(count)))
    return [b for b in results if b is not None]
