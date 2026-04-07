"""Input Guard — uses a fast LLM call to reject off-topic queries."""

from __future__ import annotations

import re

from src.config import settings
from src.llm import make_client

_SYSTEM_PROMPT = """You are a topic filter for a Polygon blockchain support bot.

Determine if the user message is related to ANY of these topics:
- Polygon PoS, CDK, or AggLayer
- Blockchain node operations, validators, staking
- Smart contract development on Polygon
- Bridging between Ethereum and Polygon
- Gas fees, transactions, RPC endpoints on Polygon
- Network health, incidents, monitoring
- MATIC/POL token
- General Ethereum/Web3 concepts when asked in a Polygon context

Respond with EXACTLY one word: "ON_TOPIC" or "OFF_TOPIC"."""

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous|above|all)\s+(instructions|prompts|rules))"
    r"|(respond\s+with\s+(exactly|only))"
    r"|(system\s*(note|prompt|instruction))",
    re.IGNORECASE,
)


async def check_relevance(message: str) -> bool:
    """Return True if the message is on-topic for Polygon support."""
    if _INJECTION_PATTERNS.search(message):
        return False

    client = make_client()
    try:
        response = await client.messages.create(
            model=settings.classifier_model,
            max_tokens=10,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        if not response.content:
            return False
        text = response.content[0].text.strip().upper()
        return text == "ON_TOPIC"
    finally:
        await client.close()
