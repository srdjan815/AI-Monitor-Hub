"""Align the execution claim index with ascending priority semantics.

Revision ID: f4a5b6c7d8e9
Revises: f3a4b5c6d7e8
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c7d8e9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_jobs_claim_v2", table_name="jobs")
    op.create_index(
        "ix_jobs_claim_v2",
        "jobs",
        [
            "queue",
            "status",
            sa.text("priority ASC"),
            sa.text("created_at ASC"),
            sa.text("id ASC"),
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_claim_v2", table_name="jobs")
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
