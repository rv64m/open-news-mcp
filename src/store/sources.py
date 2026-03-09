from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.core.feeds import Source

from .db import get_engine, get_session_factory
from .models import SourceCatalog


@dataclass(slots=True)
class SourceListItem:
    name: str
    category: str
    tier: int
    lang: str | None
    tags: list[str]
    feed_url: str


async def persist_sources(sources: list[Source]) -> int:
    engine = get_engine()
    session_factory = get_session_factory()
    if engine is None or session_factory is None or not sources:
        return 0

    insert_fn = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    rows = [
        {
            "name": source.name,
            "category": source.category,
            "tier": source.tier,
            "lang": source.lang,
            "tags": list(source.tags),
            "feed_url": source.url,
            "is_active": True,
        }
        for source in sources
    ]
    stmt = insert_fn(SourceCatalog).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[SourceCatalog.name],
        set_={
            "category": stmt.excluded.category,
            "tier": stmt.excluded.tier,
            "lang": stmt.excluded.lang,
            "tags": stmt.excluded.tags,
            "feed_url": stmt.excluded.feed_url,
            "is_active": stmt.excluded.is_active,
        },
    )

    async with session_factory() as session:
        result = await session.execute(stmt)
        await session.commit()
    return int(result.rowcount or 0)


async def list_sources_from_db(
    *,
    categories: list[str] | None = None,
    tiers: list[int] | None = None,
    limit: int = 100,
) -> list[SourceListItem]:
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database is not configured.")

    stmt = select(SourceCatalog).where(SourceCatalog.is_active.is_(True))
    if categories:
        stmt = stmt.where(SourceCatalog.category.in_(categories))
    if tiers:
        stmt = stmt.where(SourceCatalog.tier.in_(tiers))

    stmt = stmt.order_by(SourceCatalog.tier.asc(), SourceCatalog.category.asc(), SourceCatalog.name.asc()).limit(max(1, min(limit, 500)))

    async with session_factory() as session:
        rows = (await session.execute(stmt)).scalars().all()

    return [
        SourceListItem(
            name=row.name,
            category=row.category,
            tier=row.tier,
            lang=row.lang,
            tags=list(row.tags or []),
            feed_url=row.feed_url,
        )
        for row in rows
    ]
