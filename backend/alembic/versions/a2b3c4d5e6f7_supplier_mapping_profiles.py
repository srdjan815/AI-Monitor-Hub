"""Supplier Mapping Profiles.

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a2b3c4d5e6f7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_mapping_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "supplier_mapping_profiles",
        sa.Column("schema_profile_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("rule_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ARCHIVED')",
            name=op.f("ck_supplier_mapping_profiles_status_valid"),
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name=op.f("ck_supplier_mapping_profiles_version_number_positive"),
        ),
        sa.CheckConstraint(
            "rule_count >= 0",
            name=op.f("ck_supplier_mapping_profiles_rule_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name=op.f("ck_supplier_mapping_profiles_inactive_not_active_status"),
        ),
        sa.ForeignKeyConstraint(
            ["schema_profile_id"],
            ["supplier_schema_profiles.id"],
            name=op.f(
                "fk_supplier_mapping_profiles_schema_profile_id_supplier_schema_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_mapping_profiles")),
        sa.UniqueConstraint(
            "mapping_code",
            name=op.f("uq_supplier_mapping_profiles_mapping_code"),
        ),
    )
    op.alter_column(
        "supplier_mapping_profiles",
        "mapping_code",
        server_default=sa.text(
            "'MAP-' || lpad(nextval('supplier_mapping_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    op.create_index(
        "uq_supplier_mapping_profiles_active_schema",
        "supplier_mapping_profiles",
        ["schema_profile_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_supplier_mapping_profiles_schema_name_version",
        "supplier_mapping_profiles",
        ["schema_profile_id", sa.text("lower(name)"), "version_number"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_supplier_mapping_profiles_schema_status",
        "supplier_mapping_profiles",
        ["schema_profile_id", "status", "is_active"],
    )
    op.create_index(
        "ix_supplier_mapping_profiles_created_cursor",
        "supplier_mapping_profiles",
        ["created_at", "id"],
    )
    op.create_table(
        "supplier_mapping_rules",
        sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
        sa.Column("schema_field_id", sa.Uuid(), nullable=False),
        sa.Column("target_attribute", sa.String(length=255), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("transformation_type", sa.String(length=32), nullable=False),
        sa.Column(
            "transformation_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("validation_rule", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "priority >= 1",
            name=op.f("ck_supplier_mapping_rules_priority_positive"),
        ),
        sa.CheckConstraint(
            "transformation_type IN "
            "('NONE','COPY','DEFAULT_VALUE','CONSTANT','CONCAT','SPLIT','TRIM',"
            "'UPPERCASE','LOWERCASE','REPLACE','REGEX')",
            name=op.f("ck_supplier_mapping_rules_transformation_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["mapping_profile_id"],
            ["supplier_mapping_profiles.id"],
            name=op.f(
                "fk_supplier_mapping_rules_mapping_profile_id_supplier_mapping_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schema_field_id"],
            ["supplier_schema_fields.id"],
            name=op.f(
                "fk_supplier_mapping_rules_schema_field_id_supplier_schema_fields"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_mapping_rules")),
    )
    op.create_index(
        "uq_supplier_mapping_rules_active_field",
        "supplier_mapping_rules",
        ["mapping_profile_id", "schema_field_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_supplier_mapping_rules_active_target",
        "supplier_mapping_rules",
        ["mapping_profile_id", sa.text("lower(target_attribute)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_supplier_mapping_rules_active_priority",
        "supplier_mapping_rules",
        ["mapping_profile_id", "priority"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_supplier_mapping_rules_profile_active",
        "supplier_mapping_rules",
        ["mapping_profile_id", "is_active"],
    )
    op.create_index(
        "ix_supplier_mapping_rules_schema_field",
        "supplier_mapping_rules",
        ["schema_field_id"],
    )


def downgrade() -> None:
    for name in (
        "ix_supplier_mapping_rules_schema_field",
        "ix_supplier_mapping_rules_profile_active",
        "uq_supplier_mapping_rules_active_priority",
        "uq_supplier_mapping_rules_active_target",
        "uq_supplier_mapping_rules_active_field",
    ):
        op.drop_index(name, table_name="supplier_mapping_rules")
    op.drop_table("supplier_mapping_rules")
    for name in (
        "ix_supplier_mapping_profiles_created_cursor",
        "ix_supplier_mapping_profiles_schema_status",
        "uq_supplier_mapping_profiles_schema_name_version",
        "uq_supplier_mapping_profiles_active_schema",
    ):
        op.drop_index(name, table_name="supplier_mapping_profiles")
    op.drop_table("supplier_mapping_profiles")
    op.execute("DROP SEQUENCE supplier_mapping_code_seq")
