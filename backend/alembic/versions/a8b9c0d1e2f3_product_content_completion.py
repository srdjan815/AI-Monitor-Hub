"""product content completion

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def ts():
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


def upgrade():
    for table in ("product_contents", "product_landing_pages"):
        op.add_column(table, sa.Column("publish_at", sa.DateTime(timezone=True)))
        op.add_column(table, sa.Column("expire_at", sa.DateTime(timezone=True)))
        op.add_column(
            table,
            sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        )
    op.add_column("product_contents", sa.Column("campaign", sa.String(255)))
    for table in ("product_document_references", "product_video_references"):
        op.add_column(table, sa.Column("last_checked_at", sa.DateTime(timezone=True)))
        op.add_column(
            table,
            sa.Column(
                "link_status", sa.String(32), server_default="UNCHECKED", nullable=False
            ),
        )
        op.add_column(table, sa.Column("link_error", sa.Text()))
        op.add_column(table, sa.Column("next_check_at", sa.DateTime(timezone=True)))
    op.create_table(
        "content_library_items",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("item_kind", sa.String(32), nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_content_library_items_slug"),
    )
    op.create_index(
        "ix_content_library_kind_status",
        "content_library_items",
        ["item_kind", "status"],
    )
    op.create_table(
        "content_library_revisions",
        sa.Column("library_item_id", sa.Uuid(), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(
            ["library_item_id"], ["content_library_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["language_id"], ["content_languages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "library_item_id", "revision", name="uq_content_library_revision"
        ),
    )
    op.create_table(
        "product_library_references",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("library_item_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["library_item_id"], ["content_library_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "library_item_id", name="uq_product_library_reference"
        ),
    )
    op.create_table(
        "content_templates",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "content_template_items",
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("library_item_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("condition_operator", sa.String(16)),
        sa.Column("condition_source", sa.String(255)),
        sa.Column("condition_comparator", sa.String(20)),
        sa.Column("condition_value", sa.String(500)),
        *ts(),
        sa.ForeignKeyConstraint(
            ["template_id"], ["content_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["library_item_id"], ["content_library_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "library_item_id", name="uq_content_template_item"
        ),
    )
    op.create_table(
        "product_content_templates",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["content_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "template_id", name="uq_product_content_template"
        ),
    )
    op.create_table(
        "content_scoring_policies",
        sa.Column("name", sa.String(255), nullable=False),
        *[
            sa.Column(n, sa.Integer(), nullable=False)
            for n in (
                "short_description_weight",
                "long_description_weight",
                "seo_weight",
                "landing_weight",
                "document_weight",
                "video_weight",
                "translation_weight",
            )
        ],
        sa.Column("mandatory_sections", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "content_score_history",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid()),
        sa.Column("score_type", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["content_scoring_policies.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "content_type_prompt_versions",
        sa.Column("content_type_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.JSONB(), nullable=False),
        sa.Column("examples", postgresql.JSONB(), nullable=False),
        sa.Column("negative_examples", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *ts(),
        sa.ForeignKeyConstraint(
            ["content_type_id"], ["content_types.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_type_id", "version", name="uq_content_type_prompt_version"
        ),
    )


def downgrade():
    for table in (
        "content_type_prompt_versions",
        "content_score_history",
        "content_scoring_policies",
        "product_content_templates",
        "content_template_items",
        "content_templates",
        "product_library_references",
        "content_library_revisions",
        "content_library_items",
    ):
        op.drop_table(table)
    for table in ("product_document_references", "product_video_references"):
        for col in ("next_check_at", "link_error", "link_status", "last_checked_at"):
            op.drop_column(table, col)
    op.drop_column("product_contents", "campaign")
    for table in ("product_contents", "product_landing_pages"):
        for col in ("priority", "expire_at", "publish_at"):
            op.drop_column(table, col)
