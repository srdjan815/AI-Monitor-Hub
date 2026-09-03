"""Add normalized template conditions.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
"""

import sqlalchemy as sa
from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_template_conditions",
        sa.Column("template_item_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("boolean_operator", sa.String(16), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("comparator", sa.String(20), nullable=False),
        sa.Column("expected_value", sa.String(500)),
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
            ["template_item_id"],
            ["content_template_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_template_conditions_item",
        "content_template_conditions",
        ["template_item_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_template_conditions_item",
        table_name="content_template_conditions",
    )
    op.drop_table("content_template_conditions")
