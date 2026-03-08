from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceCatalog(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lang: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=func.true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_lang: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    article_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    url_mobile: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_embedded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=func.false(), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
