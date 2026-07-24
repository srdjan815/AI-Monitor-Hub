"""attribute platform completion

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-24 01:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
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
    op.add_column(
        "product_attribute_values",
        sa.Column("is_locked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("product_attribute_values", sa.Column("locked_by", sa.String(255)))
    op.add_column(
        "product_attribute_values",
        sa.Column("locked_at", sa.DateTime(timezone=True)),
    )
    op.add_column("product_attribute_values", sa.Column("lock_reason", sa.Text()))

    op.create_table(
        "attribute_families",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_attribute_families_sort_order_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_families")),
        sa.UniqueConstraint("slug", name="uq_attribute_families_slug"),
    )
    op.create_index(
        "ix_attribute_families_order",
        "attribute_families",
        ["sort_order", "slug"],
    )

    op.create_table(
        "attribute_templates",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("parent_template_id", sa.Uuid()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_attribute_templates_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_template_id"],
            ["attribute_templates.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attribute_templates_parent_template_id_attribute_templates"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_templates")),
        sa.UniqueConstraint("slug", name="uq_attribute_templates_slug"),
    )
    op.create_index(
        "ix_attribute_templates_active",
        "attribute_templates",
        ["is_active", "name"],
    )

    op.create_table(
        "attribute_family_items",
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_attribute_family_items_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["attribute_families.id"],
            ondelete="CASCADE",
            name=op.f("fk_attribute_family_items_family_id_attribute_families"),
        ),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="RESTRICT",
            name=op.f(
                "fk_attribute_family_items_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_family_items")),
        sa.UniqueConstraint(
            "family_id",
            "attribute_definition_id",
            name="uq_attribute_family_items_pair",
        ),
    )

    op.create_table(
        "attribute_template_items",
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid()),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_required_override", sa.Boolean()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_attribute_template_items_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["attribute_templates.id"],
            ondelete="CASCADE",
            name=op.f("fk_attribute_template_items_template_id_attribute_templates"),
        ),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="RESTRICT",
            name=op.f(
                "fk_attribute_template_items_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["attribute_families.id"],
            ondelete="SET NULL",
            name=op.f("fk_attribute_template_items_family_id_attribute_families"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_template_items")),
        sa.UniqueConstraint(
            "template_id",
            "attribute_definition_id",
            name="uq_attribute_template_items_pair",
        ),
    )
    op.create_index(
        "ix_attribute_template_items_order",
        "attribute_template_items",
        ["template_id", "sort_order"],
    )

    op.create_table(
        "attribute_template_families",
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["attribute_templates.id"],
            ondelete="CASCADE",
            name=op.f("fk_attribute_template_families_template_id_attribute_templates"),
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["attribute_families.id"],
            ondelete="CASCADE",
            name=op.f("fk_attribute_template_families_family_id_attribute_families"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_template_families")),
        sa.UniqueConstraint(
            "template_id",
            "family_id",
            name="uq_attribute_template_families_pair",
        ),
    )

    op.create_table(
        "category_attribute_families",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="CASCADE",
            name=op.f("fk_category_attribute_families_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["attribute_families.id"],
            ondelete="CASCADE",
            name=op.f("fk_category_attribute_families_family_id_attribute_families"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_attribute_families")),
        sa.UniqueConstraint(
            "category_id",
            "family_id",
            name="uq_category_attribute_families_pair",
        ),
    )

    op.create_table(
        "category_attribute_templates",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="CASCADE",
            name=op.f("fk_category_attribute_templates_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["attribute_templates.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_category_attribute_templates_template_id_attribute_templates"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_attribute_templates")),
        sa.UniqueConstraint(
            "category_id",
            "template_id",
            name="uq_category_attribute_templates_pair",
        ),
    )

    op.create_table(
        "attribute_formulas",
        sa.Column("target_attribute_id", sa.Uuid(), nullable=False),
        sa.Column("formula_kind", sa.String(32), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["target_attribute_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_formulas_target_attribute_id_attribute_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_formulas")),
        sa.UniqueConstraint("target_attribute_id", name="uq_attribute_formulas_target"),
    )

    op.create_table(
        "attribute_dependencies",
        sa.Column("source_attribute_id", sa.Uuid(), nullable=False),
        sa.Column("target_attribute_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_type", sa.String(40), nullable=False),
        sa.Column(
            "rule_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["source_attribute_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_dependencies_source_attribute_id_attribute_definitions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["target_attribute_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_dependencies_target_attribute_id_attribute_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_dependencies")),
        sa.UniqueConstraint(
            "source_attribute_id",
            "target_attribute_id",
            "dependency_type",
            name="uq_attribute_dependencies_rule",
        ),
    )
    op.create_index(
        "ix_attribute_dependencies_target",
        "attribute_dependencies",
        ["target_attribute_id", "dependency_type"],
    )

    op.create_table(
        "attribute_prompt_versions",
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("extraction_prompt", sa.Text()),
        sa.Column("normalization_prompt", sa.Text()),
        sa.Column("validation_prompt", sa.Text()),
        sa.Column(
            "examples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "negative_examples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "normalization_examples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "validation_examples",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_prompt_versions_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_prompt_versions")),
        sa.UniqueConstraint(
            "attribute_definition_id",
            "version_number",
            name="uq_attribute_prompt_versions_number",
        ),
    )
    op.create_index(
        "ix_attribute_prompt_versions_active",
        "attribute_prompt_versions",
        ["attribute_definition_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_table("attribute_prompt_versions")
    op.drop_table("attribute_dependencies")
    op.drop_table("attribute_formulas")
    op.drop_table("category_attribute_templates")
    op.drop_table("category_attribute_families")
    op.drop_table("attribute_template_families")
    op.drop_table("attribute_template_items")
    op.drop_table("attribute_family_items")
    op.drop_table("attribute_templates")
    op.drop_table("attribute_families")
    for name in ("lock_reason", "locked_at", "locked_by", "is_locked"):
        op.drop_column("product_attribute_values", name)
