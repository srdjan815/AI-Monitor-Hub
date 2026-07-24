"""Supplier Schema Profiles.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_schema_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "supplier_schema_profiles",
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("schema_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("field_count", sa.Integer(), server_default="0", nullable=False),
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
            name=op.f("ck_supplier_schema_profiles_status_valid"),
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name=op.f("ck_supplier_schema_profiles_version_number_positive"),
        ),
        sa.CheckConstraint(
            "field_count >= 0",
            name=op.f("ck_supplier_schema_profiles_field_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name=op.f("ck_supplier_schema_profiles_inactive_not_active_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_connection_id"],
            ["supplier_sources.id"],
            name=op.f(
                "fk_supplier_schema_profiles_source_connection_id_supplier_sources"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_schema_profiles")),
        sa.UniqueConstraint(
            "schema_code",
            name=op.f("uq_supplier_schema_profiles_schema_code"),
        ),
    )
    op.alter_column(
        "supplier_schema_profiles",
        "schema_code",
        server_default=sa.text(
            "'SCH-' || lpad(nextval('supplier_schema_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    op.create_index(
        "uq_supplier_schema_profiles_active_source",
        "supplier_schema_profiles",
        ["source_connection_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_supplier_schema_profiles_source_name_version",
        "supplier_schema_profiles",
        ["source_connection_id", sa.text("lower(name)"), "version_number"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_supplier_schema_profiles_source_status",
        "supplier_schema_profiles",
        ["source_connection_id", "status", "is_active"],
    )
    op.create_index(
        "ix_supplier_schema_profiles_created_cursor",
        "supplier_schema_profiles",
        ["created_at", "id"],
    )
    op.create_table(
        "supplier_schema_fields",
        sa.Column("schema_profile_id", sa.Uuid(), nullable=False),
        sa.Column("field_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("nullable", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("precision", sa.Integer(), nullable=True),
        sa.Column("scale", sa.Integer(), nullable=True),
        sa.Column("example_value", sa.Text(), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("is_key", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "is_identifier", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("is_price", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "is_quantity", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("is_stock", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "is_currency", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
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
            "position >= 1",
            name=op.f("ck_supplier_schema_fields_position_positive"),
        ),
        sa.CheckConstraint(
            "data_type IN "
            "('STRING','INTEGER','DECIMAL','BOOLEAN','DATE','DATETIME','TIME',"
            "'UUID','EMAIL','URL','PHONE','JSON','ENUM','BINARY')",
            name=op.f("ck_supplier_schema_fields_data_type_valid"),
        ),
        sa.CheckConstraint(
            "NOT required OR NOT nullable",
            name=op.f("ck_supplier_schema_fields_required_not_nullable"),
        ),
        sa.CheckConstraint(
            "max_length IS NULL OR max_length >= 1",
            name=op.f("ck_supplier_schema_fields_max_length_positive"),
        ),
        sa.CheckConstraint(
            "precision IS NULL OR precision >= 1",
            name=op.f("ck_supplier_schema_fields_precision_positive"),
        ),
        sa.CheckConstraint(
            "scale IS NULL OR scale >= 0",
            name=op.f("ck_supplier_schema_fields_scale_nonnegative"),
        ),
        sa.CheckConstraint(
            "scale IS NULL OR precision IS NOT NULL",
            name=op.f("ck_supplier_schema_fields_scale_requires_precision"),
        ),
        sa.CheckConstraint(
            "scale IS NULL OR scale <= precision",
            name=op.f("ck_supplier_schema_fields_scale_within_precision"),
        ),
        sa.ForeignKeyConstraint(
            ["schema_profile_id"],
            ["supplier_schema_profiles.id"],
            name=op.f(
                "fk_supplier_schema_fields_schema_profile_id_supplier_schema_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_schema_fields")),
    )
    op.create_index(
        "uq_supplier_schema_fields_active_code",
        "supplier_schema_fields",
        ["schema_profile_id", sa.text("lower(field_code)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_supplier_schema_fields_active_position",
        "supplier_schema_fields",
        ["schema_profile_id", "position"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    for suffix, predicate in (("key", "is_key"), ("price", "is_price")):
        op.create_index(
            f"uq_supplier_schema_fields_active_{suffix}",
            "supplier_schema_fields",
            ["schema_profile_id"],
            unique=True,
            postgresql_where=sa.text(f"is_active AND {predicate}"),
        )
    op.create_index(
        "ix_supplier_schema_fields_profile_active",
        "supplier_schema_fields",
        ["schema_profile_id", "is_active"],
    )


def downgrade() -> None:
    for name in (
        "ix_supplier_schema_fields_profile_active",
        "uq_supplier_schema_fields_active_price",
        "uq_supplier_schema_fields_active_key",
        "uq_supplier_schema_fields_active_position",
        "uq_supplier_schema_fields_active_code",
    ):
        op.drop_index(name, table_name="supplier_schema_fields")
    op.drop_table("supplier_schema_fields")
    for name in (
        "ix_supplier_schema_profiles_created_cursor",
        "ix_supplier_schema_profiles_source_status",
        "uq_supplier_schema_profiles_source_name_version",
        "uq_supplier_schema_profiles_active_source",
    ):
        op.drop_index(name, table_name="supplier_schema_profiles")
    op.drop_table("supplier_schema_profiles")
    op.execute("DROP SEQUENCE supplier_schema_code_seq")
