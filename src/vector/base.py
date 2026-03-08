from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class VectorPoint:
    id: str | int
    vector: list[float]
    payload: dict[str, Any]


@dataclass(slots=True, frozen=True)
class VectorSearchResult:
    id: str | int
    score: float
    payload: dict[str, Any]


class VectorStore(ABC):
    @abstractmethod
    def ensure_collection(self, *, collection_name: str, vector_size: int, distance: str = "cosine") -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, *, collection_name: str, points: list[VectorPoint]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        *,
        collection_name: str,
        vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, collection_name: str, point_ids: list[str | int]) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None
