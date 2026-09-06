"""Artifact archive lifecycle and safe deduplication.

Revision ID: a9d0e1f2a3b4
Revises: a8c9d0e1f2a3
"""

from alembic import op
import sqlalchemy as sa

revision = "a9d0e1f2a3b4"
down_revision = "a8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_archive_settings",
        sa.Column("setting_key", sa.String(50), nullable=False),
        sa.Column("backend_type", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("relative_path", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "local_retention_days", sa.Integer(), server_default="30", nullable=False
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True)),
        sa.Column("last_test_status", sa.String(20)),
        sa.Column("last_test_message", sa.String(500)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
        sa.CheckConstraint(
            "backend_type IN ('MOUNT')",
            name=op.f("ck_artifact_archive_settings_backend_type_valid"),
        ),
        sa.CheckConstraint(
            "local_retention_days BETWEEN 1 AND 3650",
            name=op.f("ck_artifact_archive_settings_local_retention_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_archive_settings")),
        sa.UniqueConstraint("setting_key", name="uq_artifact_archive_settings_key"),
    )
    op.create_table(
        "artifact_archive_transfers",
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("setting_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("archive_reference", sa.String(1000)),
        sa.Column("verified_checksum", sa.String(64)),
        sa.Column("verified_size_bytes", sa.BigInteger()),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_message", sa.String(500)),
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
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_artifact_archive_transfers_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','VERIFIED','FAILED')",
            name=op.f("ck_artifact_archive_transfers_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["supplier_source_artifacts.id"],
            name=op.f(
                "fk_artifact_archive_transfers_artifact_id_supplier_source_artifacts"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["setting_id"],
            ["artifact_archive_settings.id"],
            name=op.f(
                "fk_artifact_archive_transfers_setting_id_artifact_archive_settings"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_archive_transfers")),
        sa.UniqueConstraint(
            "artifact_id", name="uq_artifact_archive_transfers_artifact"
        ),
    )


def downgrade() -> None:
    op.drop_table("artifact_archive_transfers")
    op.drop_table("artifact_archive_settings")
