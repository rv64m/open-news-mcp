from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from itertools import chain
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings
from src.core.feeds import ALL_SOURCES, SOURCE_GROUPS, Source
from src.embedding import build_news_embedding_text, get_embedding_provider
from src.store.db import resolve_database_url
from src.store import (
    PersistMode,
    fetch_news_by_ids,
    mark_news_as_embedded,
    persist_news_payloads,
    persist_sources,
)
from src.vector import get_vector_store
from src.vector.base import VectorPoint


logger = logging.getLogger("sync")


@dataclass(slots=True)
class FeedSyncResult:
    source: Source
    fetched: int = 0
    inserted: int = 0
    skipped: int = 0
    article_ids: list[int] | None = None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync RSS/news feeds into the database.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one sync cycle and exit.")
    mode.add_argument("--loop", action="store_true", help="Run continuously with in-process scheduling.")
    parser.add_argument("--embed", action="store_true", help="Run embedding after each sync cycle.")
    parser.add_argument("--categories", nargs="*", help="Only sync the provided feed categories.")
    parser.add_argument("--sources", nargs="*", help="Only sync the provided source names.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def _validate_embedding_enabled() -> None:
    if not settings.embedding_backend:
        raise SystemExit("Embedding is not configured. Set NEWS_EMBEDDING_BACKEND first.")
    if not settings.vector_backend:
        raise SystemExit("Vector store is not configured. Set NEWS_VECTOR_BACKEND first.")


def _vector_point_id(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def _build_vector_payload(article) -> dict[str, object]:
    return {
        "article_id": article.id,
        "url": article.url,
        "title": article.title,
        "source": article.source_name,
        "category": article.source_category,
        "tier": article.source_tier,
        "domain": article.domain,
        "published_at": article.published_at.isoformat() if article.published_at else None,
    }


def _build_embedding_payload(article) -> dict[str, object]:
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


def _configure_logging(level_name: str) -> None:
    normalized_level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=normalized_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    library_level = logging.DEBUG if normalized_level <= logging.DEBUG else logging.WARNING
    transport_level = logging.DEBUG if normalized_level <= logging.DEBUG else logging.WARNING
    logging.getLogger("sentence_transformers").setLevel(library_level)
    logging.getLogger("sentence_transformers.SentenceTransformer").setLevel(library_level)
    logging.getLogger("transformers").setLevel(library_level)
    logging.getLogger("huggingface_hub").setLevel(library_level)
    logging.getLogger("httpx").setLevel(transport_level)
    logging.getLogger("httpcore").setLevel(transport_level)
    if normalized_level > logging.DEBUG:
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"


def _flatten_sources(categories: list[str] | None, source_names: list[str] | None) -> list[Source]:
    if categories:
        selected = list(chain.from_iterable(SOURCE_GROUPS.get(category, ()) for category in categories))
    else:
        selected = list(ALL_SOURCES)

    if source_names:
        names = set(source_names)
        selected = [source for source in selected if source.name in names]

    # A source can be selected through multiple categories; de-duplicate by stable source name.
    deduped: dict[str, Source] = {}
    for source in selected:
        deduped[source.name] = source
    return list(deduped.values())


def _interval_for_source(source: Source) -> int:
    if source.tier <= 1:
        return settings.feeds_sync_interval_high_minutes * 60
    if source.tier == 2:
        return settings.feeds_sync_interval_normal_minutes * 60
    return settings.feeds_sync_interval_low_minutes * 60


def _entry_published_at(entry: feedparser.FeedParserDict) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        value = entry.get(attr)
        if value:
            dt = datetime(*value[:6], tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")

    for attr in ("published", "updated"):
        raw_value = entry.get(attr)
        if not raw_value:
            continue
        try:
            dt = parsedate_to_datetime(raw_value)
        except (TypeError, ValueError, IndexError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return None


def _normalize_domain(link: str, source: Source) -> str:
    hostname = urlparse(link).hostname or urlparse(source.url).hostname or source.name
    return hostname.removeprefix("www.")


def _entry_to_payload(source: Source, entry: feedparser.FeedParserDict) -> dict[str, Any] | None:
    link = (entry.get("link") or "").strip()
    title = (entry.get("title") or "").strip()
    if not link or not title:
        return None

    # Merge static source tags with feed item tags so downstream search/query can use both.
    tags = list(source.tags)
    for tag in entry.get("tags", []) or []:
        term = getattr(tag, "term", None) or tag.get("term")
        if term:
            tags.append(str(term))

    deduped_tags = list(dict.fromkeys(tag.strip() for tag in tags if tag and str(tag).strip()))

    return {
        "name": source.name,
        "url": link,
        "category": source.category,
        "tags": deduped_tags,
        "lang": source.lang,
        "tier": source.tier,
        "title": title,
        "domain": _normalize_domain(link, source),
        "published_at": _entry_published_at(entry),
        "language": source.lang,
        "source_country": None,
        "url_mobile": "",
        "social_image": "",
        "feed_url": source.url,
    }


async def _fetch_feed(client: httpx.AsyncClient, source: Source) -> list[dict[str, Any]]:
    response = await client.get(source.url)
    response.raise_for_status()
    parsed = feedparser.parse(response.text)
    entries = parsed.entries[: settings.feeds_sync_limit_per_feed]

    payloads: list[dict[str, Any]] = []
    for entry in entries:
        payload = _entry_to_payload(source, entry)
        if payload:
            payloads.append(payload)
    return payloads


async def _sync_source(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, source: Source) -> FeedSyncResult:
    async with semaphore:
        try:
            logger.debug("syncing source: source=%s url=%s", source.name, source.url)
            payloads = await _fetch_feed(client, source)
            logger.debug("fetched feed items: source=%s count=%s", source.name, len(payloads))
            # Sync uses INSERT_ONLY so we only embed articles that are newly inserted in this cycle.
            stored = await persist_news_payloads(payloads, mode=PersistMode.INSERT_ONLY)
            return FeedSyncResult(
                source=source,
                fetched=len(payloads),
                inserted=stored.inserted,
                skipped=stored.skipped,
                article_ids=stored.article_ids,
                error=stored.error,
            )
        except Exception as exc:
            return FeedSyncResult(source=source, error=str(exc))


async def run_cycle(sources: Iterable[Source]) -> list[FeedSyncResult]:
    timeout = httpx.Timeout(settings.feeds_sync_request_timeout)
    semaphore = asyncio.Semaphore(settings.feeds_sync_concurrency)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        proxy=settings.outbound_proxy,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    ) as client:
        return await asyncio.gather(*[_sync_source(client, semaphore, source) for source in sources])


def _log_cycle(results: list[FeedSyncResult]) -> None:
    total_fetched = sum(result.fetched for result in results)
    total_inserted = sum(result.inserted for result in results)
    total_skipped = sum(result.skipped for result in results)
    failures = [result for result in results if result.error]

    logger.info(
        "cycle finished: feeds=%s fetched=%s inserted=%s skipped=%s failures=%s",
        len(results),
        total_fetched,
        total_inserted,
        total_skipped,
        len(failures),
    )
    for result in failures:
        logger.warning("feed failed: source=%s error=%s", result.source.name, result.error)


async def _embed_article_ids(article_ids: list[int]) -> None:
    if not article_ids:
        logger.info("no newly inserted articles to embed")
        return

    articles = await fetch_news_by_ids(article_ids)
    pending_articles = [article for article in articles if not article.is_embedded]
    if not pending_articles:
        logger.info("selected articles are already embedded: count=%s", len(articles))
        return

    logger.info("embedding selected articles: requested=%s pending=%s", len(article_ids), len(pending_articles))
    embedding_provider = get_embedding_provider()
    vector_store = get_vector_store()
    texts = [build_news_embedding_text(_build_embedding_payload(article)) for article in pending_articles]
    vectors = embedding_provider.embed_texts(texts)
    if not vectors:
        logger.info("embedding returned no vectors")
        return

    vector_store.ensure_collection(
        collection_name=settings.vector_collection,
        vector_size=len(vectors[0]),
        distance=settings.vector_distance,
    )
    vector_store.upsert(
        collection_name=settings.vector_collection,
        points=[
            VectorPoint(
                id=_vector_point_id(article.url),
                vector=vector,
                payload=_build_vector_payload(article),
            )
            for article, vector in zip(pending_articles, vectors, strict=True)
        ],
    )
    marked = await mark_news_as_embedded([article.id for article in pending_articles])
    logger.info("embed sweep finished: selected=%s embedded=%s marked=%s", len(pending_articles), len(vectors), marked)


async def run_loop(sources: list[Source], *, embed: bool = False) -> None:
    # Track each source independently so high-tier feeds can run more frequently than low-tier feeds.
    next_run_at = {source.name: 0.0 for source in sources}

    while True:
        now_ts = asyncio.get_running_loop().time()
        due_sources = [source for source in sources if next_run_at[source.name] <= now_ts]
        if not due_sources:
            sleep_seconds = min(next_run_at.values()) - now_ts
            await asyncio.sleep(max(1.0, sleep_seconds))
            continue

        logger.info("starting sync cycle for %s feeds", len(due_sources))
        results = await run_cycle(due_sources)
        _log_cycle(results)
        if embed:
            # In loop mode we only embed the articles inserted by this sync cycle, not the whole backlog.
            article_ids = [article_id for result in results for article_id in (result.article_ids or [])]
            logger.info("starting embed sweep after sync cycle")
            await _embed_article_ids(article_ids)

        loop_now = asyncio.get_running_loop().time()
        for source in due_sources:
            next_run_at[source.name] = loop_now + _interval_for_source(source)


async def run_once(sources: list[Source], *, embed: bool = False) -> None:
    results = await run_cycle(sources)
    _log_cycle(results)
    if embed:
        # One-shot mode follows the same incremental rule as loop mode: only embed this cycle's inserts.
        article_ids = [article_id for result in results for article_id in (result.article_ids or [])]
        logger.info("starting embed sweep after sync cycle")
        await _embed_article_ids(article_ids)

    failures = [result for result in results if result.error]
    if failures:
        raise SystemExit(1)


async def main() -> None:
    args = parse_args()
    _configure_logging("DEBUG" if args.verbose else "INFO")

    sources = _flatten_sources(args.categories, args.sources)
    if not sources:
        raise SystemExit("No sources selected.")
    if not resolve_database_url():
        raise SystemExit("Database is not configured. Set NEWS_DATABASE_BACKEND/NEWS_DATABASE_URL first.")
    if args.embed:
        _validate_embedding_enabled()

    logger.info("selected %s sources", len(sources))
    synced = await persist_sources(sources)
    logger.info("source catalog synced: %s records", synced)
    
    if args.loop:
        logger.info("starting continuous sync loop")
        await run_loop(sources, embed=args.embed)
    else:
        logger.info("starting one-shot sync")
        await run_once(sources, embed=args.embed)


if __name__ == "__main__":
    asyncio.run(main())
