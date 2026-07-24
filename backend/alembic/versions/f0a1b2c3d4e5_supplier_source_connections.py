"""Supplier Source Connections.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_source_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "supplier_sources",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("secret_reference", sa.String(length=500), nullable=True),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("last_validation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validation_status", sa.String(length=32), nullable=True),
        sa.Column("last_validation_message", sa.String(length=1000), nullable=True),
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
            "source_type IN "
            "('API','CSV','EXCEL','XML','FTP','SFTP','HTTP',"
            "'GOOGLE_DRIVE','EMAIL','MANUAL_UPLOAD')",
            name=op.f("ck_supplier_sources_source_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','INACTIVE','ERROR')",
            name=op.f("ck_supplier_sources_status_valid"),
        ),
        sa.CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name=op.f("ck_supplier_sources_archived_not_operationally_active"),
        ),
        sa.CheckConstraint(
            "last_validation_status IS NULL OR "
            "last_validation_status IN ('VALID','INVALID')",
            name=op.f("ck_supplier_sources_validation_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_sources_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_sources")),
        sa.UniqueConstraint(
            "source_code",
            name=op.f("uq_supplier_sources_source_code"),
        ),
    )
    op.alter_column(
        "supplier_sources",
        "source_code",
        server_default=sa.text(
            "'SRC-' || lpad(nextval('supplier_source_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    op.create_index(
        "uq_supplier_sources_active_supplier_name",
        "supplier_sources",
        ["supplier_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_supplier_sources_supplier_active",
        "supplier_sources",
        ["supplier_id", "is_active"],
    )
    op.create_index(
        "ix_supplier_sources_supplier_type_status",
        "supplier_sources",
        ["supplier_id", "source_type", "status"],
    )
    op.create_index(
        "ix_supplier_sources_name_id",
        "supplier_sources",
        ["supplier_id", "name", "id"],
    )
    op.create_index(
        "ix_supplier_sources_created_cursor",
        "supplier_sources",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_sources_created_cursor", table_name="supplier_sources")
    op.drop_index("ix_supplier_sources_name_id", table_name="supplier_sources")
    op.drop_index(
        "ix_supplier_sources_supplier_type_status",
        table_name="supplier_sources",
    )
    op.drop_index(
        "ix_supplier_sources_supplier_active",
        table_name="supplier_sources",
    )
    op.drop_index(
        "uq_supplier_sources_active_supplier_name",
        table_name="supplier_sources",
    )
    op.drop_table("supplier_sources")
    op.execute("DROP SEQUENCE supplier_source_code_seq")
