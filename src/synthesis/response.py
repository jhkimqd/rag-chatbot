"""Response synthesis — formats and annotates final bot responses."""

from __future__ import annotations


def format_response(result: dict, route: str) -> dict:
    """Standardize the response dict with citations footer."""
    answer = result.get("answer", "")
    sources = result.get("sources", [])

    # Append citations footer if sources are present and not already cited inline
    if sources:
        cited = [s for s in sources if f"[source: {s}]" in answer]
        uncited = [s for s in sources if s not in cited]
        if uncited:
            footer = "\n\n---\n*Sources: " + ", ".join(f"`{s}`" for s in sources) + "*"
            answer += footer

    return {
        "reply": answer,
        "source": ", ".join(sources) if sources else "system",
        "route": route,
        "metadata": result.get("metadata"),
    }
