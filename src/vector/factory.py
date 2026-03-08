from __future__ import annotations

from src.config import settings

from .base import VectorStore
from .providers.qdrant import QdrantVectorStore


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store

    if _store is not None:
        return _store

    if not settings.vector_backend:
        raise RuntimeError("Vector store is not configured. Set NEWS_VECTOR_BACKEND first.")
    if settings.vector_backend == "qdrant":
        _store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            path=settings.qdrant_path,
            timeout=settings.qdrant_timeout,
            prefer_grpc=settings.qdrant_prefer_grpc,
        )
        return _store

    raise RuntimeError(f"Unsupported vector backend: {settings.vector_backend}")
