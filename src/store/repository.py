from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, select

from .db import get_session_factory
from .models import NewsArticle


MAX_LIMIT = 50
SearchSort = Literal["published_at_desc", "published_at_asc", "tier_asc", "DateDesc", "DateAsc", "TierAsc"]


@dataclass(slots=True)
class NewsSearchFilters:
    limit: int = 10
    published_after: str | None = None
    timespan: str | None = None
    categories: list[str] | None = None
    sources: list[str] | None = None
    tiers: list[int] | None = None
    sort: SearchSort = "published_at_desc"


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


def _normalize_sort(sort: SearchSort) -> SearchSort:
    normalized = sort.strip()
    valid = {
        "published_at_desc",
        "published_at_asc",
        "tier_asc",
        "DateDesc",
        "DateAsc",
        "TierAsc",
    }
    if normalized not in valid:
        raise ValueError(
            "Unsupported sort "
            f"'{sort}'. Use one of: ['published_at_desc', 'published_at_asc', 'tier_asc', 'DateDesc', 'DateAsc', 'TierAsc']"
        )
    return normalized  # type: ignore[return-value]


async def search_news_records(filters: NewsSearchFilters) -> list[NewsArticle]:
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database is not configured.")

    normalized_limit = _normalize_limit(filters.limit)
    normalized_sort = _normalize_sort(filters.sort)

    published_cutoff = _parse_published_after(filters.published_after)
    timespan_cutoff = _parse_timespan(filters.timespan)
    cutoff = published_cutoff or timespan_cutoff
    if published_cutoff and timespan_cutoff:
        cutoff = max(published_cutoff, timespan_cutoff)

    if not any((cutoff, filters.categories, filters.sources, filters.tiers)):
        raise ValueError(
            "At least one structured filter is required: published_after/timespan/categories/sources/tiers."
        )

    conditions = []

    if cutoff:
        conditions.append(NewsArticle.published_at >= cutoff)
    if filters.categories:
        conditions.append(NewsArticle.source_category.in_(filters.categories))
    if filters.sources:
        conditions.append(NewsArticle.source_name.in_(filters.sources))
    if filters.tiers:
        conditions.append(NewsArticle.source_tier.in_(filters.tiers))

    stmt = select(NewsArticle).where(and_(*conditions))
    if normalized_sort in {"published_at_desc", "DateDesc"}:
        stmt = stmt.order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc())
    elif normalized_sort in {"published_at_asc", "DateAsc"}:
        stmt = stmt.order_by(NewsArticle.published_at.asc().nullslast(), NewsArticle.id.asc())
    else:
        stmt = stmt.order_by(NewsArticle.source_tier.asc(), NewsArticle.published_at.desc().nullslast())

    stmt = stmt.limit(normalized_limit)

    async with session_factory() as session:
        return (await session.execute(stmt)).scalars().all()
