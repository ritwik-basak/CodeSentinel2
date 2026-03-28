"""
reranker.py — Cross-encoder reranking for retrieved code chunks.

Uses ``cross-encoder/ms-marco-MiniLM-L-6-v2`` to score (query, chunk-text)
pairs and re-sort the candidate list by true relevance before agent analysis.

Model downloads automatically on first use (~25 MB).
"""

from __future__ import annotations

from typing import Any

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

def _get_model():
    global _model
    if _model is None:
        print("Loading reranker model...")
        from sentence_transformers.cross_encoder import CrossEncoder
        _model = CrossEncoder(_MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rerank(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Score each chunk against ``query`` with a cross-encoder and return the
    list sorted by relevance (highest score first).

    Parameters
    ----------
    query  : the search intent, e.g. the agent focus area
    chunks : list of chunk dicts — must each have a ``"text"`` field

    Returns
    -------
    Same dicts as input, sorted by descending cross-encoder score.
    Each dict gets a ``"rerank_score"`` field added.
    """
    if not chunks:
        return []

    model = _get_model()
    pairs  = [[query, chunk["text"]] for chunk in chunks]
    scores = model.predict(pairs)

    ranked = sorted(
        zip(scores, chunks),
        key=lambda x: x[0],
        reverse=True,
    )

    result = []
    for score, chunk in ranked:
        chunk = dict(chunk)          # shallow copy — don't mutate caller's dicts
        chunk["rerank_score"] = float(score)
        result.append(chunk)

    return result
