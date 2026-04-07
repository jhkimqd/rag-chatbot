"""Tests for the Protocol Switch routing logic."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_slash_command_routes_to_registry():
    with patch("src.router.protocol_switch.execute_command", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"reply": "Health OK", "source": "command"}

        from src.router.protocol_switch import route_input

        result = await route_input("/health")
        assert result["route"] == "command"
        assert "Health OK" in result["reply"]


@pytest.mark.asyncio
async def test_unknown_command_returns_error():
    from src.router.protocol_switch import route_input

    result = await route_input("/nonexistent-cmd")
    assert result["route"] == "command"
    assert "Unknown command" in result["reply"]


@pytest.mark.asyncio
async def test_off_topic_rejected():
    with patch("src.router.protocol_switch.check_relevance", new_callable=AsyncMock) as mock_guard:
        mock_guard.return_value = False

        from src.router.protocol_switch import route_input

        result = await route_input("What is the best pizza recipe?")
        assert result["route"] == "rejected"


@pytest.mark.asyncio
async def test_docs_intent_routes_to_rag():
    with (
        patch("src.router.protocol_switch.check_relevance", new_callable=AsyncMock) as mock_guard,
        patch("src.router.protocol_switch.classify_intent", new_callable=AsyncMock) as mock_cls,
        patch("src.router.protocol_switch.run_rag_pipeline", new_callable=AsyncMock) as mock_rag,
    ):
        mock_guard.return_value = True
        from src.router.intent_manager import Intent

        mock_cls.return_value = Intent.DOCS
        mock_rag.return_value = {"answer": "Deploy with Hardhat...", "sources": ["polygon-docs"]}

        from src.router.protocol_switch import route_input

        result = await route_input("How do I deploy on Polygon?")
        assert result["route"] == "rag"
        mock_rag.assert_called_once()


@pytest.mark.asyncio
async def test_ops_intent_routes_to_agent():
    with (
        patch("src.router.protocol_switch.check_relevance", new_callable=AsyncMock) as mock_guard,
        patch("src.router.protocol_switch.classify_intent", new_callable=AsyncMock) as mock_cls,
        patch("src.router.protocol_switch.run_ops_agent", new_callable=AsyncMock) as mock_ops,
    ):
        mock_guard.return_value = True
        from src.router.intent_manager import Intent

        mock_cls.return_value = Intent.OPS
        mock_ops.return_value = {"answer": "Network healthy", "sources": ["polygon-rpc"]}

        from src.router.protocol_switch import route_input

        result = await route_input("Is the network down?")
        assert result["route"] == "ops"
        mock_ops.assert_called_once()


@pytest.mark.asyncio
async def test_hybrid_merges_rag_and_ops():
    with (
        patch("src.router.protocol_switch.check_relevance", new_callable=AsyncMock) as mock_guard,
        patch("src.router.protocol_switch.classify_intent", new_callable=AsyncMock) as mock_cls,
        patch("src.router.protocol_switch.run_rag_pipeline", new_callable=AsyncMock) as mock_rag,
        patch("src.router.protocol_switch.run_ops_agent", new_callable=AsyncMock) as mock_ops,
    ):
        mock_guard.return_value = True
        from src.router.intent_manager import Intent

        mock_cls.return_value = Intent.HYBRID
        mock_rag.return_value = {"answer": "Check the docs.", "sources": ["polygon-docs"]}
        mock_ops.return_value = {"answer": "Metrics normal.", "sources": ["datadog"]}

        from src.router.protocol_switch import route_input

        result = await route_input("Network slow, what are the steps?")
        assert result["route"] == "hybrid"
        assert "Check the docs." in result["reply"]
        assert "Metrics normal." in result["reply"]
