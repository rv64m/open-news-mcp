from __future__ import annotations

import argparse
import asyncio
import logging
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
from src.store.db import resolve_database_url
from src.store import PersistMode, persist_news_payloads, persist_sources


logger = logging.getLogger("sync_feeds")


@dataclass(slots=True)
class FeedSyncResult:
    source: Source
    fetched: int = 0
    inserted: int = 0
    skipped: int = 0
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync RSS/news feeds into the database.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one sync cycle and exit.")
    mode.add_argument("--loop", action="store_true", help="Run continuously with in-process scheduling.")
    parser.add_argument("--categories", nargs="*", help="Only sync the provided feed categories.")
    parser.add_argument("--sources", nargs="*", help="Only sync the provided source names.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def _flatten_sources(categories: list[str] | None, source_names: list[str] | None) -> list[Source]:
    if categories:
        selected = list(chain.from_iterable(SOURCE_GROUPS.get(category, ()) for category in categories))
    else:
        selected = list(ALL_SOURCES)

    if source_names:
        names = set(source_names)
        selected = [source for source in selected if source.name in names]

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
            payloads = await _fetch_feed(client, source)
            stored = await persist_news_payloads(payloads, mode=PersistMode.INSERT_ONLY)
            return FeedSyncResult(
                source=source,
                fetched=len(payloads),
                inserted=stored.inserted,
                skipped=stored.skipped,
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


async def run_loop(sources: list[Source]) -> None:
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

        loop_now = asyncio.get_running_loop().time()
        for source in due_sources:
            next_run_at[source.name] = loop_now + _interval_for_source(source)


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    sources = _flatten_sources(args.categories, args.sources)
    if not sources:
        raise SystemExit("No sources selected.")
    if not resolve_database_url():
        raise SystemExit("Database is not configured. Set NEWS_DATABASE_BACKEND/NEWS_DATABASE_URL first.")

    logger.info("selected %s sources", len(sources))
    synced = await persist_sources(sources)
    logger.info("source catalog synced: %s records", synced)
    if args.loop:
        await run_loop(sources)
        return

    results = await run_cycle(sources)
    _log_cycle(results)

    failures = [result for result in results if result.error]
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
