import json
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..embedding import get_embedding_provider
from ..store import fetch_news_by_ids
from ..vector import get_vector_store
from ..vector.base import VectorSearchResult
from .search import _article_to_payload, _error_result


MAX_LIMIT = 50
OVERFETCH_MULTIPLIER = 5
MAX_VECTOR_FETCH = 200


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


async def query_news(
    query: str,
    limit: int = 10,
    published_after: str | None = None,
    timespan: str | None = None,
    categories: list[str] | None = None,
    sources: list[str] | None = None,
    tiers: list[int] | None = None,
    language: str | None = None,
) -> str:
    """
    Search semantically related news from the vector store using a natural-language query.
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

        categories_set = set(categories or []) or None
        sources_set = set(sources or []) or None
        tiers_set = set(tiers or []) or None

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

        articles: list[dict[str, Any]] = []
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

            payload = _article_to_payload(article)
            payload["id"] = article.id
            payload["score"] = score_by_id[article_id]
            articles.append(payload)
            if len(articles) >= normalized_limit:
                break
    except ValueError as exc:
        return _error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return _error_result(
            "QUERY_NEWS_FAILED",
            "Error querying news from the vector store.",
            {"reason": str(exc)},
        )

    return json.dumps(
        {
            "ok": True,
            "count": len(articles),
            "articles": articles,
        },
        indent=2,
    )
