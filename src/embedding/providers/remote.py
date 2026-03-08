from __future__ import annotations

from src.config import settings

from ..base import EmbeddingMetadata, EmbeddingProvider, EmbeddingVector


class _NotImplementedRemoteEmbeddingProvider(EmbeddingProvider):
    def __init__(self, *, backend: str, model_name: str) -> None:
        self._metadata = EmbeddingMetadata(backend=backend, model=model_name)

    @property
    def metadata(self) -> EmbeddingMetadata:
        return self._metadata

    def embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        raise NotImplementedError(
            f"Embedding backend '{self._metadata.backend}' is configured but not implemented yet."
        )


class OpenAIEmbeddingProvider(_NotImplementedRemoteEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__(backend="openai", model_name=settings.embedding_model)


class GoogleEmbeddingProvider(_NotImplementedRemoteEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__(backend="google", model_name=settings.embedding_model)


class OpenRouterEmbeddingProvider(_NotImplementedRemoteEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__(backend="openrouter", model_name=settings.embedding_model)
