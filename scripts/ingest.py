"""Ingest markdown docs from data/docs/ into Qdrant for RAG retrieval."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from pathlib import Path

from qdrant_client import AsyncQdrantClient, models

# Add project root to path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.rag.embeddings import embed_texts

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
CHUNK_SIZE = 800  # characters per chunk (roughly 150-200 tokens)
CHUNK_OVERLAP = 100  # overlap between chunks for context continuity


def load_markdown_files(docs_dir: Path) -> list[dict]:
    """Load all .md files from the docs directory."""
    documents = []
    for md_file in sorted(docs_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8").strip()
        if text:
            documents.append({"source": md_file.stem, "text": text})
            logger.info("Loaded %s (%d chars)", md_file.name, len(text))
    return documents


def chunk_document(doc: dict) -> list[dict]:
    """Split a document into overlapping chunks, respecting section boundaries."""
    text = doc["text"]
    source = doc["source"]

    # Split on markdown headers (##, ###, etc.)
    sections = re.split(r"\n(?=#{1,4}\s)", text)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # If section fits in one chunk, keep it whole
        if len(section) <= CHUNK_SIZE:
            chunks.append({"text": section, "source": source})
            continue

        # Otherwise split into overlapping chunks at paragraph boundaries
        paragraphs = section.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > CHUNK_SIZE and current_chunk:
                chunks.append({"text": current_chunk.strip(), "source": source})
                # Keep overlap from end of previous chunk
                overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else current_chunk
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append({"text": current_chunk.strip(), "source": source})

    return chunks


async def ingest() -> None:
    """Main ingestion pipeline: load docs, chunk, embed, and upsert into Qdrant."""
    # Load documents
    documents = load_markdown_files(DOCS_DIR)
    if not documents:
        logger.error("No markdown files found in %s", DOCS_DIR)
        sys.exit(1)

    logger.info("Loaded %d documents", len(documents))

    # Chunk documents
    all_chunks = []
    for doc in documents:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)

    logger.info("Created %d chunks from %d documents", len(all_chunks), len(documents))

    # Generate embeddings
    logger.info("Generating embeddings with model: %s", settings.embedding_model)
    texts = [c["text"] for c in all_chunks]
    embeddings = await embed_texts(texts)
    vector_size = len(embeddings[0])
    logger.info("Generated %d embeddings (dim=%d)", len(embeddings), vector_size)

    # Connect to Qdrant and create/recreate collection
    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )

    try:
        # Delete existing collection if it exists
        collections = await client.get_collections()
        existing = [c.name for c in collections.collections]
        if settings.qdrant_collection in existing:
            logger.info("Deleting existing collection: %s", settings.qdrant_collection)
            await client.delete_collection(settings.qdrant_collection)

        # Create collection
        logger.info("Creating collection: %s (vector_size=%d)", settings.qdrant_collection, vector_size)
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

        # Upsert points
        points = [
            models.PointStruct(
                id=i,
                vector=embeddings[i],
                payload={"text": all_chunks[i]["text"], "source": all_chunks[i]["source"]},
            )
            for i in range(len(all_chunks))
        ]

        # Upsert in batches of 100
        batch_size = 100
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            await client.upsert(
                collection_name=settings.qdrant_collection,
                points=batch,
            )
            logger.info("Upserted batch %d-%d", start, start + len(batch))

        # Verify
        info = await client.get_collection(settings.qdrant_collection)
        logger.info(
            "Ingestion complete. Collection '%s' has %d points.",
            settings.qdrant_collection,
            info.points_count,
        )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(ingest())
