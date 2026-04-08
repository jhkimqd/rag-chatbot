"""Protocol Switch — the top-level router that dispatches to commands, RAG, or ops."""

from __future__ import annotations

import logging

from src.commands.registry import execute_command, has_command
from src.guard.input_guard import check_relevance
from src.guard.output_guard import check_output
from src.ops.agent import run_ops_agent
from src.rag.pipeline import run_rag_pipeline
from src.router.intent_manager import Intent, classify_intent
from src.router.regex_dispatcher import try_parse_command
from src.synthesis.response import format_response

logger = logging.getLogger(__name__)

_OFF_TOPIC_REPLY = (
    "I'm the Polygon support bot — I can help with Polygon PoS, CDK, AggLayer, "
    "node operations, smart contracts, bridging, gas fees, and network health. "
    "Could you rephrase your question in one of those areas?"
)


async def route_input(
    message: str,
    user_id: str = "anonymous",
) -> dict:
    """Route user input through the Protocol Switch and return a response dict."""

    # --- Layer 0: Regex Dispatcher (deterministic commands) ---
    parsed = try_parse_command(message)
    if parsed is not None:
        if has_command(parsed.name):
            result = await execute_command(parsed.name, parsed.raw_args)
            return {
                "reply": result["reply"],
                "source": result.get("source", "command"),
                "route": "command",
                "metadata": result.get("metadata"),
            }
        return {
            "reply": f"Unknown command `/{parsed.name}`. Type `/help` for available commands.",
            "source": "system",
            "route": "command",
        }

    # --- Input Guard: topic relevance check ---
    on_topic = await check_relevance(message)
    if not on_topic:
        return {
            "reply": _OFF_TOPIC_REPLY,
            "source": "system",
            "route": "rejected",
        }

    # --- Layer 1: Intent classification ---
    intent = await classify_intent(message)
    logger.info("Classified intent=%s for user=%s", intent.value, user_id)

    if intent == Intent.DOCS:
        rag_result = await run_rag_pipeline(message)
        response = format_response(rag_result, route="rag")
        return await _apply_output_guard(response, message)

    if intent == Intent.OPS:
        ops_result = await run_ops_agent(message)
        response = format_response(ops_result, route="ops")
        return await _apply_output_guard(response, message)

    # HYBRID: run both and merge
    rag_result = await run_rag_pipeline(message)
    ops_result = await run_ops_agent(message)
    merged_reply = (
        f"{rag_result['answer']}\n\n"
        f"---\n**Live Data:**\n{ops_result['answer']}"
    )
    sources = list({*rag_result.get("sources", []), *ops_result.get("sources", [])})
    response = format_response(
        {"answer": merged_reply, "sources": sources},
        route="hybrid",
    )
    return await _apply_output_guard(response, message)


async def _apply_output_guard(response: dict, original_query: str) -> dict:
    """Run the output guard and replace the response if it fails."""
    replacement = await check_output(response["reply"], original_query)
    if replacement is not None:
        return {
            "reply": replacement,
            "source": "system",
            "route": "rejected",
        }
    return response
