"""Supplier Administration.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

from alembic import op
import sqlalchemy as sa


revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "suppliers",
        sa.Column("supplier_code", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=500), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tax_identifier", sa.String(length=120), nullable=True),
        sa.Column("registration_number", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
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
            "is_active OR status <> 'ACTIVE'",
            name=op.f("ck_suppliers_archived_not_operationally_active"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')",
            name=op.f("ck_suppliers_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppliers")),
        sa.UniqueConstraint(
            "supplier_code",
            name=op.f("uq_suppliers_supplier_code"),
        ),
    )
    op.alter_column(
        "suppliers",
        "supplier_code",
        server_default=sa.text(
            "'SUP-' || lpad(nextval('supplier_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    op.create_index(
        "ix_suppliers_active_status",
        "suppliers",
        ["is_active", "status"],
    )
    op.create_index(
        "ix_suppliers_company_name_id",
        "suppliers",
        ["company_name", "id"],
    )
    op.create_index(
        "ix_suppliers_created_cursor",
        "suppliers",
        ["created_at", "id"],
    )
    op.create_index(
        "uq_suppliers_active_tax_identifier",
        "suppliers",
        ["tax_identifier"],
        unique=True,
        postgresql_where=sa.text("is_active AND tax_identifier IS NOT NULL"),
    )
    op.create_index(
        "uq_suppliers_active_registration_number",
        "suppliers",
        ["registration_number"],
        unique=True,
        postgresql_where=sa.text(
            "is_active AND registration_number IS NOT NULL"
        ),
    )

    op.create_table(
        "supplier_contacts",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column(
            "contact_type",
            sa.String(length=32),
            server_default="GENERAL",
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("position", sa.String(length=255), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
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
            "contact_type IN "
            "('GENERAL', 'TECHNICAL', 'COMMERCIAL', 'BILLING', 'OTHER')",
            name=op.f("ck_supplier_contacts_contact_type_valid"),
        ),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name=op.f("ck_supplier_contacts_email_or_phone_required"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_contacts_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_contacts")),
    )
    op.create_index(
        "ix_supplier_contacts_order",
        "supplier_contacts",
        ["supplier_id", "is_primary", "contact_type", "name", "id"],
    )
    op.create_index(
        "ix_supplier_contacts_supplier_active",
        "supplier_contacts",
        ["supplier_id", "is_active"],
    )
    op.create_index(
        "uq_supplier_contacts_active_primary_type",
        "supplier_contacts",
        ["supplier_id", "contact_type"],
        unique=True,
        postgresql_where=sa.text("is_active AND is_primary"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_supplier_contacts_active_primary_type",
        table_name="supplier_contacts",
    )
    op.drop_index(
        "ix_supplier_contacts_supplier_active",
        table_name="supplier_contacts",
    )
    op.drop_index("ix_supplier_contacts_order", table_name="supplier_contacts")
    op.drop_table("supplier_contacts")

    op.drop_index(
        "uq_suppliers_active_registration_number",
        table_name="suppliers",
    )
    op.drop_index(
        "uq_suppliers_active_tax_identifier",
        table_name="suppliers",
    )
    op.drop_index("ix_suppliers_created_cursor", table_name="suppliers")
    op.drop_index("ix_suppliers_company_name_id", table_name="suppliers")
    op.drop_index("ix_suppliers_active_status", table_name="suppliers")
    op.drop_table("suppliers")
    op.execute("DROP SEQUENCE supplier_code_seq")
