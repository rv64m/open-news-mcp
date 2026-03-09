import json
from datetime import datetime, timezone
from typing import Any

from ..store import NewsSearchFilters, search_news_records
from .common import (
    ToolArgumentError,
    error_result,
    normalize_int,
    normalize_int_list,
    normalize_optional_string,
    normalize_string_list,
)


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
    limit: Any = 10,
    offset: Any = 0,
    published_after: Any | None = None,
    timespan: Any | None = None,
    categories: Any | None = None,
    sources: Any | None = None,
    tiers: Any | None = None,
    sort: Any = "published_at_desc",
) -> str:
    """
    Browse normalized news articles from the local database using structured filters.
    """
    try:
        normalized_limit = normalize_int(limit, field_name="limit", min_value=1)
        normalized_offset = normalize_int(offset, field_name="offset", min_value=0)
        normalized_categories = normalize_string_list(categories, field_name="categories")
        normalized_sources = normalize_string_list(sources, field_name="sources")
        normalized_tiers = normalize_int_list(tiers, field_name="tiers")
        normalized_published_after = normalize_optional_string(published_after, field_name="published_after")
        normalized_timespan = normalize_optional_string(timespan, field_name="timespan")
        normalized_sort = normalize_optional_string(sort, field_name="sort") or "published_at_desc"

        records = await search_news_records(
            NewsSearchFilters(
                limit=normalized_limit,
                offset=normalized_offset,
                published_after=normalized_published_after,
                timespan=normalized_timespan,
                categories=normalized_categories,
                sources=normalized_sources,
                tiers=normalized_tiers,
                sort=normalized_sort,  # type: ignore[arg-type]
            )
        )
    except ToolArgumentError as exc:
        return error_result("INVALID_ARGUMENT", str(exc), field=exc.field)
    except ValueError as exc:
        return error_result("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return error_result(
            "SEARCH_NEWS_FAILED",
            "Error searching local news database.",
            details={"reason": str(exc)},
        )

    articles = [_article_to_payload(article) for article in records]
    return json.dumps(
        {
            "ok": True,
            "count": len(articles),
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "next_offset": normalized_offset + len(articles),
            },
            "query_diagnostics": {
                "applied_filters": {
                    "published_after": normalized_published_after,
                    "timespan": normalized_timespan,
                    "categories": normalized_categories,
                    "sources": normalized_sources,
                    "tiers": normalized_tiers,
                    "sort": normalized_sort,
                },
            },
            "articles": articles,
        },
        indent=2,
    )
