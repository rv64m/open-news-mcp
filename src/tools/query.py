import json
import re
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..embedding import build_news_embedding_text, get_embedding_provider
from ..store import fetch_news_by_ids, fetch_news_by_urls
from ..vector import get_vector_store
from ..vector.base import VectorSearchResult
from .common import (
    ToolArgumentError,
    error_result,
    normalize_float,
    normalize_int,
    normalize_int_list,
    normalize_optional_string,
    normalize_required_string,
    normalize_string_list,
    parse_published_after,
    parse_timespan,
)
from .search import _article_to_payload


MAX_LIMIT = 50
OVERFETCH_MULTIPLIER = 5
MAX_VECTOR_FETCH = 200
MAX_GRAPH_EDGES = 100
DEFAULT_RELATED_PER_ARTICLE = 3
DEFAULT_MIN_SCORE = 0.35


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


def _compute_next_offset(*, offset: int, page_count: int, matched_total: int) -> int | None:
    if page_count <= 0:
        return None
    candidate = offset + page_count
    if candidate >= matched_total:
        return None
    return candidate


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


def _article_dedupe_key(article: Any) -> str:
    normalized_title = re.sub(r"\s+", " ", (article.title or "").strip().lower())
    published_day = ""
    if article.published_at is not None:
        published_day = article.published_at.date().isoformat()
    return f"{normalized_title}|{article.domain or ''}|{published_day}"


def _normalize_filters(
    *,
    published_after: str | None,
    timespan: str | None,
    categories: Any | None,
    sources: Any | None,
    tiers: Any | None,
) -> tuple[datetime | None, list[str] | None, list[str] | None, list[int] | None]:
    published_cutoff = parse_published_after(published_after)
    timespan_cutoff = parse_timespan(timespan)
    cutoff = published_cutoff or timespan_cutoff
    if published_cutoff and timespan_cutoff:
        cutoff = max(published_cutoff, timespan_cutoff)

    normalized_categories = normalize_string_list(categories, field_name="categories")
    normalized_sources = normalize_string_list(sources, field_name="sources")
    normalized_tiers = normalize_int_list(tiers, field_name="tiers")
    return cutoff, normalized_categories, normalized_sources, normalized_tiers


async def _collect_ranked_articles(
    *,
    hits: list[VectorSearchResult],
    offset: int,
    limit: int,
    min_score: float,
    cutoff: datetime | None,
    categories: set[str] | None,
    sources: set[str] | None,
    tiers: set[int] | None,
    excluded_article_ids: set[int] | None = None,
    excluded_dedupe_keys: set[str] | None = None,
) -> tuple[list[Any], dict[int, float], set[str], dict[str, Any]]:
    article_ids: list[int] = []
    urls: list[str] = []
    score_by_url: dict[str, float] = {}
    excluded = excluded_article_ids or set()
    dedupe_excluded = excluded_dedupe_keys or set()
    top_score = _query_hit_to_score(hits[0]) if hits else None

    for hit in hits:
        score = _query_hit_to_score(hit)
        if score < min_score:
            continue
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
        score_by_url[normalized_url] = score
        if isinstance(article_id, int):
            article_ids.append(article_id)

    if not urls:
        return [], {}, set(), {"candidate_count": len(hits), "top_score": top_score, "matched_before_pagination": 0}

    records = await fetch_news_by_urls(urls)
    if not records and article_ids:
        records = await fetch_news_by_ids(article_ids)
    records_by_url = {str(record.url).strip(): record for record in records}

    matched_all: list[Any] = []
    matched_scores: dict[int, float] = {}
    seen_dedupe_keys: set[str] = set()

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
        dedupe_key = _article_dedupe_key(article)
        if dedupe_key in dedupe_excluded or dedupe_key in seen_dedupe_keys:
            continue

        seen_dedupe_keys.add(dedupe_key)
        matched_all.append(article)
        matched_scores[int(article.id)] = score_by_url[url]

    paged_articles = matched_all[offset : offset + limit]
    paged_scores = {int(article.id): matched_scores[int(article.id)] for article in paged_articles}
    diagnostics = {
        "candidate_count": len(hits),
        "top_score": top_score,
        "matched_before_pagination": len(matched_all),
    }
    return paged_articles, paged_scores, seen_dedupe_keys, diagnostics


async def _search_ranked_articles(
    *,
    vector_store: Any,
    vector: list[float],
    offset: int,
    limit: int,
    min_score: float,
    cutoff: datetime | None,
    categories: set[str] | None,
    sources: set[str] | None,
    tiers: set[int] | None,
    excluded_article_ids: set[int] | None = None,
    excluded_dedupe_keys: set[str] | None = None,
) -> tuple[list[Any], dict[int, float], set[str], dict[str, Any]]:
    vector_limit = MAX_VECTOR_FETCH
    hits = vector_store.search(
        collection_name=settings.vector_collection,
        vector=vector,
        limit=vector_limit,
    )
    return await _collect_ranked_articles(
        hits=hits,
        offset=offset,
        limit=limit,
        min_score=min_score,
        cutoff=cutoff,
        categories=categories,
        sources=sources,
        tiers=tiers,
        excluded_article_ids=excluded_article_ids,
        excluded_dedupe_keys=excluded_dedupe_keys,
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
    dedupe_to_node_id: dict[str, str] = {}

    def add_article_node(article: Any, *, kind: str, query_score: float | None = None) -> str:
        dedupe_key = _article_dedupe_key(article)
        existing = dedupe_to_node_id.get(dedupe_key)
        if existing:
            return existing

        node_id = f"article:{article.id}"
        if node_id in node_ids:
            return node_id
        payload = _article_to_payload(article)
        payload["id"] = article.id
        payload["node_id"] = node_id
        payload["kind"] = kind
        payload["dedupe_key"] = dedupe_key
        if query_score is not None:
            payload["query_score"] = query_score
        nodes.append(payload)
        node_ids.add(node_id)
        dedupe_to_node_id[dedupe_key] = node_id
        return node_id

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
        seed_node_id = add_article_node(article, kind="seed", query_score=seed_score_by_id[article.id])
        add_edge("query", seed_node_id, "query_match", seed_score_by_id[article.id])

        related_articles, related_score_by_id = related_by_seed_id.get(article.id, ([], {}))
        for related_article in related_articles:
            related_node_id = add_article_node(related_article, kind="related")
            add_edge(
                seed_node_id,
                related_node_id,
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


def _build_applied_filters(
    *,
    published_after: str | None,
    timespan: str | None,
    categories: list[str] | None,
    sources: list[str] | None,
    tiers: list[int] | None,
    limit: int,
    offset: int,
    min_score: float,
) -> dict[str, Any]:
    return {
        "published_after": published_after,
        "timespan": timespan,
        "categories": categories,
        "sources": sources,
        "tiers": tiers,
        "limit": limit,
        "offset": offset,
        "min_score": min_score,
        "filter_scope": "categories/sources/tiers are source-level filters, not strict article-topic labels",
    }


async def query_news(
    query: Any,
    limit: Any = 10,
    offset: Any = 0,
    min_score: Any = DEFAULT_MIN_SCORE,
    published_after: Any | None = None,
    timespan: Any | None = None,
    categories: Any | None = None,
    sources: Any | None = None,
    tiers: Any | None = None,
) -> str:
    """
    Search semantically related news from the vector store and return the matching articles.
    """
    try:
        normalized_query = normalize_required_string(query, field_name="query")
        normalized_limit = _normalize_limit(normalize_int(limit, field_name="limit", min_value=1))
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)
        normalized_min_score = normalize_float(min_score, field_name="min_score", min_value=0.0, max_value=1.0)
        normalized_published_after = normalize_optional_string(published_after, field_name="published_after")
        normalized_timespan = normalize_optional_string(timespan, field_name="timespan")
        cutoff, categories_list, sources_list, tiers_list = _normalize_filters(
            published_after=normalized_published_after,
            timespan=normalized_timespan,
            categories=categories,
            sources=sources,
            tiers=tiers,
        )

        categories_set = set(categories_list or []) or None
        sources_set = set(sources_list or []) or None
        tiers_set = set(tiers_list or []) or None

        embedding_provider = get_embedding_provider()
        vector_store = get_vector_store()
        vector = embedding_provider.embed_text(normalized_query)
        matched_articles, score_by_id, _, diagnostics = await _search_ranked_articles(
            vector_store=vector_store,
            vector=vector,
            offset=normalized_offset,
            limit=normalized_limit,
            min_score=normalized_min_score,
            cutoff=cutoff,
            categories=categories_set,
            sources=sources_set,
            tiers=tiers_set,
        )
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except ValueError as exc:
        return error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return error_result(
            "QUERY_NEWS_FAILED",
            "Error querying related news from the vector store.",
            details={"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(matched_articles),
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": _compute_next_offset(
                    offset=normalized_offset,
                    page_count=len(matched_articles),
                    matched_total=diagnostics["matched_before_pagination"],
                ),
            },
            "query_diagnostics": {
                "top_score": diagnostics["top_score"],
                "candidate_count": diagnostics["candidate_count"],
                "candidate_count_scope": f"top_{MAX_VECTOR_FETCH}_vector_hits_after_embedding_search",
                "matched_before_pagination": diagnostics["matched_before_pagination"],
                "threshold_used": normalized_min_score,
                "applied_filters": _build_applied_filters(
                    published_after=normalized_published_after,
                    timespan=normalized_timespan,
                    categories=categories_list,
                    sources=sources_list,
                    tiers=tiers_list,
                    limit=normalized_limit,
                    offset=normalized_offset,
                    min_score=normalized_min_score,
                ),
            },
            "articles": [
                _article_to_query_payload(article, score=score_by_id[article.id]) for article in matched_articles
            ],
        },
        indent=2,
    )


async def query_related_news_graph(
    query: Any,
    limit: Any = 10,
    offset: Any = 0,
    min_score: Any = DEFAULT_MIN_SCORE,
    published_after: Any | None = None,
    timespan: Any | None = None,
    categories: Any | None = None,
    sources: Any | None = None,
    tiers: Any | None = None,
) -> str:
    """
    Search semantically related news from the vector store and return a related-news graph.
    """
    try:
        normalized_query = normalize_required_string(query, field_name="query")
        normalized_limit = _normalize_limit(normalize_int(limit, field_name="limit", min_value=1))
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)
        normalized_min_score = normalize_float(min_score, field_name="min_score", min_value=0.0, max_value=1.0)
        normalized_published_after = normalize_optional_string(published_after, field_name="published_after")
        normalized_timespan = normalize_optional_string(timespan, field_name="timespan")
        cutoff, categories_list, sources_list, tiers_list = _normalize_filters(
            published_after=normalized_published_after,
            timespan=normalized_timespan,
            categories=categories,
            sources=sources,
            tiers=tiers,
        )
        categories_set = set(categories_list or []) or None
        sources_set = set(sources_list or []) or None
        tiers_set = set(tiers_list or []) or None

        embedding_provider = get_embedding_provider()
        vector_store = get_vector_store()
        vector = embedding_provider.embed_text(normalized_query)
        matched_articles, score_by_id, seed_dedupe_keys, diagnostics = await _search_ranked_articles(
            vector_store=vector_store,
            vector=vector,
            offset=normalized_offset,
            limit=normalized_limit,
            min_score=normalized_min_score,
            cutoff=cutoff,
            categories=categories_set,
            sources=sources_set,
            tiers=tiers_set,
        )

        if not matched_articles:
            return json.dumps(
                {
                    "ok": True,
                    "count": 0,
                    "pagination": {
                        "limit": normalized_limit,
                        "offset": normalized_offset,
                        "next_offset": normalized_offset,
                    },
                    "query_diagnostics": {
                        "top_score": diagnostics["top_score"],
                        "candidate_count": diagnostics["candidate_count"],
                        "candidate_count_scope": f"top_{MAX_VECTOR_FETCH}_vector_hits_after_embedding_search",
                        "matched_before_pagination": 0,
                        "threshold_used": normalized_min_score,
                        "applied_filters": _build_applied_filters(
                            published_after=normalized_published_after,
                            timespan=normalized_timespan,
                            categories=categories_list,
                            sources=sources_list,
                            tiers=tiers_list,
                            limit=normalized_limit,
                            offset=normalized_offset,
                            min_score=normalized_min_score,
                        ),
                    },
                    "graph": {"nodes": [], "edges": []},
                },
                indent=2,
            )

        article_texts = [build_news_embedding_text(_build_embedding_payload(article)) for article in matched_articles]
        article_vectors = embedding_provider.embed_texts(article_texts)
        related_limit = min(DEFAULT_RELATED_PER_ARTICLE, normalized_limit)
        seen_article_ids = {int(article.id) for article in matched_articles}
        related_by_seed_id: dict[int, tuple[list[Any], dict[int, float]]] = {}
        seen_dedupe_keys = set(seed_dedupe_keys)

        for article, article_vector in zip(matched_articles, article_vectors, strict=True):
            related_articles, related_score_by_id, related_keys, _ = await _search_ranked_articles(
                vector_store=vector_store,
                vector=article_vector,
                offset=0,
                limit=related_limit,
                min_score=normalized_min_score,
                cutoff=cutoff,
                categories=categories_set,
                sources=sources_set,
                tiers=tiers_set,
                excluded_article_ids=seen_article_ids | {int(article.id)},
                excluded_dedupe_keys=seen_dedupe_keys,
            )
            related_by_seed_id[int(article.id)] = (related_articles, related_score_by_id)
            seen_article_ids.update(int(related_article.id) for related_article in related_articles)
            seen_dedupe_keys.update(related_keys)

        graph = _build_graph(normalized_query, matched_articles, score_by_id, related_by_seed_id)
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except ValueError as exc:
        return error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return error_result(
            "QUERY_RELATED_NEWS_GRAPH_FAILED",
            "Error querying related-news graph from the vector store.",
            details={"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(graph["nodes"]) - 1,
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": _compute_next_offset(
                    offset=normalized_offset,
                    page_count=len(matched_articles),
                    matched_total=diagnostics["matched_before_pagination"],
                ),
            },
            "query_diagnostics": {
                "top_score": diagnostics["top_score"],
                "candidate_count": diagnostics["candidate_count"],
                "candidate_count_scope": f"top_{MAX_VECTOR_FETCH}_vector_hits_after_embedding_search",
                "matched_before_pagination": diagnostics["matched_before_pagination"],
                "threshold_used": normalized_min_score,
                "applied_filters": _build_applied_filters(
                    published_after=normalized_published_after,
                    timespan=normalized_timespan,
                    categories=categories_list,
                    sources=sources_list,
                    tiers=tiers_list,
                    limit=normalized_limit,
                    offset=normalized_offset,
                    min_score=normalized_min_score,
                ),
            },
            "graph": graph,
        },
        indent=2,
    )
