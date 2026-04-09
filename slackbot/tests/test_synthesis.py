"""Tests for response synthesis."""

from polygon_bot.synthesis.response import format_response


def test_format_with_sources():
    result = {"answer": "Gas is low.", "sources": ["polygon-rpc"]}
    resp = format_response(result, route="ops")
    assert resp["route"] == "ops"
    assert resp["source"] == "polygon-rpc"
    assert "polygon-rpc" in resp["reply"]


def test_format_with_inline_citation():
    result = {
        "answer": "Gas is low. [source: polygon-rpc]",
        "sources": ["polygon-rpc"],
    }
    resp = format_response(result, route="ops")
    assert resp["reply"].count("polygon-rpc") == 1


def test_format_no_sources():
    result = {"answer": "Hello.", "sources": []}
    resp = format_response(result, route="command")
    assert resp["source"] == "system"
    assert "Sources:" not in resp["reply"]


def test_format_mixed_sources():
    result = {
        "answer": "Data from RPC. [source: polygon-rpc]",
        "sources": ["polygon-rpc", "datadog"],
    }
    resp = format_response(result, route="ops")
    assert "datadog" in resp["reply"]
    assert resp["source"] == "polygon-rpc, datadog"
