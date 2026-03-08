from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


EmbeddingVector = list[float]


@dataclass(slots=True, frozen=True)
class EmbeddingMetadata:
    backend: str
    model: str
    dimension: int | None = None


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> EmbeddingMetadata:
        raise NotImplementedError

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        raise NotImplementedError

    def embed_text(self, text: str) -> EmbeddingVector:
        return self.embed_texts([text])[0]
