"""Input Guard — uses a fast LLM call to reject off-topic queries."""

from __future__ import annotations

import re
import unicodedata

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
    r"(ignore\s+(previous|above|all|prior|any)\s+(instructions|prompts|rules|directives|guidelines))"
    r"|(disregard\s+(your|all|any|previous|prior)\s+(rules|instructions|directives|prompts|guidelines))"
    r"|(forget\s+(your|all|any|previous|prior)\s+(rules|instructions|directives|prompts))"
    r"|(respond\s+with\s+(exactly|only))"
    r"|(system\s*(note|prompt|instruction|message))"
    r"|(you\s+are\s+now\s+(a|an|my)\s+)"
    r"|(new\s+(instructions|rules|persona|role)\s*:)"
    r"|(do\s+not\s+follow\s+(your|the|any)\s+(system|original|previous))"
    r"|(override\s+(all\s+)?(previous|prior|system|safety)\s+(instructions|rules|prompts))"
    r"|(act\s+as\s+(if|though)\s+you\s+(are|were|have))"
    r"|(reveal\s+(your|the)\s+(system|original|internal)\s+(prompt|instructions|rules))"
    r"|(what\s+(is|are)\s+your\s+(system|original|initial)\s+(prompt|instructions|rules))"
    r"|(repeat\s+(your|the)\s+(system|original|initial)\s+(prompt|instructions|message))"
    r"|(print\s+(your|the)\s+(system|original|initial)\s+(prompt|instructions))"
    r"|(jailbreak|DAN\s*mode|developer\s*mode|bypass\s*(filter|safety|guard))",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    """Normalize Unicode to catch homoglyph attacks and remove zero-width chars."""
    text = unicodedata.normalize("NFKC", text)
    # Strip zero-width characters used to evade pattern matching
    text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", text)
    return text


async def check_relevance(message: str) -> bool:
    """Return True if the message is on-topic for Polygon support."""
    normalized = _normalize_text(message)
    if _INJECTION_PATTERNS.search(normalized):
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
