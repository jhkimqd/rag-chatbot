"""Tests for the standalone RPC client."""

import pytest

from polygon_mcp.rpc import get_chain_status, get_recent_blocks


@pytest.mark.asyncio
async def test_get_chain_status_bad_url():
    """Should return None when RPC endpoint is unreachable."""
    result = await get_chain_status(rpc_url="http://localhost:1")
    assert result is None


@pytest.mark.asyncio
async def test_get_recent_blocks_bad_url():
    """Should return empty list when RPC endpoint is unreachable."""
    result = await get_recent_blocks(count=1, rpc_url="http://localhost:1")
    assert result == []
