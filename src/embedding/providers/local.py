from __future__ import annotations

import logging
from typing import Any

from ..base import EmbeddingMetadata, EmbeddingProvider, EmbeddingVector


logger = logging.getLogger("embedding.local")


class LocalSentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        model_name: str,
        device: str | None = None,
        normalize: bool = True,
        batch_size: int = 16,
        trust_remote_code: bool = True,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._normalize = normalize
        self._batch_size = batch_size
        self._trust_remote_code = trust_remote_code
        self._model: Any | None = None

    @property
    def metadata(self) -> EmbeddingMetadata:
        dimension: int | None = None
        if self._model is not None:
            dimension = int(self._model.get_sentence_embedding_dimension())
        return EmbeddingMetadata(backend="local", model=self._model_name, dimension=dimension)

    def _get_model(self):
        if self._model is None:
            logger.info(
                "loading local embedding model: model=%s device=%s trust_remote_code=%s",
                self._model_name,
                self._device or "auto",
                self._trust_remote_code,
            )
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
                trust_remote_code=self._trust_remote_code,
            )
            logger.info(
                "local embedding model ready: model=%s dimension=%s",
                self._model_name,
                self._model.get_sentence_embedding_dimension(),
            )
        return self._model

    def embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        if not texts:
            return []

        model = self._get_model()
        logger.info(
            "encoding texts with local embedding model: model=%s count=%s batch_size=%s normalize=%s",
            self._model_name,
            len(texts),
            self._batch_size,
            self._normalize,
        )
        vectors = model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        logger.info(
            "local embedding encoding finished: model=%s count=%s dimension=%s",
            self._model_name,
            len(texts),
            len(vectors[0]) if len(vectors) > 0 else 0,
        )
        return [vector.tolist() for vector in vectors]
