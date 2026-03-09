import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..embedding import build_news_embedding_text, get_embedding_provider
from ..store import fetch_news_by_ids, fetch_news_by_urls
from ..vector import get_vector_store
from ..vector.base import VectorSearchResult
from .search import _article_to_payload, _error_result


MAX_LIMIT = 50
OVERFETCH_MULTIPLIER = 5
MAX_VECTOR_FETCH = 200
MAX_GRAPH_EDGES = 100
DEFAULT_RELATED_PER_ARTICLE = 3


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


def _normalize_filters(
    *,
    published_after: str | None,
    timespan: str | None,
    categories: Any | None,
    sources: Any | None,
    tiers: Any | None,
) -> tuple[datetime | None, set[str] | None, set[str] | None, set[int] | None]:
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
    return cutoff, categories_set, sources_set, tiers_set


async def _collect_ranked_articles(
    *,
    hits: list[VectorSearchResult],
    limit: int,
    cutoff: datetime | None,
    categories: set[str] | None,
    sources: set[str] | None,
    tiers: set[int] | None,
    excluded_article_ids: set[int] | None = None,
) -> tuple[list[Any], dict[int, float]]:
    article_ids: list[int] = []
    urls: list[str] = []
    score_by_url: dict[str, float] = {}
    excluded = excluded_article_ids or set()

    for hit in hits:
        url = hit.payload.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        normalized_url = url.strip()
        article_id = hit.payload.get("article_id")
        if normalized_url in score_by_url:
            continue
        if isinstance(article_id, int) and article_id in excluded:
            continue
        urls.append(normalized_url)
        score_by_url[normalized_url] = _query_hit_to_score(hit)
        if isinstance(article_id, int):
            article_ids.append(article_id)

    if not urls:
        return [], {}

    records = await fetch_news_by_urls(urls)
    if not records and article_ids:
        records = await fetch_news_by_ids(article_ids)
    records_by_url = {str(record.url).strip(): record for record in records}

    matched_articles: list[Any] = []
    matched_scores: dict[int, float] = {}
    for url in urls:
        article = records_by_url.get(url)
        if article is None:
            continue
        if not _article_matches_filters(
            article,
            cutoff=cutoff,
            categories=categories,
            sources=sources,
            tiers=tiers,
        ):
            continue

        matched_articles.append(article)
        matched_scores[int(article.id)] = score_by_url[url]
        if len(matched_articles) >= limit:
            break

    return matched_articles, matched_scores


async def _search_ranked_articles(
    *,
    vector_store: Any,
    vector: list[float],
    limit: int,
    cutoff: datetime | None,
    categories: set[str] | None,
    sources: set[str] | None,
    tiers: set[int] | None,
    excluded_article_ids: set[int] | None = None,
) -> tuple[list[Any], dict[int, float]]:
    vector_limit = min(MAX_VECTOR_FETCH, max(limit, limit * OVERFETCH_MULTIPLIER))
    hits = vector_store.search(
        collection_name=settings.vector_collection,
        vector=vector,
        limit=vector_limit,
    )
    return await _collect_ranked_articles(
        hits=hits,
        limit=limit,
        cutoff=cutoff,
        categories=categories,
        sources=sources,
        tiers=tiers,
        excluded_article_ids=excluded_article_ids,
    )


def _build_graph(
    query: str,
    seed_articles: list[Any],
    seed_score_by_id: dict[int, float],
    related_by_seed_id: dict[int, tuple[list[Any], dict[int, float]]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {
            "id": "query",
            "kind": "query",
            "label": query,
            "query": query,
        }
    ]
    edges: list[dict[str, Any]] = []
    node_ids = {"query"}

    def add_article_node(article: Any, *, kind: str, query_score: float | None = None) -> None:
        node_id = f"article:{article.id}"
        if node_id in node_ids:
            return
        payload = _article_to_payload(article)
        payload["id"] = article.id
        payload["node_id"] = node_id
        payload["kind"] = kind
        if query_score is not None:
            payload["query_score"] = query_score
        nodes.append(payload)
        node_ids.add(node_id)

    edge_keys: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, kind: str, score: float) -> None:
        edge_key = (source, target, kind)
        if edge_key in edge_keys:
            return
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": kind,
                "score": score,
            }
        )
        edge_keys.add(edge_key)

    for article in seed_articles:
        add_article_node(article, kind="seed", query_score=seed_score_by_id[article.id])
        add_edge("query", f"article:{article.id}", "query_match", seed_score_by_id[article.id])

        related_articles, related_score_by_id = related_by_seed_id.get(article.id, ([], {}))
        for related_article in related_articles:
            add_article_node(related_article, kind="related")
            add_edge(
                f"article:{article.id}",
                f"article:{related_article.id}",
                "related",
                related_score_by_id[related_article.id],
            )

    edges.sort(key=lambda edge: edge["score"], reverse=True)
    if len(edges) > MAX_GRAPH_EDGES:
        query_edges = [edge for edge in edges if edge["kind"] == "query_match"]
        related_edges = [edge for edge in edges if edge["kind"] == "related"][: max(0, MAX_GRAPH_EDGES - len(query_edges))]
        edges = query_edges + related_edges
    return {"nodes": nodes, "edges": edges}


def _article_to_query_payload(article: Any, *, score: float) -> dict[str, Any]:
    payload = _article_to_payload(article)
    payload["id"] = article.id
    payload["score"] = score
    return payload


async def query_news(
    query: str,
    limit: int = 10,
    published_after: str | None = None,
    timespan: str | None = None,
    categories: Any | None = None,
    sources: Any | None = None,
    tiers: Any | None = None,
) -> str:
    """
    Search semantically related news from the vector store and return the matching articles.
    """
    normalized_query = query.strip()
    if not normalized_query:
        return _error_result("INVALID_ARGUMENT", "query is required.")

    try:
        normalized_limit = _normalize_limit(limit)
        cutoff, categories_set, sources_set, tiers_set = _normalize_filters(
            published_after=published_after,
            timespan=timespan,
            categories=categories,
            sources=sources,
            tiers=tiers,
        )

        embedding_provider = get_embedding_provider()
        vector_store = get_vector_store()
        vector = embedding_provider.embed_text(normalized_query)
        matched_articles, score_by_id = await _search_ranked_articles(
            vector_store=vector_store,
            vector=vector,
            limit=normalized_limit,
            cutoff=cutoff,
            categories=categories_set,
            sources=sources_set,
            tiers=tiers_set,
        )
    except ValueError as exc:
        return _error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return _error_result(
            "QUERY_NEWS_FAILED",
            "Error querying related news from the vector store.",
            {"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(matched_articles),
            "articles": [
                _article_to_query_payload(article, score=score_by_id[article.id]) for article in matched_articles
            ],
        },
        indent=2,
    )


async def query_related_news_graph(
    query: str,
    limit: int = 10,
    published_after: str | None = None,
    timespan: str | None = None,
    categories: Any | None = None,
    sources: Any | None = None,
    tiers: Any | None = None,
) -> str:
    """
    Search semantically related news from the vector store and return a related-news graph.
    """
    normalized_query = query.strip()
    if not normalized_query:
        return _error_result("INVALID_ARGUMENT", "query is required.")

    try:
        normalized_limit = _normalize_limit(limit)
        cutoff, categories_set, sources_set, tiers_set = _normalize_filters(
            published_after=published_after,
            timespan=timespan,
            categories=categories,
            sources=sources,
            tiers=tiers,
        )

        embedding_provider = get_embedding_provider()
        vector_store = get_vector_store()
        vector = embedding_provider.embed_text(normalized_query)
        matched_articles, score_by_id = await _search_ranked_articles(
            vector_store=vector_store,
            vector=vector,
            limit=normalized_limit,
            cutoff=cutoff,
            categories=categories_set,
            sources=sources_set,
            tiers=tiers_set,
        )

        if not matched_articles:
            return json.dumps({"ok": True, "count": 0, "graph": {"nodes": [], "edges": []}}, indent=2)

        article_texts = [build_news_embedding_text(_build_embedding_payload(article)) for article in matched_articles]
        article_vectors = embedding_provider.embed_texts(article_texts)
        related_limit = min(DEFAULT_RELATED_PER_ARTICLE, normalized_limit)
        seen_article_ids = {int(article.id) for article in matched_articles}
        related_by_seed_id: dict[int, tuple[list[Any], dict[int, float]]] = {}

        for article, article_vector in zip(matched_articles, article_vectors, strict=True):
            related_articles, related_score_by_id = await _search_ranked_articles(
                vector_store=vector_store,
                vector=article_vector,
                limit=related_limit,
                cutoff=cutoff,
                categories=categories_set,
                sources=sources_set,
                tiers=tiers_set,
                excluded_article_ids=seen_article_ids | {int(article.id)},
            )
            related_by_seed_id[int(article.id)] = (related_articles, related_score_by_id)
            seen_article_ids.update(int(related_article.id) for related_article in related_articles)

        graph = _build_graph(normalized_query, matched_articles, score_by_id, related_by_seed_id)
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
            "count": len(graph["nodes"]) - 1,
            "graph": graph,
        },
        indent=2,
    )
