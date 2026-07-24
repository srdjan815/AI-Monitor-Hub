"""Add fenced execution job leases.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""

from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("lease_token", sa.Uuid(), nullable=True))
    op.create_index("ix_jobs_lease_token", "jobs", ["lease_token"])


def downgrade() -> None:
    op.drop_index("ix_jobs_lease_token", table_name="jobs")
    op.drop_column("jobs", "lease_token")
