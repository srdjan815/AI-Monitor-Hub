"""Replace redundant claim indexes with an order-compatible partial index.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""

from alembic import op
import sqlalchemy as sa


revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_jobs_claim", table_name="jobs")
    op.drop_index("ix_jobs_claim_v2", table_name="jobs")
    op.create_index(
        "ix_jobs_claim_v3",
        "jobs",
        [
            "queue",
            sa.text("priority ASC"),
            sa.text("created_at ASC"),
            sa.text("id ASC"),
        ],
        postgresql_where=sa.text("status IN ('PENDING', 'RETRYING')"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_claim_v3", table_name="jobs")
    op.create_index(
        "ix_jobs_claim",
        "jobs",
        ["queue", "status", "priority", "created_at"],
    )
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
