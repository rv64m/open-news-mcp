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
    feeds_sync_interval_high_minutes: int = Field(default=5)
    feeds_sync_interval_normal_minutes: int = Field(default=10)
    feeds_sync_interval_low_minutes: int = Field(default=30)
    feeds_sync_limit_per_feed: int = Field(default=20)
    feeds_sync_request_timeout: float = Field(default=20.0)
    feeds_sync_concurrency: int = Field(default=8)
    embedding_backend: Literal["local", "openai", "google", "openrouter"] | None = Field(default=None)
    embedding_model: str = Field(default="Qwen/Qwen3-Embedding-0.6B")
    embedding_device: str | None = Field(default=None)
    embedding_normalize: bool = Field(default=True)
    embedding_batch_size: int = Field(default=16)
    embedding_trust_remote_code: bool = Field(default=True)
    embedding_openai_api_key: str | None = Field(default=None)
    embedding_openai_base_url: str | None = Field(default=None)
    embedding_google_api_key: str | None = Field(default=None)
    embedding_google_base_url: str | None = Field(default=None)
    embedding_openrouter_api_key: str | None = Field(default=None)
    embedding_openrouter_base_url: str | None = Field(default=None)
    vector_backend: Literal["qdrant"] | None = Field(default=None)
    vector_collection: str = Field(default="news_articles")
    vector_distance: Literal["cosine", "dot", "euclid"] = Field(default="cosine")
    qdrant_url: str | None = Field(default=None)
    qdrant_api_key: str | None = Field(default=None)
    qdrant_path: str | None = Field(default=None)
    qdrant_timeout: float = Field(default=10.0)
    qdrant_prefer_grpc: bool = Field(default=False)

    @property
    def outbound_proxy(self) -> str | None:
        if self.proxy_enable and self.proxy_url:
            return self.proxy_url
        return self.gdelt_proxy


settings = Settings()
