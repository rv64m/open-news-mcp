from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .db import get_engine, get_session_factory
from .models import NewsArticle


class PersistMode(StrEnum):
    INSERT_ONLY = "insert_only"
    UPSERT_TOUCH = "upsert_touch"


@dataclass(slots=True)
class PersistResult:
    enabled: bool
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    article_ids: list[int] | None = None
    error: str | None = None

    @property
    def saved(self) -> int:
        return self.inserted + self.updated


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_row(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    url = str(payload["url"]).strip()
    return {
        "url": url,
        "url_hash": _hash_url(url),
        "title": str(payload.get("title") or "").strip() or url,
        "domain": str(payload.get("domain") or "").strip(),
        "source_name": str(payload.get("name") or payload.get("domain") or "unknown").strip(),
        "source_category": payload.get("category"),
        "source_lang": payload.get("lang"),
        "source_tier": int(payload.get("tier") or 2),
        "article_language": payload.get("language"),
        "source_country": payload.get("source_country"),
        "published_at": _parse_datetime(payload.get("published_at")),
        "url_mobile": payload.get("url_mobile"),
        "social_image": payload.get("social_image"),
        "tags": list(payload.get("tags") or []),
        "raw_payload": payload,
        "is_embedded": False,
        "last_seen_at": now,
    }


def _dedupe_rows(payloads: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        if not payload.get("url"):
            continue
        row = _normalize_row(payload, now)
        deduped[row["url_hash"]] = row
    return list(deduped.values())


async def persist_news_payloads(
    payloads: list[dict[str, Any]],
    *,
    mode: PersistMode = PersistMode.UPSERT_TOUCH,
) -> PersistResult:
    if not payloads:
        return PersistResult(enabled=get_engine() is not None)

    engine = get_engine()
    session_factory = get_session_factory()
    if engine is None or session_factory is None:
        return PersistResult(enabled=False)

    now = datetime.now(timezone.utc)
    rows = _dedupe_rows(payloads, now)
    if not rows:
        return PersistResult(enabled=True, skipped=len(payloads))

    insert_fn = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = insert_fn(NewsArticle).values(rows)
    if mode == PersistMode.INSERT_ONLY:
        stmt = stmt.on_conflict_do_nothing(index_elements=[NewsArticle.url_hash])
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[NewsArticle.url_hash],
            set_={
                "url": stmt.excluded.url,
                "title": stmt.excluded.title,
                "domain": stmt.excluded.domain,
                "source_name": stmt.excluded.source_name,
                "source_category": stmt.excluded.source_category,
                "source_lang": stmt.excluded.source_lang,
                "source_tier": stmt.excluded.source_tier,
                "article_language": stmt.excluded.article_language,
                "source_country": stmt.excluded.source_country,
                "published_at": stmt.excluded.published_at,
                "url_mobile": stmt.excluded.url_mobile,
                "social_image": stmt.excluded.social_image,
                "tags": stmt.excluded.tags,
                "raw_payload": stmt.excluded.raw_payload,
                "is_embedded": False,
                "last_seen_at": stmt.excluded.last_seen_at,
                "updated_at": now,
            },
        )

    try:
        stmt = stmt.returning(NewsArticle.id)
        async with session_factory() as session:
            result = await session.execute(stmt)
            article_ids = [int(article_id) for article_id in result.scalars().all()]
            await session.commit()
    except Exception as exc:
        return PersistResult(enabled=True, skipped=len(rows), error=str(exc))

    affected = len(article_ids)
    if mode == PersistMode.INSERT_ONLY:
        return PersistResult(
            enabled=True,
            inserted=affected,
            skipped=len(rows) - affected,
            article_ids=article_ids,
        )
    return PersistResult(enabled=True, updated=affected, article_ids=article_ids)


async def fetch_unembedded_news(limit: int = 100) -> list[NewsArticle]:
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database is not configured.")

    stmt = (
        select(NewsArticle)
        .where(NewsArticle.is_embedded.is_(False))
        .order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.id.asc())
        .limit(max(1, min(limit, 1000)))
    )
    async with session_factory() as session:
        return (await session.execute(stmt)).scalars().all()


async def fetch_news_by_ids(article_ids: list[int]) -> list[NewsArticle]:
    if not article_ids:
        return []

    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database is not configured.")

    stmt = (
        select(NewsArticle)
        .where(NewsArticle.id.in_(article_ids))
        .order_by(NewsArticle.id.asc())
    )
    async with session_factory() as session:
        return (await session.execute(stmt)).scalars().all()


async def mark_news_as_embedded(article_ids: list[int]) -> int:
    if not article_ids:
        return 0

    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database is not configured.")

    stmt = (
        update(NewsArticle)
        .where(NewsArticle.id.in_(article_ids))
        .values(is_embedded=True)
    )
    async with session_factory() as session:
        result = await session.execute(stmt)
        await session.commit()
    return int(result.rowcount or 0)
