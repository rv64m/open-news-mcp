"""
GDELT 2.0 Doc API Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~
Thin async wrapper around the GDELT DOC 2.0 API (https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/).

Supported query modes
---------------------
* article_search  – list of news articles (up to 250 per call)
* timeline_search – time-series volume / tone metrics

Usage example::

    async with GdeltProvider() as gd:
        articles = await gd.article_search(
            keywords=["bitcoin", "ethereum"],
            timespan="24h",
            num_records=50,
        )
        for a in articles:
            print(a.title, a.url, a.published_at)

        tl = await gd.timeline_search(
            mode="timelinevol",
            keywords="crypto bitcoin",
            timespan="7d",
        )
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# All valid timeline modes accepted by the GDELT Doc 2.0 API
TIMELINE_MODES = frozenset(
    {
        "timelinevol",
        "timelinevolraw",
        "timelinelang",
        "timelinesourcecountry",
        "timelinetone",
    }
)

# FIPS-2 country codes used by GDELT (common subset)
GDELT_COUNTRIES: dict[str, str] = {
    "US": "United States",
    "UK": "United Kingdom",
    "CH": "China",
    "RS": "Russia",
    "GM": "Germany",
    "FR": "France",
    "JA": "Japan",
    "IN": "India",
    "CA": "Canada",
    "AU": "Australia",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GdeltArticle:
    """A single news article returned by the GDELT article_search endpoint."""

    url: str
    title: str
    domain: str
    published_at: datetime | None  # UTC, naive
    language: str
    source_country: str
    url_mobile: str = ""
    social_image: str = ""


@dataclass(slots=True)
class GdeltTimelinePoint:
    """A single data point in a GDELT timeline response."""

    date: datetime  # UTC, naive
    series: str
    value: float


@dataclass(slots=True)
class GdeltSearchResult:
    """Aggregated result from article_search."""

    articles: list[GdeltArticle]
    query: str


@dataclass(slots=True)
class GdeltTimelineResult:
    """Aggregated result from timeline_search."""

    mode: str
    query: str
    points: list[GdeltTimelinePoint]


# ---------------------------------------------------------------------------
# Filter builder
# ---------------------------------------------------------------------------


def _build_query(
    *,
    keywords: str | list[str] | None = None,
    domain: str | list[str] | None = None,
    country: str | list[str] | None = None,
    language: str | list[str] | None = None,
    theme: str | list[str] | None = None,
    tone: str | None = None,
) -> str:
    """Build a GDELT query string from individual filter parameters.

    Multiple values within the same filter are OR-joined.
    All filters are AND-joined together.
    """
    parts: list[str] = []

    def _or_join(values: str | list[str] | None, prefix: str = "") -> str | None:
        if not values:
            return None
        if isinstance(values, str):
            values = [values]
        terms = [f'{prefix}"{v}"' if " " in v else f"{prefix}{v}" for v in values]
        if len(terms) == 1:
            return terms[0]
        return f"({' OR '.join(terms)})"

    kw_part = _or_join(keywords)
    if kw_part:
        parts.append(kw_part)

    domain_part = _or_join(domain, prefix="domain:")
    if domain_part:
        parts.append(domain_part)

    country_part = _or_join(country, prefix="sourcecountry:")
    if country_part:
        parts.append(country_part)

    lang_part = _or_join(language, prefix="sourcelang:")
    if lang_part:
        parts.append(lang_part)

    theme_part = _or_join(theme, prefix="theme:")
    if theme_part:
        parts.append(theme_part)

    if tone:
        tone = tone.strip()
        if tone and tone[0] not in ("<", ">"):
            raise ValueError("tone must start with '<' or '>' (e.g. '>5' or '<-5')")
        parts.append(f"tone{tone}")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y%m%dT%H%M%SZ",       # GDELT native  e.g. 20240101T120000Z
    "%Y-%m-%dT%H:%M:%SZ",   # ISO-8601 Z
    "%Y%m%d%H%M%S",         # compact no-tz
    "%Y%m%d",               # date-only
]


def _parse_gdelt_date(raw: str) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=None)  # store as naive UTC
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GdeltProvider:
    """Async GDELT Doc 2.0 API provider.

    Can be used as an async context manager::

        async with GdeltProvider() as gd:
            articles = await gd.article_search(keywords="bitcoin", timespan="24h")

    Or instantiated directly and shared::

        gd = GdeltProvider()
        articles = await gd.article_search(...)
        await gd.close()
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        resolved_proxy = (
            settings.outbound_proxy
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("ALL_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("http_proxy")
            or os.environ.get("all_proxy")
        )
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self._client = httpx.AsyncClient(
            proxy=resolved_proxy,
            transport=transport,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GdeltProvider":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def article_search(
        self,
        *,
        keywords: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        country: str | list[str] | None = None,
        language: str | None = "English",
        theme: str | list[str] | None = None,
        tone: str | None = None,
        timespan: str | None = "24h",
        start_date: str | None = None,
        end_date: str | None = None,
        num_records: int = 75,
        sort: str = "DateDesc",
    ) -> GdeltSearchResult:
        """Search for news articles via GDELT Doc 2.0 API.

        Parameters
        ----------
        keywords:
            One or more keyword phrases to search for (OR-joined).
        domain:
            Filter by domain(s), e.g. ``"cnn.com"`` or ``["bbc.co.uk", "nytimes.com"]``.
        country:
            FIPS-2 country code(s), e.g. ``"US"`` or ``["US", "UK"]``.
        language:
            ISO 639 language name, defaults to ``"English"``. Pass ``None`` for all languages.
        theme:
            GDELT GKG theme(s), e.g. ``"GENERAL_HEALTH"``.
        tone:
            Tone filter, must start with ``<`` or ``>``, e.g. ``">5"`` or ``"<-5"``.
        timespan:
            Relative timespan such as ``"15min"``, ``"1h"``, ``"24h"``, ``"7d"``, ``"3m"``.
            Ignored when ``start_date``/``end_date`` are provided.
        start_date:
            Start of the date range in ``YYYYMMDDHHMMSS`` or ``YYYY-MM-DD`` format (UTC).
        end_date:
            End of the date range (same format as ``start_date``).
        num_records:
            Number of articles to return (1–250).
        sort:
            Sort order – ``"DateDesc"`` (default) or ``"DateAsc"`` or ``"Relevance"``.

        Returns
        -------
        GdeltSearchResult
            Contains the list of :class:`GdeltArticle` objects and the raw query string.
        """
        num_records = max(1, min(num_records, 250))
        query = _build_query(
            keywords=keywords,
            domain=domain,
            country=country,
            language=language,
            theme=theme,
            tone=tone,
        )

        params: dict[str, Any] = {
            "query": query or "bitcoin",  # GDELT requires a non-empty query
            "mode": "ArtList",
            "maxrecords": num_records,
            "sort": sort,
            "format": "json",
        }
        if start_date and end_date:
            params["startdatetime"] = _normalise_date(start_date)
            params["enddatetime"] = _normalise_date(end_date)
        elif timespan:
            params["timespan"] = timespan

        data = await self._get_json(params)
        articles: list[GdeltArticle] = []
        for item in data.get("articles") or []:
            articles.append(
                GdeltArticle(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    domain=item.get("domain", ""),
                    published_at=_parse_gdelt_date(item.get("seendate", "")),
                    language=item.get("language", ""),
                    source_country=item.get("sourcecountry", ""),
                    url_mobile=item.get("url_mobile", ""),
                    social_image=item.get("socialimage", ""),
                )
            )

        return GdeltSearchResult(articles=articles, query=query)

    async def timeline_search(
        self,
        *,
        mode: str = "timelinevol",
        keywords: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        country: str | list[str] | None = None,
        language: str | None = None,
        theme: str | list[str] | None = None,
        tone: str | None = None,
        timespan: str | None = "7d",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> GdeltTimelineResult:
        """Retrieve a news coverage/tone timeline from GDELT.

        Parameters
        ----------
        mode:
            One of: ``timelinevol``, ``timelinevolraw``, ``timelinelang``,
            ``timelinesourcecountry``, ``timelinetone``.
        keywords, domain, country, language, theme, tone, timespan, start_date, end_date:
            Same semantics as :meth:`article_search`.

        Returns
        -------
        GdeltTimelineResult
            Contains a list of :class:`GdeltTimelinePoint` objects.
        """
        if mode not in TIMELINE_MODES:
            raise ValueError(f"Invalid timeline mode '{mode}'. Choose from: {sorted(TIMELINE_MODES)}")

        query = _build_query(
            keywords=keywords,
            domain=domain,
            country=country,
            language=language,
            theme=theme,
            tone=tone,
        )

        params: dict[str, Any] = {
            "query": query or "bitcoin",
            "mode": mode,
            "format": "json",
        }
        if start_date and end_date:
            params["startdatetime"] = _normalise_date(start_date)
            params["enddatetime"] = _normalise_date(end_date)
        elif timespan:
            params["timespan"] = timespan

        data = await self._get_json(params)

        points: list[GdeltTimelinePoint] = []
        # GDELT timeline JSON shape: {"timeline": [{"date": "...", "value": 1.23}, ...]}
        # For lang/country modes the shape is: {"timeline": {"SeriesName": [...], ...}}
        timeline_raw = data.get("timeline") or []

        if isinstance(timeline_raw, list):
            # Single series (timelinevol, timelinevolraw, timelinetone)
            for entry in timeline_raw:
                dt = _parse_gdelt_date(entry.get("date", ""))
                if dt is None:
                    continue
                points.append(
                    GdeltTimelinePoint(
                        date=dt,
                        series="default",
                        value=float(entry.get("value", 0.0)),
                    )
                )
        elif isinstance(timeline_raw, dict):
            # Multi-series (timelinelang, timelinesourcecountry)
            for series_name, entries in timeline_raw.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    dt = _parse_gdelt_date(entry.get("date", ""))
                    if dt is None:
                        continue
                    points.append(
                        GdeltTimelinePoint(
                            date=dt,
                            series=series_name,
                            value=float(entry.get("value", 0.0)),
                        )
                    )

        return GdeltTimelineResult(mode=mode, query=query, points=points)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_json(self, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{_BASE_URL}?{urlencode(params)}"
        resp = await self._client.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _normalise_date(date_str: str) -> str:
    """Normalise a date string to GDELT's ``YYYYMMDDHHMMSS`` format."""
    date_str = date_str.strip().replace("-", "").replace("T", "").replace(":", "").replace("Z", "")
    if len(date_str) == 8:
        date_str += "000000"  # append midnight
    return date_str


# ---------------------------------------------------------------------------
# Convenience preset: crypto news
# ---------------------------------------------------------------------------

_CRYPTO_KEYWORDS = [
    "bitcoin",
    "ethereum",
    "crypto",
    "cryptocurrency",
    "blockchain",
    "DeFi",
    "stablecoin",
]

_CRYPTO_DOMAINS = [
    "coindesk.com",
    "cointelegraph.com",
    "decrypt.co",
    "theblock.co",
    "cryptoslate.com",
    "bitcoinmagazine.com",
]


async def fetch_crypto_news(
    *,
    timespan: str = "24h",
    num_records: int = 100,
    language: str | None = "English",
    provider: GdeltProvider | None = None,
) -> list[GdeltArticle]:
    """Convenience function: fetch recent crypto news from GDELT.

    Uses a sensible default set of crypto keywords.  Pass your own
    ``provider`` instance to reuse an existing HTTP client.

    Parameters
    ----------
    timespan:
        The GDELT timespan string, defaults to ``"24h"``.
    num_records:
        Number of articles to return (max 250).
    language:
        Language filter, defaults to ``"English"``.
    provider:
        Optional existing :class:`GdeltProvider`.  If ``None`` a temporary
        client is created and closed automatically.
    """
    _own_provider = provider is None
    if _own_provider:
        provider = GdeltProvider()
    try:
        result = await provider.article_search(
            keywords=_CRYPTO_KEYWORDS,
            timespan=timespan,
            num_records=num_records,
            language=language,
        )
        return result.articles
    finally:
        if _own_provider:
            await provider.close()
