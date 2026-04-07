"""Embedding generation via sentence-transformers (local, no API key required)."""

from __future__ import annotations

import logging

from src.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the sentence-transformers model on first use."""
    global _model  # noqa: PLW0603
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


async def embed_query(text: str) -> list[float]:
    """Generate a single query embedding."""
    model = _get_model()
    embedding = model.encode([text], normalize_embeddings=True)
    return embedding[0].tolist()
