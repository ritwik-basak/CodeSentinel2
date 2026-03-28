"""
vector_store.py — Pinecone storage and retrieval for code chunk embeddings.

Public functions
----------------
upsert_chunks(chunks)              — store embedder output in Pinecone
search(query_text, top_k, filter)  — semantic search over stored chunks
clear_index()                      — wipe all vectors (useful for test runs)
"""

from __future__ import annotations

import os
import time
import math
from typing import Any

from pinecone import Pinecone, ServerlessSpec

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INDEX_NAME = "code-review-index"
DIMENSION  = 384
METRIC     = "cosine"
BATCH_SIZE = 50

# Pinecone Serverless — change cloud/region to match your project's settings
_CLOUD  = "aws"
_REGION = "us-east-1"

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_pc:    Pinecone | None = None
_index: Any | None      = None


def _get_index():
    """Return a ready Pinecone Index, creating it if it doesn't exist yet."""
    global _pc, _index
    if _index is not None:
        return _index

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "PINECONE_API_KEY is not set. Add it to your .env file."
        )

    _pc = Pinecone(api_key=api_key)

    existing_names = {idx.name for idx in _pc.list_indexes()}
    if INDEX_NAME not in existing_names:
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        _pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric=METRIC,
            spec=ServerlessSpec(cloud=_CLOUD, region=_REGION),
        )
        _wait_until_ready()

    _index = _pc.Index(INDEX_NAME)
    return _index


def _wait_until_ready(timeout: int = 120) -> None:
    """Poll until the index reports ready, or raise after ``timeout`` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status = _pc.describe_index(INDEX_NAME).status
            if status.get("ready", False):
                return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError(
        f"Pinecone index '{INDEX_NAME}' was not ready within {timeout}s."
    )


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------

def upsert_chunks(chunks: list[dict[str, Any]]) -> None:
    """
    Upsert all embedded chunks into Pinecone.

    Each chunk's embedding becomes the vector; all other non-None scalar
    fields are stored as metadata.

    Parameters
    ----------
    chunks : list of dicts as returned by ``core.embedder.embed_chunks``
    """
    index = _get_index()

    vectors = []
    for chunk in chunks:
        if chunk.get("embedding") is None:
            continue

        metadata = {
            k: v for k, v in {
                "text":          chunk["text"],
                "filename":      chunk["filename"],
                "chunk_type":    chunk["chunk_type"],
                "language":      chunk["language"],
                "function_name": chunk.get("function_name"),
                "class_name":    chunk.get("class_name"),
                "line":          chunk.get("line"),
                "has_doc":       chunk.get("has_doc"),
            }.items()
            if v is not None  # Pinecone metadata must not contain None
        }

        vectors.append({
            "id":       chunk["chunk_id"],
            "values":   chunk["embedding"],
            "metadata": metadata,
        })

    if not vectors:
        print("No vectors to upsert.")
        return

    num_batches = math.ceil(len(vectors) / BATCH_SIZE)
    for i in range(num_batches):
        batch = vectors[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        print(f"Upserting batch {i + 1}/{num_batches}...")
        index.upsert(vectors=batch)

    print(f"✅ Upserted {len(vectors)} chunks to Pinecone")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def search(
    query_text: str,
    top_k: int = 10,
    filter: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Embed ``query_text`` with the BGE model and return the top-k most
    semantically similar chunks from Pinecone.

    Parameters
    ----------
    query_text : plain-English query, e.g. "functions missing error handling"
    top_k      : number of results to return
    filter     : optional Pinecone metadata filter, e.g.
                 ``{"chunk_type": "function"}`` or ``{"language": "python"}``

    Returns
    -------
    List of dicts with keys:
        chunk_id, score, text, filename, function_name, line, chunk_type
    """
    from core.embedder import _get_model

    model = _get_model()
    query_vector = model.encode([query_text])[0].tolist()

    index  = _get_index()
    kwargs = dict(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )
    if filter:
        kwargs["filter"] = filter

    response = index.query(**kwargs)

    results = []
    for match in response.matches:
        meta = match.metadata or {}
        results.append({
            "chunk_id":      match.id,
            "score":         round(match.score, 4),
            "text":          meta.get("text", ""),
            "filename":      meta.get("filename", ""),
            "function_name": meta.get("function_name"),
            "class_name":    meta.get("class_name"),
            "line":          meta.get("line"),
            "chunk_type":    meta.get("chunk_type", ""),
            "language":      meta.get("language", ""),
        })

    return results


# ---------------------------------------------------------------------------
# clear_index
# ---------------------------------------------------------------------------

def clear_index() -> None:
    """Delete all vectors from the index (non-destructive to the index itself)."""
    index = _get_index()
    index.delete(delete_all=True)
    print(f"🗑️  All vectors deleted from '{INDEX_NAME}'")
