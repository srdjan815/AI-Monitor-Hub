"""Add stable keyset indexes for high-volume list endpoints.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""

from alembic import op


revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_created_cursor",
        "jobs",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_products_created_cursor",
        "products",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_inventory_created_cursor",
        "inventory",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_inventory_movements_occurred_cursor",
        "inventory_movements",
        ["occurred_at", "id"],
    )
    op.drop_index("ix_inventory_reservations_created", table_name="inventory_reservations")
    op.create_index(
        "ix_inventory_reservations_created",
        "inventory_reservations",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_attribute_definitions_created_cursor",
        "attribute_definitions",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_attribute_definitions_created_cursor",
        table_name="attribute_definitions",
    )
    op.drop_index(
        "ix_inventory_reservations_created",
        table_name="inventory_reservations",
    )
    op.create_index(
        "ix_inventory_reservations_created",
        "inventory_reservations",
        ["created_at"],
    )
    op.drop_index(
        "ix_inventory_movements_occurred_cursor",
        table_name="inventory_movements",
    )
    op.drop_index("ix_inventory_created_cursor", table_name="inventory")
    op.drop_index("ix_products_created_cursor", table_name="products")
    op.drop_index("ix_jobs_created_cursor", table_name="jobs")
