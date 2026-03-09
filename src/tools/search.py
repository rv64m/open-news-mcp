import json
from datetime import datetime, timezone
from typing import Any

from ..store import NewsSearchFilters, search_news_records


def _error_result(code: str, message: str, details: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return json.dumps(payload, indent=2)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _article_to_payload(article: Any) -> dict[str, Any]:
    return {
        "name": article.source_name,
        "url": article.url,
        "category": article.source_category,
        "tier": article.source_tier,
        "lang": article.source_lang,
        "title": article.title,
        "domain": article.domain,
        "published_at": _serialize_datetime(article.published_at),
        "language": article.article_language,
        "source_country": article.source_country,
        "url_mobile": article.url_mobile,
        "social_image": article.social_image,
        "tags": list(article.tags or []),
    }


async def search_news(
    limit: int = 10,
    published_after: str | None = None,
    timespan: str | None = None,
    categories: list[str] | None = None,
    sources: list[str] | None = None,
    tiers: list[int] | None = None,
    sort: str = "DateDesc",
) -> str:
    """
    Browse normalized news articles from the local database using structured filters.
    """
    try:
        records = await search_news_records(
            NewsSearchFilters(
                limit=limit,
                published_after=published_after,
                timespan=timespan,
                categories=categories,
                sources=sources,
                tiers=tiers,
                sort=sort,
            )
        )
    except ValueError as exc:
        return _error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return _error_result(
            "SEARCH_NEWS_FAILED",
            "Error searching local news database.",
            {"reason": str(exc)},
        )

    articles = [_article_to_payload(article) for article in records]
    return json.dumps(
        {
            "ok": True,
            "count": len(articles),
            "articles": articles,
        },
        indent=2,
    )
