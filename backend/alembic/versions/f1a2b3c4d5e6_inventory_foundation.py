"""inventory foundation

Revision ID: f1a2b3c4d5e6
Revises: eb5f2829e72e
Create Date: 2026-07-23 15:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "eb5f2829e72e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("code", name="uq_warehouses_code"),
    )
    op.create_index(
        "ix_warehouses_active",
        "warehouses",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "inventory",
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False),
        sa.Column("minimum_stock", sa.Integer(), nullable=False),
        sa.Column("reorder_point", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            "minimum_stock >= 0",
            name=op.f("ck_inventory_minimum_stock_nonnegative"),
        ),
        sa.CheckConstraint(
            "quantity_on_hand >= 0",
            name=op.f("ck_inventory_quantity_on_hand_nonnegative"),
        ),
        sa.CheckConstraint(
            "quantity_reserved >= 0",
            name=op.f("ck_inventory_quantity_reserved_nonnegative"),
        ),
        sa.CheckConstraint(
            "quantity_reserved <= quantity_on_hand",
            name=op.f("ck_inventory_reserved_not_above_on_hand"),
        ),
        sa.CheckConstraint(
            "reorder_point >= 0",
            name=op.f("ck_inventory_reorder_point_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_inventory_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_inventory_warehouse_id_warehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory")),
        sa.UniqueConstraint(
            "warehouse_id",
            "product_id",
            name="uq_inventory_warehouse_product",
        ),
    )
    op.create_index(
        "ix_inventory_product_active",
        "inventory",
        ["product_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_warehouse_active",
        "inventory",
        ["warehouse_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_warehouse_active",
        table_name="inventory",
    )
    op.drop_index(
        "ix_inventory_product_active",
        table_name="inventory",
    )
    op.drop_table("inventory")
    op.drop_index("ix_warehouses_active", table_name="warehouses")
    op.drop_table("warehouses")
