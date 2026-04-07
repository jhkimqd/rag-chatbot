"""Operational tool definitions for the tool-calling agent."""

from __future__ import annotations

import logging
import time

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_DATADOG_PREFIXES = (
    "avg:polygon.", "sum:polygon.", "max:polygon.", "min:polygon.",
    "avg:network.", "sum:network.", "max:network.",
    "avg:rpc.", "sum:rpc.", "max:rpc.",
    "avg:blockchain.", "sum:blockchain.",
)

TOOL_DEFINITIONS = [
    {
        "name": "get_chain_status",
        "description": (
            "Get the current status of the Polygon PoS chain including latest block, "
            "gas price, sync status, and peer count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "query_datadog_metrics",
        "description": (
            "Query Datadog for a specific metric over a time window. "
            "Returns metric values and summary statistics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Datadog metric query (e.g. 'avg:polygon.rpc.latency{*}')",
                },
                "minutes": {
                    "type": "integer",
                    "description": "Lookback window in minutes (default 60)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_active_incidents",
        "description": "Fetch currently active incidents from Incident.io.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_active_monitors",
        "description": "List currently triggered Datadog monitors for Polygon infrastructure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "Filter monitors by tag (e.g. 'service:polygon-rpc')",
                },
            },
            "required": [],
        },
    },
]


async def execute_tool(name: str, inputs: dict) -> str:
    """Execute a tool by name and return its result as a string."""
    if name == "get_chain_status":
        return await _get_chain_status()
    if name == "query_datadog_metrics":
        return await _query_datadog(inputs.get("query", ""), inputs.get("minutes", 60))
    if name == "get_active_incidents":
        return await _get_incidents()
    if name == "get_active_monitors":
        return await _get_monitors(inputs.get("tag"))
    return f"Unknown tool: {name}"


async def _get_chain_status() -> str:
    """Fetch chain status via JSON-RPC."""
    from src.integrations.polygon_rpc import get_chain_status

    status = await get_chain_status()
    if not status:
        return "Error: Could not reach Polygon RPC."
    return (
        f"Latest block: {status['latest_block']}, "
        f"Gas price: {status['gas_price_gwei']:.2f} Gwei, "
        f"Syncing: {status['syncing']}, "
        f"Peers: {status['peer_count']}"
    )


async def _query_datadog(query: str, minutes: int) -> str:
    """Query Datadog metrics API."""
    if not settings.datadog_api_key:
        return "Datadog integration not configured."

    if not any(query.startswith(prefix) for prefix in _ALLOWED_DATADOG_PREFIXES):
        return "Query not permitted. Only Polygon-related metrics are allowed."

    minutes = max(1, min(minutes, 1440))

    now = int(time.time())
    start = now - (minutes * 60)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://api.{settings.datadog_site}/api/v1/query",
                params={"from": start, "to": now, "query": query},
                headers={
                    "DD-API-KEY": settings.datadog_api_key,
                    "DD-APPLICATION-KEY": settings.datadog_app_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Datadog query failed: %s", exc)
        return f"Failed to query Datadog: {type(exc).__name__}"

    series = data.get("series", [])
    if not series:
        return f"No data returned for query: {query}"

    points = series[0].get("pointlist", [])
    if not points:
        return f"Query returned empty series: {query}"

    values = [p[1] for p in points if p[1] is not None]
    if not values:
        return "All data points are null."

    avg = sum(values) / len(values)
    return (
        f"Metric: {query}\n"
        f"Window: last {minutes}m\n"
        f"Points: {len(values)}\n"
        f"Avg: {avg:.4f}, Min: {min(values):.4f}, Max: {max(values):.4f}"
    )


async def _get_incidents() -> str:
    """Fetch active incidents from Incident.io."""
    if not settings.incident_io_api_key:
        return "Incident.io integration not configured."

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.incident.io/v2/incidents",
                params={"status": "live"},
                headers={
                    "Authorization": f"Bearer {settings.incident_io_api_key}"
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Incident.io query failed: %s", exc)
        return f"Failed to fetch incidents: {type(exc).__name__}"

    incidents = data.get("incidents", [])
    if not incidents:
        return "No active incidents."

    lines = []
    for inc in incidents[:10]:
        lines.append(
            f"- [{inc.get('severity', {}).get('name', 'Unknown')}] "
            f"{inc.get('name', 'Unnamed')}: {inc.get('summary', 'No summary')}"
        )
    return f"Active incidents ({len(incidents)}):\n" + "\n".join(lines)


async def _get_monitors(tag: str | None) -> str:
    """Fetch triggered Datadog monitors."""
    if not settings.datadog_api_key:
        return "Datadog integration not configured."

    params: dict = {"monitor_tags": tag} if tag else {}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://api.{settings.datadog_site}/api/v1/monitor",
                params=params,
                headers={
                    "DD-API-KEY": settings.datadog_api_key,
                    "DD-APPLICATION-KEY": settings.datadog_app_key,
                },
            )
            resp.raise_for_status()
            monitors = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Datadog monitors query failed: %s", exc)
        return f"Failed to fetch monitors: {type(exc).__name__}"

    triggered = [m for m in monitors if m.get("overall_state") in ("Alert", "Warn")]
    if not triggered:
        return "No triggered monitors." + (f" (filter: {tag})" if tag else "")

    lines = []
    for m in triggered[:10]:
        lines.append(f"- [{m.get('overall_state')}] {m.get('name', 'Unnamed')}")
    return f"Triggered monitors ({len(triggered)}):\n" + "\n".join(lines)
