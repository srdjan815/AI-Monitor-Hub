"""inventory reservations

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-23 20:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_reservations",
        sa.Column("reservation_number", sa.String(32), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("fulfilled_quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reference_type", sa.String(100), nullable=True),
        sa.Column("reference_id", sa.String(255), nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fulfilled_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "released_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "cancelled_at", sa.DateTime(timezone=True), nullable=True
        ),
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
            "quantity > 0",
            name=op.f("ck_inventory_reservations_quantity_positive"),
        ),
        sa.CheckConstraint(
            "fulfilled_quantity >= 0",
            name=op.f(
                "ck_inventory_reservations_fulfilled_quantity_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "fulfilled_quantity <= quantity",
            name=op.f(
                "ck_inventory_reservations_fulfilled_not_above_quantity"
            ),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PARTIALLY_FULFILLED', 'FULFILLED', "
            "'RELEASED', 'CANCELLED', 'EXPIRED')",
            name=op.f("ck_inventory_reservations_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f(
                "fk_inventory_reservations_product_id_products"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f(
                "fk_inventory_reservations_warehouse_id_warehouses"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_inventory_reservations")
        ),
        sa.UniqueConstraint(
            "reservation_number",
            name="uq_inventory_reservations_reservation_number",
        ),
        sa.UniqueConstraint(
            "external_reference",
            name="uq_inventory_reservations_external_reference",
        ),
    )
    op.create_index(
        "ix_inventory_reservations_created",
        "inventory_reservations",
        ["created_at"],
    )
    op.create_index(
        "ix_inventory_reservations_product_status",
        "inventory_reservations",
        ["product_id", "status"],
    )
    op.create_index(
        "ix_inventory_reservations_status_expires",
        "inventory_reservations",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_inventory_reservations_warehouse_status",
        "inventory_reservations",
        ["warehouse_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_reservations_warehouse_status",
        table_name="inventory_reservations",
    )
    op.drop_index(
        "ix_inventory_reservations_status_expires",
        table_name="inventory_reservations",
    )
    op.drop_index(
        "ix_inventory_reservations_product_status",
        table_name="inventory_reservations",
    )
    op.drop_index(
        "ix_inventory_reservations_created",
        table_name="inventory_reservations",
    )
    op.drop_table("inventory_reservations")
