"""Enforce Product Content current and scheduling invariants.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
"""

import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, key, index_name in (
        ("product_contents", "content_key", "uq_product_contents_current_key"),
        ("product_seo", "seo_key", "uq_product_seo_current_key"),
        (
            "product_landing_pages",
            "landing_key",
            "uq_product_landing_current_key",
        ),
    ):
        op.create_index(
            index_name,
            table,
            [key],
            unique=True,
            postgresql_where=sa.text("is_current"),
        )
    op.create_index(
        "uq_content_prompt_active_type",
        "content_type_prompt_versions",
        ["content_type_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_check_constraint(
        "ck_product_contents_schedule_order",
        "product_contents",
        "expire_at IS NULL OR publish_at IS NULL OR expire_at > publish_at",
    )
    op.create_check_constraint(
        "ck_product_landing_pages_schedule_order",
        "product_landing_pages",
        "expire_at IS NULL OR publish_at IS NULL OR expire_at > publish_at",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_product_landing_pages_schedule_order",
        "product_landing_pages",
        type_="check",
    )
    op.drop_constraint(
        "ck_product_contents_schedule_order",
        "product_contents",
        type_="check",
    )
    op.drop_index(
        "uq_content_prompt_active_type",
        table_name="content_type_prompt_versions",
    )
    for table, index_name in (
        ("product_landing_pages", "uq_product_landing_current_key"),
        ("product_seo", "uq_product_seo_current_key"),
        ("product_contents", "uq_product_contents_current_key"),
    ):
        op.drop_index(index_name, table_name=table)
