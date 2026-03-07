from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_base(url: str | None) -> str:
    return (url or "").strip().rstrip("/")


@dataclass(frozen=True)
class ProxySettings:
    env: str
    api_base: str
    rss_proxy_base: str

    @property
    def is_dev(self) -> bool:
        return self.env in {"dev", "development", "local"}


def get_proxy_settings() -> ProxySettings:
    env = (os.getenv("APP_ENV") or os.getenv("ENV") or os.getenv("ENVIRONMENT") or "dev").strip().lower()

    # Prefer an explicit relay base in production, mirroring worldmonitor's
    # "direct to relay when enabled" flow.
    relay_base = _normalize_base(
        os.getenv("NEWS_RSS_PROXY_BASE")
        or os.getenv("RSS_PROXY_BASE")
        or os.getenv("NEWS_PROXY_BASE")
    )
    relay_enabled = _is_truthy(
        os.getenv("NEWS_RSS_DIRECT_TO_RELAY")
        or os.getenv("RSS_DIRECT_TO_RELAY")
    )

    api_base = _normalize_base(
        os.getenv("NEWS_API_BASE")
        or os.getenv("API_BASE_URL")
        or os.getenv("PUBLIC_API_BASE")
        or os.getenv("APP_BASE_URL")
    )

    rss_proxy_base = relay_base if relay_enabled and relay_base else ""
    return ProxySettings(env=env, api_base=api_base, rss_proxy_base=rss_proxy_base)


def rss_proxy_url(feed_url: str, *, settings: ProxySettings | None = None) -> str:
    current = settings or get_proxy_settings()
    encoded = quote(feed_url, safe="")

    if current.rss_proxy_base:
        return f"{current.rss_proxy_base}/rss?url={encoded}"

    if current.api_base:
        return f"{current.api_base}/api/rss-proxy?url={encoded}"

    if current.is_dev:
        return feed_url

    return f"/api/rss-proxy?url={encoded}"


def source_url(url: str, *, use_proxy: bool = True, settings: ProxySettings | None = None) -> str:
    if not use_proxy:
        return url
    return rss_proxy_url(url, settings=settings)

