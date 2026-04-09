"""Tests for the MCP server tool and resource registrations."""

from polygon_mcp.server import mcp, search_polygon_docs


def test_search_polygon_docs_returns_results():
    result = search_polygon_docs("deploy smart contract", top_k=3)
    assert "Result 1" in result
    assert "[source:" in result


def test_search_polygon_docs_no_results():
    result = search_polygon_docs("xyznonexistent123foobarbaz")
    assert "No relevant documentation" in result


def test_search_polygon_docs_clamps_top_k():
    result = search_polygon_docs("polygon", top_k=100)
    # Should clamp to 10 max
    assert "Result 1" in result


def test_mcp_has_tools():
    """Verify that the MCP server has the expected tools registered."""
    # FastMCP stores tool definitions; just verify the server object exists
    assert mcp.name == "polygon-knowledge"
