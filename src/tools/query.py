import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..embedding import build_news_embedding_text, get_embedding_provider
from ..store import fetch_news_by_ids
from ..vector import get_vector_store
from ..vector.base import VectorSearchResult
from .search import _article_to_payload, _error_result


MAX_LIMIT = 50
OVERFETCH_MULTIPLIER = 5
MAX_VECTOR_FETCH = 200
MAX_GRAPH_EDGES = 100
MIN_RELATED_EDGE_SCORE = 0.70


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


def _parse_published_after(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_timespan(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip().lower()
    if len(raw) < 2 or not raw[:-1].isdigit():
        raise ValueError("timespan must look like '72h', '7d', or '30m'.")
    amount = int(raw[:-1])
    unit = raw[-1]
    now = datetime.now(timezone.utc)
    if unit == "m":
        return now - timedelta(minutes=amount)
    if unit == "h":
        return now - timedelta(hours=amount)
    if unit == "d":
        return now - timedelta(days=amount)
    raise ValueError("timespan must use suffix m, h, or d.")


def _normalize_string_list(value: Any, *, field_name: str) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[\s,]+", value.strip()) if part.strip()]
        return parts or None
    if isinstance(value, (list, tuple, set)):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or None
    raise ValueError(f"{field_name} must be a string or a list of strings.")


def _normalize_int_list(value: Any, *, field_name: str) -> list[int] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[\s,]+", value.strip()) if part.strip()]
        if not parts:
            return None
        try:
            return [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError(f"{field_name} must contain integers.") from exc
    if isinstance(value, (list, tuple, set)):
        try:
            normalized = [int(item) for item in value]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must contain integers.") from exc
        return normalized or None
    raise ValueError(f"{field_name} must be a string or a list of integers.")


def _article_matches_filters(
    article: Any,
    *,
    cutoff: datetime | None,
    categories: set[str] | None,
    sources: set[str] | None,
    tiers: set[int] | None,
    language: str | None,
) -> bool:
    if cutoff:
        if article.published_at is None:
            return False
        published_at = article.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        else:
            published_at = published_at.astimezone(timezone.utc)
        if published_at < cutoff:
            return False
    if categories and article.source_category not in categories:
        return False
    if sources and article.source_name not in sources:
        return False
    if tiers and article.source_tier not in tiers:
        return False
    if language and article.article_language != language and article.source_lang != language:
        return False
    return True


def _query_hit_to_score(hit: VectorSearchResult) -> float:
    return float(hit.score)


def _build_embedding_payload(article: Any) -> dict[str, object]:
    return {
        "name": article.source_name,
        "url": article.url,
        "category": article.source_category,
        "tags": list(article.tags or []),
        "lang": article.source_lang,
        "tier": article.source_tier,
        "title": article.title,
        "domain": article.domain,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "language": article.article_language,
    }


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _build_graph(
    query: str,
    articles: list[Any],
    score_by_id: dict[int, float],
    article_vectors: list[list[float]],
) -> dict[str, Any]:
    nodes = [
        {
            "id": "query",
            "kind": "query",
            "label": query,
            "query": query,
        }
    ]
    edges: list[dict[str, Any]] = []

    for article in articles:
        payload = _article_to_payload(article)
        payload["id"] = article.id
        payload["node_id"] = f"article:{article.id}"
        payload["kind"] = "article"
        payload["query_score"] = score_by_id[article.id]
        nodes.append(payload)
        edges.append(
            {
                "source": "query",
                "target": f"article:{article.id}",
                "kind": "query_match",
                "score": score_by_id[article.id],
            }
        )

    related_edges: list[dict[str, Any]] = []
    for index, article in enumerate(articles):
        for other_index in range(index + 1, len(articles)):
            other_article = articles[other_index]
            similarity = _cosine_similarity(article_vectors[index], article_vectors[other_index])
            if similarity < MIN_RELATED_EDGE_SCORE:
                continue
            related_edges.append(
                {
                    "source": f"article:{article.id}",
                    "target": f"article:{other_article.id}",
                    "kind": "related",
                    "score": similarity,
                }
            )

    related_edges.sort(key=lambda edge: edge["score"], reverse=True)
    edges.extend(related_edges[:MAX_GRAPH_EDGES])
    return {"nodes": nodes, "edges": edges}


async def query_related_news_graph(
    query: str,
    limit: int = 10,
    published_after: str | None = None,
    timespan: str | None = None,
    categories: Any | None = None,
    sources: Any | None = None,
    tiers: Any | None = None,
    language: str | None = None,
) -> str:
    """
    Search semantically related news from the vector store and return a related-news graph.
    """
    normalized_query = query.strip()
    if not normalized_query:
        return _error_result("INVALID_ARGUMENT", "query is required.")

    try:
        normalized_limit = _normalize_limit(limit)
        published_cutoff = _parse_published_after(published_after)
        timespan_cutoff = _parse_timespan(timespan)
        cutoff = published_cutoff or timespan_cutoff
        if published_cutoff and timespan_cutoff:
            cutoff = max(published_cutoff, timespan_cutoff)

        normalized_categories = _normalize_string_list(categories, field_name="categories")
        normalized_sources = _normalize_string_list(sources, field_name="sources")
        normalized_tiers = _normalize_int_list(tiers, field_name="tiers")

        categories_set = set(normalized_categories or []) or None
        sources_set = set(normalized_sources or []) or None
        tiers_set = set(normalized_tiers or []) or None

        embedding_provider = get_embedding_provider()
        vector_store = get_vector_store()
        vector = embedding_provider.embed_text(normalized_query)

        vector_limit = min(MAX_VECTOR_FETCH, max(normalized_limit, normalized_limit * OVERFETCH_MULTIPLIER))
        hits = vector_store.search(
            collection_name=settings.vector_collection,
            vector=vector,
            limit=vector_limit,
        )
        if not hits:
            return json.dumps({"ok": True, "count": 0, "articles": []}, indent=2)

        article_ids: list[int] = []
        score_by_id: dict[int, float] = {}
        for hit in hits:
            article_id = hit.payload.get("article_id")
            if not isinstance(article_id, int):
                continue
            if article_id in score_by_id:
                continue
            article_ids.append(article_id)
            score_by_id[article_id] = _query_hit_to_score(hit)

        if not article_ids:
            return json.dumps({"ok": True, "count": 0, "articles": []}, indent=2)

        records = await fetch_news_by_ids(article_ids)
        records_by_id = {int(record.id): record for record in records}

        matched_articles: list[Any] = []
        for article_id in article_ids:
            article = records_by_id.get(article_id)
            if article is None:
                continue
            if not _article_matches_filters(
                article,
                cutoff=cutoff,
                categories=categories_set,
                sources=sources_set,
                tiers=tiers_set,
                language=language,
            ):
                continue

            matched_articles.append(article)
            if len(matched_articles) >= normalized_limit:
                break

        if not matched_articles:
            return json.dumps({"ok": True, "count": 0, "graph": {"nodes": [], "edges": []}}, indent=2)

        article_texts = [build_news_embedding_text(_build_embedding_payload(article)) for article in matched_articles]
        article_vectors = embedding_provider.embed_texts(article_texts)
        graph = _build_graph(normalized_query, matched_articles, score_by_id, article_vectors)
    except ValueError as exc:
        return _error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return _error_result(
            "QUERY_RELATED_NEWS_GRAPH_FAILED",
            "Error querying related-news graph from the vector store.",
            {"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(matched_articles),
            "graph": graph,
        },
        indent=2,
    )
