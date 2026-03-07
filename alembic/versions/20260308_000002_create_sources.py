from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260308_000002"
down_revision = "20260308_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("lang", sa.String(length=32), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sources_category", "sources", ["category"], unique=False)
    op.create_index("ix_sources_lang", "sources", ["lang"], unique=False)
    op.create_index("ix_sources_name", "sources", ["name"], unique=True)
    op.create_index("ix_sources_tier", "sources", ["tier"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sources_tier", table_name="sources")
    op.drop_index("ix_sources_name", table_name="sources")
    op.drop_index("ix_sources_lang", table_name="sources")
    op.drop_index("ix_sources_category", table_name="sources")
    op.drop_table("sources")
