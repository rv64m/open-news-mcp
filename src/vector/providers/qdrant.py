from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from ..base import VectorPoint, VectorSearchResult, VectorStore


_DISTANCE_MAP = {
    "cosine": Distance.COSINE,
    "dot": Distance.DOT,
    "euclid": Distance.EUCLID,
}


class QdrantVectorStore(VectorStore):
    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        path: str | None = None,
        timeout: float = 10.0,
        prefer_grpc: bool = False,
    ) -> None:
        if path:
            self._client = QdrantClient(path=path, timeout=timeout)
        else:
            self._client = QdrantClient(
                url=url or "http://127.0.0.1:6333",
                api_key=api_key,
                timeout=timeout,
                prefer_grpc=prefer_grpc,
            )

    def ensure_collection(self, *, collection_name: str, vector_size: int, distance: str = "cosine") -> None:
        if distance not in _DISTANCE_MAP:
            raise ValueError(f"Unsupported vector distance: {distance}")

        collections = self._client.get_collections().collections
        if any(collection.name == collection_name for collection in collections):
            return

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=_DISTANCE_MAP[distance]),
        )

    def upsert(self, *, collection_name: str, points: list[VectorPoint]) -> None:
        if not points:
            return

        self._client.upsert(
            collection_name=collection_name,
            wait=True,
            points=[
                PointStruct(
                    id=self._normalize_point_id(point.id),
                    vector=point.vector,
                    payload=point.payload,
                )
                for point in points
            ],
        )

    def search(
        self,
        *,
        collection_name: str,
        vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        query_filter = None
        if filters:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key=key,
                        match=MatchAny(any=[item for item in value])
                        if isinstance(value, (list, tuple, set))
                        else MatchValue(value=value),
                    )
                    for key, value in filters.items()
                ]
            )

        results = self._client.query_points(
            collection_name=collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
        ).points

        return [
            VectorSearchResult(
                id=result.id,
                score=float(result.score or 0.0),
                payload=dict(result.payload or {}),
            )
            for result in results
        ]

    def delete(self, *, collection_name: str, point_ids: list[str | int]) -> None:
        if not point_ids:
            return
        self._client.delete(
            collection_name=collection_name,
            points_selector=[self._normalize_point_id(point_id) for point_id in point_ids],
            wait=True,
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _normalize_point_id(point_id: str | int) -> str | int:
        if isinstance(point_id, int):
            return point_id
        try:
            uuid.UUID(point_id)
            return point_id
        except ValueError:
            return str(uuid.uuid5(uuid.NAMESPACE_URL, point_id))
