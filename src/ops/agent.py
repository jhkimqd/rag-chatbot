"""Ops Agent — tool-calling agent for real-time operational queries."""

from __future__ import annotations

import logging

import anthropic

from src.config import settings
from src.ops.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a Polygon network operations assistant.

You have access to tools that query real-time data from the Polygon network,
Datadog monitoring, and Incident.io. Use these tools to answer operational
questions about network health, performance, and incidents.

Rules:
- Always call a tool before answering — do NOT guess at live metrics.
- Summarize tool outputs in clear, actionable language.
- Cite the data source using [source: <name>] tags.
- If a tool fails or returns no data, say so explicitly.
- Format responses in Markdown."""

MAX_TOOL_ROUNDS = 5


async def run_ops_agent(query: str) -> dict:
    """Run the tool-calling agent loop to answer an operational question."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages: list[dict] = [{"role": "user", "content": query}]
    sources: list[str] = []

    try:
        for _round in range(MAX_TOOL_ROUNDS):
            response = await client.messages.create(
                model=settings.reasoning_model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            if not response.content:
                return {"answer": "No response generated.", "sources": sources}

            # Collect text and tool-use blocks
            tool_uses = []
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if response.stop_reason == "end_turn" or not tool_uses:
                answer = "\n".join(text_parts) if text_parts else "No response generated."
                return {"answer": answer, "sources": sources}

            # Execute all tool calls
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                logger.info("Ops agent calling tool: %s", tool_use.name)
                result = await execute_tool(tool_use.name, tool_use.input)
                sources.append(_tool_source(tool_use.name))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
    finally:
        await client.close()

    # Exhausted tool rounds
    return {
        "answer": "I ran out of tool rounds trying to answer this. "
        "Please try a more specific question.",
        "sources": sources,
    }


def _tool_source(tool_name: str) -> str:
    mapping = {
        "get_chain_status": "polygon-rpc",
        "query_datadog_metrics": "datadog",
        "get_active_incidents": "incident.io",
        "get_active_monitors": "datadog",
    }
    return mapping.get(tool_name, tool_name)
