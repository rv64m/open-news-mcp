from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parent.parent / ".env",
            Path(__file__).resolve().parent / ".env",
        ),
        env_prefix="NEWS_",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=10110)
    transport: Literal["stdio", "sse", "streamable-http"] = Field(default="streamable-http")
    gdelt_timeout: float = Field(default=30.0)
    proxy_enable: bool = Field(
        default=False,
        validation_alias=AliasChoices("NEWS_PROXY_ENABLE", "PROXY_ENABLE"),
    )
    proxy_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NEWS_PROXY_URL", "PROXY_URL"),
    )
    # Backward-compatible fallback for older setups.
    gdelt_proxy: str | None = Field(default=None)
    database_backend: Literal["disabled", "sqlite", "postgres"] = Field(default="disabled")
    database_url: str | None = Field(default=None)
    sqlite_path: str = Field(default="data/news.db")
    database_echo: bool = Field(default=False)
    database_auto_migrate: bool = Field(default=False)
    feeds_sync_interval_high_minutes: int = Field(default=10)
    feeds_sync_interval_normal_minutes: int = Field(default=15)
    feeds_sync_interval_low_minutes: int = Field(default=30)
    feeds_sync_limit_per_feed: int = Field(default=20)
    feeds_sync_request_timeout: float = Field(default=20.0)
    feeds_sync_concurrency: int = Field(default=8)

    @property
    def outbound_proxy(self) -> str | None:
        if self.proxy_enable and self.proxy_url:
            return self.proxy_url
        return self.gdelt_proxy


settings = Settings()
