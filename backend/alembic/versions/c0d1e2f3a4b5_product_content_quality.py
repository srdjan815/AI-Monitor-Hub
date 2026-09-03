"""Product Content quality constraints and indexes.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
"""

import sqlalchemy as sa
from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_product_seo_current_slug",
        "product_seo",
        type_="unique",
    )
    op.create_index(
        "uq_product_seo_current_slug",
        "product_seo",
        ["language_id", "slug"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "uq_content_library_current_language",
        "content_library_revisions",
        ["library_item_id", "language_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_check_constraint(
        "ck_product_library_references_sort_order_nonnegative",
        "product_library_references",
        "sort_order >= 0",
    )
    op.create_index(
        "ix_product_library_item",
        "product_library_references",
        ["library_item_id", "is_active"],
    )
    op.create_check_constraint(
        "ck_content_template_items_sort_order_nonnegative",
        "content_template_items",
        "sort_order >= 0",
    )
    op.create_check_constraint(
        "ck_content_template_conditions_sort_order_nonnegative",
        "content_template_conditions",
        "sort_order >= 0",
    )
    op.create_index(
        "ix_product_content_template",
        "product_content_templates",
        ["template_id", "is_active"],
    )
    op.create_check_constraint(
        "ck_content_scoring_policies_weights_nonnegative",
        "content_scoring_policies",
        "short_description_weight >= 0 AND "
        "long_description_weight >= 0 AND seo_weight >= 0 AND "
        "landing_weight >= 0 AND document_weight >= 0 AND "
        "video_weight >= 0 AND translation_weight >= 0",
    )
    op.create_check_constraint(
        "ck_content_score_history_score_range",
        "content_score_history",
        "score >= 0 AND score <= 100",
    )
    op.create_index(
        "ix_content_score_product_type_calculated",
        "content_score_history",
        ["product_id", "score_type", "calculated_at"],
    )
    op.create_index(
        "ix_content_prompt_type_active",
        "content_type_prompt_versions",
        ["content_type_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_prompt_type_active",
        table_name="content_type_prompt_versions",
    )
    op.drop_index(
        "ix_content_score_product_type_calculated",
        table_name="content_score_history",
    )
    op.drop_constraint(
        "ck_content_score_history_score_range",
        "content_score_history",
        type_="check",
    )
    op.drop_constraint(
        "ck_content_scoring_policies_weights_nonnegative",
        "content_scoring_policies",
        type_="check",
    )
    op.drop_index(
        "ix_product_content_template",
        table_name="product_content_templates",
    )
    op.drop_constraint(
        "ck_content_template_conditions_sort_order_nonnegative",
        "content_template_conditions",
        type_="check",
    )
    op.drop_constraint(
        "ck_content_template_items_sort_order_nonnegative",
        "content_template_items",
        type_="check",
    )
    op.drop_index(
        "ix_product_library_item",
        table_name="product_library_references",
    )
    op.drop_constraint(
        "ck_product_library_references_sort_order_nonnegative",
        "product_library_references",
        type_="check",
    )
    op.drop_index(
        "uq_content_library_current_language",
        table_name="content_library_revisions",
    )
    op.drop_index("uq_product_seo_current_slug", table_name="product_seo")
    op.create_unique_constraint(
        "uq_product_seo_current_slug",
        "product_seo",
        ["language_id", "slug", "is_current"],
    )
