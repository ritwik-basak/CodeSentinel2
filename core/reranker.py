"""
reranker.py — Reranking for retrieved code chunks.

Sorts chunks by their Pinecone similarity score (descending).
No local model required — keeps deployment lightweight.
"""

from __future__ import annotations

from typing import Any


def rerank(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort chunks by their existing Pinecone similarity score (highest first).

    Parameters
    ----------
    query  : unused, kept for interface compatibility
    chunks : list of chunk dicts — must each have a ``"score"`` field

    Returns
    -------
    Same dicts sorted by descending score, each with a ``"rerank_score"`` field.
    """
    if not chunks:
        return []

    result = []
    for chunk in chunks:
        chunk = dict(chunk)
        chunk["rerank_score"] = chunk.get("score", 0.0)
        result.append(chunk)

    return sorted(result, key=lambda x: x["rerank_score"], reverse=True)
