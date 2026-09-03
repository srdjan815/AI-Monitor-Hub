"""Add execution claim and stable-list query indexes.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_claim_v2",
        "jobs",
        [
            "queue",
            "status",
            sa.text("priority DESC"),
            sa.text("created_at ASC"),
            sa.text("id ASC"),
        ],
    )
    op.create_index(
        "ix_jobs_status_created",
        "jobs",
        [
            "status",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.drop_index("ix_jobs_claim_v2", table_name="jobs")
