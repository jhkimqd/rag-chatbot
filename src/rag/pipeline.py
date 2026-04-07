"""RAG Pipeline — retrieves relevant docs and generates a grounded answer."""

from __future__ import annotations

import logging

from src.config import settings
from src.llm import make_client
from src.rag.retriever import retrieve

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a Polygon blockchain technical support assistant.

Answer the user's question using ONLY the context provided in their message.
If the context does not contain enough information, say so clearly rather than guessing.

Rules:
- Be precise and technical.
- Include code snippets when relevant.
- Cite your sources using [source: <name>] tags at the end of relevant statements.
- If multiple sources agree, cite the most specific one.
- Format responses in Markdown."""


async def run_rag_pipeline(query: str) -> dict:
    """Retrieve relevant docs and generate a grounded answer."""
    chunks = await retrieve(query)

    if not chunks:
        return {
            "answer": (
                "I couldn't find relevant documentation for your question. "
                "Try rephrasing, or check the official Polygon docs at "
                "https://docs.polygon.technology"
            ),
            "sources": [],
        }

    context_block = "\n\n---\n\n".join(
        f"[Source: {c.source}]\n{c.text}" for c in chunks
    )

    client = make_client()
    try:
        response = await client.messages.create(
            model=settings.reasoning_model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"<context>\n{context_block}\n</context>\n\n"
                        f"<question>\n{query}\n</question>"
                    ),
                }
            ],
        )
    finally:
        await client.close()

    if not response.content:
        return {"answer": "No response generated.", "sources": []}

    answer = response.content[0].text
    sources = list({c.source for c in chunks})

    return {"answer": answer, "sources": sources}
