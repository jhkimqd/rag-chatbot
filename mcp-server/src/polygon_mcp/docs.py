"""Document loading and keyword search over bundled Polygon markdown docs."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


def _resolve_docs_dir() -> Path:
    """Find docs directory: env var > bundled in package > repo root fallback."""
    env_dir = os.environ.get("POLYGON_DOCS_DIR", "")
    if env_dir:
        return Path(env_dir)

    # Bundled inside the installed package (via pyproject.toml force-include)
    bundled = Path(__file__).resolve().parent / "bundled_docs"
    if bundled.is_dir():
        return bundled

    # Repo checkout: data/docs/ at repo root
    repo_docs = Path(__file__).resolve().parent.parent.parent.parent / "data" / "docs"
    if repo_docs.is_dir():
        return repo_docs

    return bundled  # fall back to bundled path even if missing


_DOCS_DIR = _resolve_docs_dir()

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass
class DocChunk:
    text: str
    source: str
    score: float = 0.0


@dataclass
class DocsIndex:
    """Simple TF-IDF-like index over document chunks — no external dependencies."""

    chunks: list[DocChunk] = field(default_factory=list)
    _idf: dict[str, float] = field(default_factory=dict)
    _tf_cache: list[dict[str, float]] = field(default_factory=list)

    def build(self, chunks: list[DocChunk]) -> None:
        self.chunks = chunks
        n = len(chunks)
        df: dict[str, int] = {}
        self._tf_cache = []

        for chunk in chunks:
            tokens = _tokenize(chunk.text)
            tf: dict[str, float] = {}
            total = len(tokens) or 1
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            for tok in tf:
                tf[tok] /= total
                df[tok] = df.get(tok, 0) + 1
            self._tf_cache.append(tf)

        self._idf = {tok: math.log((n + 1) / (count + 1)) + 1 for tok, count in df.items()}

    def search(self, query: str, top_k: int = 5) -> list[DocChunk]:
        if not self.chunks:
            return []

        query_tokens = set(_tokenize(query))
        scored: list[tuple[float, int]] = []

        for i, tf in enumerate(self._tf_cache):
            score = sum(tf.get(tok, 0) * self._idf.get(tok, 0) for tok in query_tokens)
            if score > 0:
                scored.append((score, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, idx in scored[:top_k]:
            chunk = self.chunks[idx]
            results.append(DocChunk(text=chunk.text, source=chunk.source, score=score))
        return results


def _tokenize(text: str) -> list[str]:
    """Lowercase split on non-alphanumeric, drop short tokens."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1]


def load_docs(docs_dir: Path | None = None) -> list[dict]:
    """Load all .md files from the docs directory."""
    docs_dir = docs_dir or _DOCS_DIR
    documents = []
    for md_file in sorted(docs_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8").strip()
        if text:
            documents.append({"source": md_file.stem, "text": text})
    return documents


def chunk_document(doc: dict) -> list[DocChunk]:
    """Split a document into overlapping chunks respecting section boundaries."""
    text = doc["text"]
    source = doc["source"]
    sections = re.split(r"\n(?=#{1,4}\s)", text)
    chunks: list[DocChunk] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= CHUNK_SIZE:
            chunks.append(DocChunk(text=section, source=source))
            continue

        paragraphs = section.split("\n\n")
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 > CHUNK_SIZE and current:
                chunks.append(DocChunk(text=current.strip(), source=source))
                overlap = current[-CHUNK_OVERLAP:] if len(current) > CHUNK_OVERLAP else current
                current = overlap + "\n\n" + para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            chunks.append(DocChunk(text=current.strip(), source=source))

    return chunks


def build_index(docs_dir: Path | None = None) -> DocsIndex:
    """Load docs, chunk them, and build a searchable index."""
    documents = load_docs(docs_dir)
    all_chunks: list[DocChunk] = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc))

    index = DocsIndex()
    index.build(all_chunks)
    return index
