"""Search-mode boundary; unchanged BM25 remains the default and safe fallback."""
from __future__ import annotations

import logging
import os

from .rag_embeddings import VectorUnavailable
from .rag_hybrid import rrf
from .rag_retrieval import retrieve as bm25

logger = logging.getLogger(__name__)


def configured_mode() -> str:
    return os.getenv("HAEDAP_RETRIEVAL_MODE", "bm25").lower()


def search(query: str, chunks: list[dict], top_k: int = 5, *, mode: str | None = None,
           vector_index=None) -> dict:
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    requested = mode if mode is not None else configured_mode()
    report = {"requested_mode": requested if requested in {"bm25", "vector", "hybrid"} else "invalid",
              "effective_mode": requested, "fallback_reason": None}
    if requested == "bm25":
        return {**report, "results": bm25(query, chunks, top_k)}
    if not chunks or not query.strip():
        return {**report, "results": []}
    try:
        if requested not in {"vector", "hybrid"}:
            raise VectorUnavailable("invalid_configuration")
        try:
            count = max(top_k, int(os.getenv("HAEDAP_RAG_CANDIDATES", "30")))
            k = int(os.getenv("HAEDAP_RRF_K", "60"))
            if not 1 <= count <= 1000 or k < 1:
                raise ValueError
        except ValueError:
            raise VectorUnavailable("invalid_configuration") from None
        if vector_index is None:
            from .rag_vector import VectorIndex
            vector_index = VectorIndex()
        vectors = vector_index.search(query, chunks, count)
        results = vectors[:top_k] if requested == "vector" else rrf(
            [bm25(query, chunks, count), vectors], top_k=top_k, k=k)
        return {**report, "results": results}
    except Exception as exc:
        # Third-party error messages may contain payloads, paths, credentials.
        reason = str(exc) if isinstance(exc, VectorUnavailable) else "vector_backend_failure"
        logger.warning("rag_fallback requested=%s effective=bm25 reason=%s", report["requested_mode"], reason)
        return {**report, "effective_mode": "bm25", "fallback_reason": reason,
                "results": bm25(query, chunks, top_k)}


def retrieve(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    return search(query, chunks, top_k)["results"]
