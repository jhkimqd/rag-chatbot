"""Tests for the document loading and search module."""

from polygon_mcp.docs import DocChunk, DocsIndex, build_index, chunk_document, load_docs


def test_load_docs_finds_markdown():
    docs = load_docs()
    assert len(docs) > 0
    for doc in docs:
        assert "source" in doc
        assert "text" in doc
        assert len(doc["text"]) > 0


def test_chunk_document_small():
    doc = {"source": "test", "text": "Short content."}
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].source == "test"
    assert chunks[0].text == "Short content."


def test_chunk_document_large():
    # Use realistic content with paragraph breaks so chunking can split
    paragraphs = [f"This is paragraph number {i} with enough text to matter." for i in range(40)]
    doc = {"source": "test", "text": "\n\n".join(paragraphs)}
    chunks = chunk_document(doc)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.source == "test"


def test_chunk_document_sections():
    doc = {
        "source": "test",
        "text": "## Section One\nContent one.\n\n## Section Two\nContent two.",
    }
    chunks = chunk_document(doc)
    assert len(chunks) >= 2


def test_index_search():
    index = DocsIndex()
    index.build([
        DocChunk(text="Polygon PoS uses validators to secure the network.", source="pos"),
        DocChunk(text="Smart contracts can be deployed using Hardhat.", source="contracts"),
        DocChunk(text="Gas fees on Polygon are paid in MATIC.", source="gas"),
    ])

    results = index.search("gas fees MATIC", top_k=2)
    assert len(results) > 0
    assert results[0].source == "gas"


def test_index_search_no_results():
    index = DocsIndex()
    index.build([
        DocChunk(text="Polygon uses proof of stake.", source="pos"),
    ])

    results = index.search("xyznonexistent123")
    assert results == []


def test_index_search_empty():
    index = DocsIndex()
    index.build([])
    results = index.search("anything")
    assert results == []


def test_build_index_from_real_docs():
    index = build_index()
    assert len(index.chunks) > 0
    results = index.search("deploy smart contract polygon")
    assert len(results) > 0
