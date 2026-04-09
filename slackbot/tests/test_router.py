"""Tests for the router (command dispatch + ops routing)."""

from unittest.mock import AsyncMock, patch

import pytest

from polygon_bot.router import ParsedCommand, try_parse_command

# --- Regex Dispatcher Tests ---

def test_valid_command_no_args():
    result = try_parse_command("/health")
    assert result == ParsedCommand(name="health", raw_args="")


def test_valid_command_with_args():
    result = try_parse_command("/gas-usage 20")
    assert result == ParsedCommand(name="gas-usage", raw_args="20")


def test_command_with_whitespace():
    result = try_parse_command("  /health  ")
    assert result == ParsedCommand(name="health", raw_args="")


def test_non_command_returns_none():
    assert try_parse_command("How do I deploy on Polygon?") is None


def test_empty_string_returns_none():
    assert try_parse_command("") is None


def test_slash_only_returns_none():
    assert try_parse_command("/") is None


def test_command_name_normalized_lowercase():
    result = try_parse_command("/GAS-USAGE")
    assert result is not None
    assert result.name == "gas-usage"


# --- Route Input Tests ---

@pytest.mark.asyncio
async def test_slash_command_routes_to_registry():
    with patch("polygon_bot.router.execute_command", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"reply": "Health OK", "source": "command"}

        from polygon_bot.router import route_input

        result = await route_input("/health")
        assert result["route"] == "command"
        assert "Health OK" in result["reply"]


@pytest.mark.asyncio
async def test_unknown_command_returns_error():
    from polygon_bot.router import route_input

    result = await route_input("/nonexistent-cmd")
    assert result["route"] == "command"
    assert "Unknown command" in result["reply"]


@pytest.mark.asyncio
async def test_natural_language_routes_to_ops():
    with patch("polygon_bot.router.run_ops_agent", new_callable=AsyncMock) as mock_ops:
        mock_ops.return_value = {"answer": "Network healthy", "sources": ["polygon-rpc"]}

        from polygon_bot.router import route_input

        result = await route_input("Is the network down?")
        assert result["route"] == "ops"
        mock_ops.assert_called_once()
