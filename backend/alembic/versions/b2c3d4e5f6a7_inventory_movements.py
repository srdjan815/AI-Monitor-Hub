"""inventory movements

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-23 17:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_movements",
        sa.Column("movement_number", sa.String(length=32), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("source_warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("destination_warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(length=100), nullable=True),
        sa.Column("reference_id", sa.String(length=255), nullable=True),
        sa.Column(
            "external_reference",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("is_reversed", sa.Boolean(), nullable=False),
        sa.Column(
            "reversed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("reversal_movement_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_inventory_movements_quantity_positive"),
        ),
        sa.CheckConstraint(
            "movement_type IN "
            "('RECEIPT', 'ISSUE', 'ADJUSTMENT_IN', "
            "'ADJUSTMENT_OUT', 'TRANSFER')",
            name=op.f(
                "ck_inventory_movements_movement_type_valid"
            ),
        ),
        sa.CheckConstraint(
            "("
            "movement_type IN ('RECEIPT', 'ADJUSTMENT_IN') "
            "AND source_warehouse_id IS NULL "
            "AND destination_warehouse_id IS NOT NULL"
            ") OR ("
            "movement_type IN ('ISSUE', 'ADJUSTMENT_OUT') "
            "AND source_warehouse_id IS NOT NULL "
            "AND destination_warehouse_id IS NULL"
            ") OR ("
            "movement_type = 'TRANSFER' "
            "AND source_warehouse_id IS NOT NULL "
            "AND destination_warehouse_id IS NOT NULL "
            "AND source_warehouse_id <> destination_warehouse_id"
            ")",
            name=op.f(
                "ck_inventory_movements_warehouse_combination_valid"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["destination_warehouse_id"],
            ["warehouses.id"],
            name=op.f(
                "fk_inventory_movements_destination_warehouse_id_warehouses"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f(
                "fk_inventory_movements_product_id_products"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversal_movement_id"],
            ["inventory_movements.id"],
            name=op.f(
                "fk_inventory_movements_reversal_movement_id_"
                "inventory_movements"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_warehouse_id"],
            ["warehouses.id"],
            name=op.f(
                "fk_inventory_movements_source_warehouse_id_warehouses"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_inventory_movements"),
        ),
        sa.UniqueConstraint(
            "external_reference",
            name="uq_inventory_movements_external_reference",
        ),
        sa.UniqueConstraint(
            "movement_number",
            name="uq_inventory_movements_movement_number",
        ),
    )
    op.create_index(
        "ix_inventory_movements_destination_occurred",
        "inventory_movements",
        ["destination_warehouse_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_product_occurred",
        "inventory_movements",
        ["product_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_source_occurred",
        "inventory_movements",
        ["source_warehouse_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_movements_type_occurred",
        "inventory_movements",
        ["movement_type", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_movements_type_occurred",
        table_name="inventory_movements",
    )
    op.drop_index(
        "ix_inventory_movements_source_occurred",
        table_name="inventory_movements",
    )
    op.drop_index(
        "ix_inventory_movements_product_occurred",
        table_name="inventory_movements",
    )
    op.drop_index(
        "ix_inventory_movements_destination_occurred",
        table_name="inventory_movements",
    )
    op.drop_table("inventory_movements")
