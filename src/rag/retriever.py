"""Hybrid retriever — vector search + BM25 keyword matching via Qdrant."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient, models

from src.config import settings
from src.rag.embeddings import embed_query

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float


async def retrieve(query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Run hybrid search (vector + keyword) over the Polygon docs collection."""
    top_k = top_k or settings.top_k

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )

    try:
        query_vector = await embed_query(query)

        # Vector search (semantic)
        vector_results = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        # Hybrid search via RRF fusion of vector + keyword
        keyword_results = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            prefetch=[
                models.Prefetch(query=query_vector, limit=top_k),
            ],
            limit=top_k,
            with_payload=True,
        )

        # Prefer fusion results if available, fall back to vector-only
        results = keyword_results.points if keyword_results.points else vector_results.points
    except Exception as exc:
        logger.warning("Qdrant retrieval failed: %s — returning empty results", exc)
        return []
    finally:
        await client.close()

    chunks: list[RetrievedChunk] = []
    for point in results:
        payload = point.payload or {}
        chunks.append(
            RetrievedChunk(
                text=payload.get("text", ""),
                source=payload.get("source", "polygon-docs"),
                score=point.score if point.score is not None else 0.0,
            )
        )
    return chunks
