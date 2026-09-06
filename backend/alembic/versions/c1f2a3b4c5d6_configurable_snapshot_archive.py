"""Configure snapshot archives on the verified mounted storage.

Revision ID: c1f2a3b4c5d6
Revises: b0e1f2a3b4c5
"""

from alembic import op
import sqlalchemy as sa

revision = "c1f2a3b4c5d6"
down_revision = "b0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifact_archive_settings",
        sa.Column(
            "snapshot_relative_path",
            sa.String(length=500),
            server_default="snapshots",
            nullable=False,
        ),
    )
    # A previous successful probe covered only the original-price-list folder.
    # Force an explicit re-test now that snapshot storage is part of the contract.
    op.execute(
        """
        UPDATE artifact_archive_settings
        SET last_tested_at = NULL,
            last_test_status = NULL,
            last_test_message = NULL,
            version = version + 1
        """
    )


def downgrade() -> None:
    op.drop_column("artifact_archive_settings", "snapshot_relative_path")
