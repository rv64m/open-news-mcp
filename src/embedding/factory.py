from __future__ import annotations

from src.config import settings

from .base import EmbeddingProvider
from .providers.local import LocalSentenceTransformerEmbeddingProvider
from .providers.remote import GoogleEmbeddingProvider, OpenAIEmbeddingProvider, OpenRouterEmbeddingProvider


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider

    if _provider is not None:
        return _provider

    backend = settings.embedding_backend
    if not backend:
        raise RuntimeError("Embedding is not configured. Set NEWS_EMBEDDING_BACKEND first.")
    if backend == "local":
        _provider = LocalSentenceTransformerEmbeddingProvider(
            model_name=settings.embedding_model,
            device=settings.embedding_device,
            normalize=settings.embedding_normalize,
            batch_size=settings.embedding_batch_size,
            trust_remote_code=settings.embedding_trust_remote_code,
        )
        return _provider
    if backend == "openai":
        _provider = OpenAIEmbeddingProvider()
        return _provider
    if backend == "google":
        _provider = GoogleEmbeddingProvider()
        return _provider
    if backend == "openrouter":
        _provider = OpenRouterEmbeddingProvider()
        return _provider

    raise RuntimeError(f"Unsupported embedding backend: {backend}")
