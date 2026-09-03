"""product content platform

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def ts() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "content_languages",
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("native_name", sa.String(120), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_content_languages_code"),
        sa.UniqueConstraint("name", name="uq_content_languages_name"),
    )
    op.create_table(
        "content_types",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("supports_rich_text", sa.Boolean(), nullable=False),
        sa.Column("is_multilanguage", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.CheckConstraint(
            "sort_order >= 0", name="ck_content_types_sort_order_nonnegative"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_content_types_slug"),
    )
    op.create_table(
        "product_contents",
        sa.Column("content_key", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("content_type_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("subtitle", sa.String(500)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("prompt", sa.Text()),
        sa.Column("prompt_version", sa.String(100)),
        sa.Column("ai_model", sa.String(120)),
        sa.Column("temperature", sa.Numeric(5, 3)),
        sa.Column("token_count", sa.Integer()),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("generation_time_ms", sa.Integer()),
        sa.Column("generation_reason", sa.Text()),
        sa.Column("generation_notes", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("duplicate_of_id", sa.Uuid()),
        *ts(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_id"], ["content_languages.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["content_type_id"], ["content_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"], ["product_contents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_key", "revision", name="uq_product_contents_revision"
        ),
    )
    op.create_index(
        "ix_product_contents_lookup",
        "product_contents",
        ["product_id", "language_id", "content_type_id", "is_current"],
    )
    op.create_index(
        "ix_product_contents_workflow",
        "product_contents",
        ["status", "approval_status"],
    )
    op.create_index("ix_product_contents_updated", "product_contents", ["updated_at"])
    op.create_table(
        "product_seo",
        sa.Column("seo_key", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("seo_title", sa.String(70), nullable=False),
        sa.Column("seo_description", sa.String(170), nullable=False),
        sa.Column("seo_keywords", sa.Text()),
        sa.Column("canonical_url", sa.String(1000)),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("robots", sa.String(120), nullable=False),
        sa.Column("open_graph", postgresql.JSONB(), nullable=False),
        sa.Column("twitter_card", postgresql.JSONB(), nullable=False),
        sa.Column("schema_org", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_id"], ["content_languages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seo_key", "revision", name="uq_product_seo_revision"),
        sa.UniqueConstraint(
            "language_id", "slug", "is_current", name="uq_product_seo_current_slug"
        ),
    )
    op.create_index(
        "ix_product_seo_current",
        "product_seo",
        ["product_id", "language_id", "is_current"],
    )
    op.create_table(
        "product_landing_pages",
        sa.Column("landing_key", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("campaign", sa.String(255)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("hero_text", sa.Text()),
        sa.Column("cta_text", sa.String(255)),
        sa.Column("cta_url", sa.String(1000)),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_id"], ["content_languages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "landing_key", "revision", name="uq_product_landing_revision"
        ),
    )
    op.create_index(
        "ix_product_landing_current",
        "product_landing_pages",
        ["product_id", "language_id", "is_current"],
    )
    op.create_table(
        "product_document_references",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid()),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1500), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(120)),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_id"], ["content_languages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_documents_product",
        "product_document_references",
        ["product_id", "language_id"],
    )
    op.create_table(
        "product_video_references",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid()),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1500), nullable=False),
        sa.Column("video_type", sa.String(40), nullable=False),
        sa.Column("thumbnail_reference", sa.String(1500)),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.CheckConstraint(
            "sort_order >= 0", name="ck_product_video_references_sort_order_nonnegative"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_id"], ["content_languages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_videos_product",
        "product_video_references",
        ["product_id", "language_id", "sort_order"],
    )
    op.create_table(
        "content_change_events",
        sa.Column("cursor", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid()),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cursor"),
    )
    op.create_index(
        "ix_content_change_product", "content_change_events", ["product_id", "cursor"]
    )


def downgrade() -> None:
    for table in (
        "content_change_events",
        "product_video_references",
        "product_document_references",
        "product_landing_pages",
        "product_seo",
        "product_contents",
        "content_types",
        "content_languages",
    ):
        op.drop_table(table)
