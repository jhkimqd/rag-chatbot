"""Layer 1: Intent Manager — classifies natural language into DOCS, OPS, or HYBRID."""

from __future__ import annotations

import logging
from enum import Enum

from src.config import settings
from src.llm import make_client

logger = logging.getLogger(__name__)


class Intent(str, Enum):  # noqa: UP042 — StrEnum needs Python 3.11+
    DOCS = "DOCS"
    OPS = "OPS"
    HYBRID = "HYBRID"


_SYSTEM_PROMPT = """You are an intent classifier for a Polygon blockchain support bot.

Classify the user's message into exactly ONE of these categories:

DOCS — The user is asking a technical "how-to", "what is", or documentation question.
  Examples: "How do I deploy on Polygon?", "What is the chain ID?", "What is Heimdall?"

OPS — The user is asking about current/real-time network health, metrics, or incidents.
  Examples: "Is the network down?", "What is the current gas price?", "Are there active incidents?"

HYBRID — The user needs both documentation AND real-time data to get an answer.
  Examples: "The network is slow, what are the remediation steps?",
  "My node is stuck, what should I check and is there a known issue?"

Respond with EXACTLY one word: DOCS, OPS, or HYBRID."""


async def classify_intent(message: str) -> Intent:
    """Classify a natural-language message into DOCS, OPS, or HYBRID."""
    client = make_client()
    try:
        response = await client.messages.create(
            model=settings.classifier_model,
            max_tokens=10,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        if not response.content:
            logger.warning("Intent classifier returned empty content — defaulting to DOCS")
            return Intent.DOCS
        text = response.content[0].text.strip().upper()
        try:
            return Intent(text)
        except ValueError:
            logger.warning(
                "Intent classifier returned unexpected value: %s — defaulting to DOCS", text
            )
            return Intent.DOCS
    finally:
        await client.close()
