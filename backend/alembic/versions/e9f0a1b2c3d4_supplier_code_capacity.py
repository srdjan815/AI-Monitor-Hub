"""Expand Supplier Code capacity.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""

from alembic import op
import sqlalchemy as sa


revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "suppliers",
        "supplier_code",
        existing_type=sa.String(length=10),
        type_=sa.String(length=50),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "suppliers",
        "supplier_code",
        existing_type=sa.String(length=50),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
