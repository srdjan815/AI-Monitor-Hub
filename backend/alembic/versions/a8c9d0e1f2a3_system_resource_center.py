"""System resource center audit.

Revision ID: a8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from alembic import op
import sqlalchemy as sa


revision = "a8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_cleanup_audit",
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("older_than_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deleted_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deleted_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("candidate_digest", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.CheckConstraint("deleted_bytes >= 0", name=op.f("ck_system_cleanup_audit_deleted_bytes_nonnegative")),
        sa.CheckConstraint("deleted_files >= 0", name=op.f("ck_system_cleanup_audit_deleted_files_nonnegative")),
        sa.CheckConstraint("status IN ('SUCCEEDED','FAILED','NO_CHANGES')", name=op.f("ck_system_cleanup_audit_status_valid")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_cleanup_audit")),
    )
    op.create_index(
        "ix_system_cleanup_audit_created_at",
        "system_cleanup_audit",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_system_cleanup_audit_created_at", table_name="system_cleanup_audit")
    op.drop_table("system_cleanup_audit")
