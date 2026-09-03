"""product attribute system

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-07-23 23:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attribute_groups",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_attribute_groups_sort_order_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_groups")),
        sa.UniqueConstraint("slug", name="uq_attribute_groups_slug"),
    )
    op.create_index(
        "ix_attribute_groups_order",
        "attribute_groups",
        ["sort_order", "slug"],
    )

    op.add_column(
        "attribute_definitions", sa.Column("slug", sa.String(255), nullable=True)
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("internal_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "attribute_definitions", sa.Column("tooltip", sa.Text(), nullable=True)
    )
    op.add_column(
        "attribute_definitions", sa.Column("group_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "storage_kind",
            sa.String(32),
            server_default="ATTRIBUTE_VALUE",
            nullable=False,
        ),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("source_path", sa.String(500), nullable=True),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "default_sort_order", sa.Integer(), server_default="0", nullable=False
        ),
    )
    for name, default in (
        ("show_in_admin", "true"),
        ("show_on_webshop", "true"),
        ("show_in_mini_specification", "false"),
        ("show_in_full_specification", "true"),
        ("is_compatibility_attribute", "false"),
        ("use_ai", "false"),
    ):
        op.add_column(
            "attribute_definitions",
            sa.Column(name, sa.Boolean(), server_default=default, nullable=False),
        )
    op.add_column(
        "attribute_definitions", sa.Column("minimum_value", sa.Numeric(24, 8))
    )
    op.add_column(
        "attribute_definitions", sa.Column("maximum_value", sa.Numeric(24, 8))
    )
    op.add_column("attribute_definitions", sa.Column("minimum_length", sa.Integer()))
    op.add_column("attribute_definitions", sa.Column("maximum_length", sa.Integer()))
    op.add_column("attribute_definitions", sa.Column("regex_pattern", sa.Text()))
    op.add_column("attribute_definitions", sa.Column("default_unit", sa.String(80)))
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "accepted_units",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.add_column("attribute_definitions", sa.Column("validation_message", sa.Text()))
    op.add_column("attribute_definitions", sa.Column("filter_type", sa.String(32)))
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "filter_sort_order", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column("compatibility_type", sa.String(120)),
    )
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "compatibility_priority", sa.Integer(), server_default="0", nullable=False
        ),
    )
    for name in (
        "extraction_prompt",
        "normalization_prompt",
        "validation_prompt",
    ):
        op.add_column("attribute_definitions", sa.Column(name, sa.Text()))
    op.add_column(
        "attribute_definitions",
        sa.Column(
            "confidence_threshold",
            sa.Numeric(5, 4),
            server_default="0.8",
            nullable=False,
        ),
    )
    for name in ("examples", "forbidden_values"):
        op.add_column(
            "attribute_definitions",
            sa.Column(
                name,
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )
    op.add_column(
        "attribute_definitions",
        sa.Column("deactivated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        "UPDATE attribute_definitions "
        "SET slug = code, internal_name = COALESCE(api_name, code)"
    )
    op.alter_column("attribute_definitions", "slug", nullable=False)
    op.alter_column("attribute_definitions", "internal_name", nullable=False)
    op.create_unique_constraint(
        "uq_attribute_definitions_slug", "attribute_definitions", ["slug"]
    )
    op.create_unique_constraint(
        "uq_attribute_definitions_api_name",
        "attribute_definitions",
        ["api_name"],
    )
    op.create_unique_constraint(
        "uq_attribute_definitions_internal_name",
        "attribute_definitions",
        ["internal_name"],
    )
    op.create_foreign_key(
        op.f("fk_attribute_definitions_group_id_attribute_groups"),
        "attribute_definitions",
        "attribute_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_attribute_definitions_default_sort_order_nonnegative",
        "attribute_definitions",
        "default_sort_order >= 0",
    )
    op.create_check_constraint(
        "ck_attribute_definitions_confidence_threshold_range",
        "attribute_definitions",
        "confidence_threshold >= 0 AND confidence_threshold <= 1",
    )
    op.create_index(
        "ix_attribute_definitions_group_order",
        "attribute_definitions",
        ["group_id", "default_sort_order"],
    )

    op.add_column(
        "category_attributes",
        sa.Column("group_id_override", sa.Uuid(), nullable=True),
    )
    for name in (
        "show_on_webshop_override",
        "show_in_mini_specification_override",
        "show_in_full_specification_override",
        "is_filter_override",
        "is_compatibility_override",
    ):
        op.add_column("category_attributes", sa.Column(name, sa.Boolean()))
    op.add_column(
        "category_attributes",
        sa.Column("filter_type_override", sa.String(32)),
    )
    op.add_column(
        "category_attributes",
        sa.Column("compatibility_priority_override", sa.Integer()),
    )
    op.create_foreign_key(
        op.f("fk_category_attributes_group_id_override_attribute_groups"),
        "category_attributes",
        "attribute_groups",
        ["group_id_override"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_category_attributes_position_nonnegative",
        "category_attributes",
        "position >= 0",
    )

    op.create_table(
        "attribute_options",
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_value", sa.String(500), nullable=False),
        sa.Column("display_value", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "option_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_attribute_options_sort_order_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_options_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_options")),
        sa.UniqueConstraint(
            "attribute_definition_id",
            "canonical_value",
            name="uq_attribute_options_canonical",
        ),
    )
    op.create_index(
        "ix_attribute_options_order",
        "attribute_options",
        ["attribute_definition_id", "sort_order"],
    )

    op.create_table(
        "attribute_option_aliases",
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(500), nullable=False),
        sa.Column("normalized_alias", sa.String(500), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_option_aliases_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["attribute_options.id"],
            ondelete="CASCADE",
            name=op.f("fk_attribute_option_aliases_option_id_attribute_options"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_option_aliases")),
        sa.UniqueConstraint(
            "attribute_definition_id",
            "normalized_alias",
            name="uq_attribute_option_aliases_normalized",
        ),
    )

    op.create_table(
        "attribute_normalization_rules",
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("replacement", sa.Text()),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("case_sensitive", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text()),
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
        sa.CheckConstraint(
            "priority >= 0",
            name=op.f("ck_attribute_normalization_rules_priority_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="CASCADE",
            name=op.f(
                "fk_attribute_normalization_rules_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_normalization_rules")),
    )
    op.create_index(
        "ix_attribute_normalization_rules_order",
        "attribute_normalization_rules",
        ["attribute_definition_id", "priority"],
    )

    op.create_table(
        "product_attribute_values",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("value_key", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("raw_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "canonical_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("display_value", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(80)),
        sa.Column("text_value", sa.Text()),
        sa.Column("numeric_value", sa.Numeric(24, 8)),
        sa.Column("boolean_value", sa.Boolean()),
        sa.Column("date_value", sa.Date()),
        sa.Column("datetime_value", sa.DateTime(timezone=True)),
        sa.Column("json_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("validation_status", sa.String(32), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("validation_message", sa.Text()),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name=op.f("ck_product_attribute_values_confidence_range"),
        ),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_product_attribute_values_position_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="RESTRICT",
            name=op.f(
                "fk_product_attribute_values_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
            name=op.f("fk_product_attribute_values_product_id_products"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_attribute_values")),
    )
    op.create_index(
        "ix_product_attribute_values_product",
        "product_attribute_values",
        ["product_id"],
    )
    op.create_index(
        "ix_product_attribute_values_attribute",
        "product_attribute_values",
        ["attribute_definition_id"],
    )
    op.create_index(
        "ix_product_attribute_values_review",
        "product_attribute_values",
        ["validation_status", "approval_status"],
    )
    op.create_index(
        "ix_product_attribute_values_numeric",
        "product_attribute_values",
        ["numeric_value"],
    )
    op.create_index(
        "ix_product_attribute_values_text",
        "product_attribute_values",
        ["text_value"],
    )
    op.create_index(
        "ix_product_attribute_values_single",
        "product_attribute_values",
        ["product_id", "attribute_definition_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND value_key = 'single'"),
    )

    op.create_table(
        "product_attribute_value_history",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
        sa.Column("product_attribute_value_id", sa.Uuid()),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("previous_raw_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("previous_canonical_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("new_raw_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("new_canonical_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("actor_identifier", sa.String(255)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["attribute_definitions.id"],
            ondelete="RESTRICT",
            name=op.f(
                "fk_product_attribute_value_history_attribute_definition_id_attribute_definitions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["product_attribute_value_id"],
            ["product_attribute_values.id"],
            ondelete="SET NULL",
            name=op.f(
                "fk_product_attribute_value_history_product_attribute_value_id_product_attribute_values"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
            name=op.f("fk_product_attribute_value_history_product_id_products"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_attribute_value_history")),
    )
    op.create_index(
        "ix_product_attribute_history_product",
        "product_attribute_value_history",
        ["product_id", "occurred_at"],
    )

    op.create_table(
        "attribute_change_events",
        sa.Column(
            "cursor",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid()),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
            name=op.f("fk_attribute_change_events_product_id_products"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_change_events")),
        sa.UniqueConstraint("cursor", name=op.f("uq_attribute_change_events_cursor")),
    )
    op.create_index(
        "ix_attribute_change_events_product",
        "attribute_change_events",
        ["product_id", "cursor"],
    )
    op.create_index(
        "ix_attribute_change_events_occurred",
        "attribute_change_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("attribute_change_events")
    op.drop_table("product_attribute_value_history")
    op.drop_table("product_attribute_values")
    op.drop_table("attribute_normalization_rules")
    op.drop_table("attribute_option_aliases")
    op.drop_table("attribute_options")
    op.drop_constraint(
        op.f("ck_category_attributes_position_nonnegative"),
        "category_attributes",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_category_attributes_group_id_override_attribute_groups"),
        "category_attributes",
        type_="foreignkey",
    )
    for name in (
        "compatibility_priority_override",
        "filter_type_override",
        "is_compatibility_override",
        "is_filter_override",
        "show_in_full_specification_override",
        "show_in_mini_specification_override",
        "show_on_webshop_override",
        "group_id_override",
    ):
        op.drop_column("category_attributes", name)
    op.drop_index(
        "ix_attribute_definitions_group_order",
        table_name="attribute_definitions",
    )
    op.drop_constraint(
        op.f("ck_attribute_definitions_confidence_threshold_range"),
        "attribute_definitions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_attribute_definitions_default_sort_order_nonnegative"),
        "attribute_definitions",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_attribute_definitions_group_id_attribute_groups"),
        "attribute_definitions",
        type_="foreignkey",
    )
    for name in (
        "uq_attribute_definitions_internal_name",
        "uq_attribute_definitions_api_name",
        "uq_attribute_definitions_slug",
    ):
        op.drop_constraint(name, "attribute_definitions", type_="unique")
    for name in (
        "deactivated_at",
        "forbidden_values",
        "examples",
        "confidence_threshold",
        "validation_prompt",
        "normalization_prompt",
        "extraction_prompt",
        "use_ai",
        "compatibility_priority",
        "compatibility_type",
        "is_compatibility_attribute",
        "filter_sort_order",
        "filter_type",
        "validation_message",
        "default_value",
        "accepted_units",
        "default_unit",
        "regex_pattern",
        "maximum_length",
        "minimum_length",
        "maximum_value",
        "minimum_value",
        "show_in_full_specification",
        "show_in_mini_specification",
        "show_on_webshop",
        "show_in_admin",
        "default_sort_order",
        "source_path",
        "status",
        "storage_kind",
        "group_id",
        "tooltip",
        "internal_name",
        "slug",
    ):
        op.drop_column("attribute_definitions", name)
    op.drop_table("attribute_groups")
