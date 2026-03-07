from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260308_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_category", sa.String(length=128), nullable=True),
        sa.Column("source_lang", sa.String(length=32), nullable=True),
        sa.Column("source_tier", sa.Integer(), nullable=False),
        sa.Column("article_language", sa.String(length=32), nullable=True),
        sa.Column("source_country", sa.String(length=32), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url_mobile", sa.Text(), nullable=True),
        sa.Column("social_image", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_news_articles_domain", "news_articles", ["domain"], unique=False)
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"], unique=False)
    op.create_index("ix_news_articles_source_category", "news_articles", ["source_category"], unique=False)
    op.create_index("ix_news_articles_source_name", "news_articles", ["source_name"], unique=False)
    op.create_index("ix_news_articles_url_hash", "news_articles", ["url_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_news_articles_url_hash", table_name="news_articles")
    op.drop_index("ix_news_articles_source_name", table_name="news_articles")
    op.drop_index("ix_news_articles_source_category", table_name="news_articles")
    op.drop_index("ix_news_articles_published_at", table_name="news_articles")
    op.drop_index("ix_news_articles_domain", table_name="news_articles")
    op.drop_table("news_articles")
