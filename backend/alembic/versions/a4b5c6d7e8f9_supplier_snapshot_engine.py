"""Supplier Snapshot Engine.

Revision ID: a4b5c6d7e8f9
Revises: a3b4c5d6e7f8
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a4b5c6d7e8f9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.execute("CREATE SEQUENCE supplier_snapshot_code_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "supplier_snapshots",
        sa.Column("snapshot_code", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("source_connection_id", sa.Uuid(), nullable=False),
        sa.Column("acquisition_run_id", sa.Uuid(), nullable=False),
        sa.Column("schema_profile_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_reference", sa.Integer(), nullable=False),
        sa.Column("mapping_version_reference", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("storage_state", sa.String(length=16), nullable=False),
        sa.Column("total_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("snapshot_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("payload_checksum", sa.String(length=64), nullable=True),
        sa.Column("source_artifact_checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "created_from_acquisition_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive_reference", sa.String(length=1000), nullable=True),
        sa.Column("archive_checksum", sa.String(length=64), nullable=True),
        sa.Column("archive_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("archive_format_version", sa.Integer(), nullable=True),
        sa.Column("archive_manifest_version", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "retention_class",
            sa.String(length=50),
            server_default="STANDARD",
            nullable=False,
        ),
        sa.Column("archive_after_days", sa.Integer(), nullable=True),
        sa.Column(
            "preserve_online", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "legal_hold", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("archive_notes", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('BUILDING','READY','FAILED')",
            name=op.f("ck_supplier_snapshots_status_valid"),
        ),
        sa.CheckConstraint(
            "storage_state IN ('ONLINE','ARCHIVED','RESTORING')",
            name=op.f("ck_supplier_snapshots_storage_state_valid"),
        ),
        sa.CheckConstraint(
            "total_items >= 0",
            name=op.f("ck_supplier_snapshots_total_items_nonnegative"),
        ),
        sa.CheckConstraint(
            "archive_size_bytes IS NULL OR archive_size_bytes >= 0",
            name=op.f("ck_supplier_snapshots_archive_size_nonnegative"),
        ),
        sa.CheckConstraint(
            "archive_after_days IS NULL OR archive_after_days >= 1",
            name=op.f("ck_supplier_snapshots_archive_after_days_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_snapshots_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_connection_id"],
            ["supplier_sources.id"],
            name=op.f(
                "fk_supplier_snapshots_source_connection_id_supplier_sources"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id"],
            ["supplier_acquisition_runs.id"],
            name=op.f(
                "fk_supplier_snapshots_acquisition_run_id_supplier_acquisition_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schema_profile_id"],
            ["supplier_schema_profiles.id"],
            name=op.f(
                "fk_supplier_snapshots_schema_profile_id_supplier_schema_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mapping_profile_id"],
            ["supplier_mapping_profiles.id"],
            name=op.f(
                "fk_supplier_snapshots_mapping_profile_id_supplier_mapping_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_snapshots")),
        sa.UniqueConstraint(
            "snapshot_code",
            name=op.f("uq_supplier_snapshots_snapshot_code"),
        ),
        sa.UniqueConstraint(
            "acquisition_run_id",
            name=op.f("uq_supplier_snapshots_acquisition_run_id"),
        ),
    )
    op.alter_column(
        "supplier_snapshots",
        "snapshot_code",
        server_default=sa.text(
            "'SNP-' || lpad(nextval('supplier_snapshot_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    op.create_index(
        "ix_supplier_snapshots_supplier_created",
        "supplier_snapshots",
        ["supplier_id", "created_at", "id"],
    )
    op.create_index(
        "ix_supplier_snapshots_source_state_created",
        "supplier_snapshots",
        ["source_connection_id", "storage_state", "created_at"],
    )
    op.create_index(
        "ix_supplier_snapshots_status_state",
        "supplier_snapshots",
        ["status", "storage_state"],
    )
    op.create_table(
        "supplier_snapshot_items",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_staged_record_id", sa.Uuid(), nullable=False),
        sa.Column("record_number", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("source_identifier", sa.Text(), nullable=True),
        sa.Column("item_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "mapped_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "source_image_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "record_number >= 1",
            name=op.f("ck_supplier_snapshot_items_record_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supplier_snapshots.id"],
            name=op.f(
                "fk_supplier_snapshot_items_snapshot_id_supplier_snapshots"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_staged_record_id"],
            ["supplier_staged_acquisition_records.id"],
            name=op.f(
                "fk_supplier_snapshot_items_source_staged_record_id_supplier_staged_acquisition_records"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_snapshot_items")),
        sa.UniqueConstraint(
            "snapshot_id",
            "source_staged_record_id",
            name=op.f("uq_supplier_snapshot_items_staged_record"),
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "record_number",
            name=op.f("uq_supplier_snapshot_items_record_number"),
        ),
    )
    op.create_index(
        "ix_supplier_snapshot_items_snapshot_record",
        "supplier_snapshot_items",
        ["snapshot_id", "record_number"],
    )
    op.create_index(
        "ix_supplier_snapshot_items_snapshot_identifier",
        "supplier_snapshot_items",
        ["snapshot_id", "source_identifier"],
    )
    op.create_table(
        "supplier_snapshot_archive_operations",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("archive_reference", sa.String(length=1000), nullable=True),
        sa.Column("archive_checksum", sa.String(length=64), nullable=True),
        sa.Column("archive_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "format_version", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "manifest_version", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "include_source_artifact",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('EXPORTING','VERIFIED','FAILED','OFFLOADED','RESTORED')",
            name=op.f("ck_supplier_snapshot_archive_operations_status_valid"),
        ),
        sa.CheckConstraint(
            "archive_size_bytes IS NULL OR archive_size_bytes >= 0",
            name=op.f(
                "ck_supplier_snapshot_archive_operations_archive_size_nonnegative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supplier_snapshots.id"],
            name=op.f(
                "fk_supplier_snapshot_archive_operations_snapshot_id_supplier_snapshots"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_supplier_snapshot_archive_operations")
        ),
    )
    op.create_index(
        "ix_supplier_snapshot_archive_operations_snapshot_created",
        "supplier_snapshot_archive_operations",
        ["snapshot_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_snapshot_archive_operations_snapshot_created",
        table_name="supplier_snapshot_archive_operations",
    )
    op.drop_table("supplier_snapshot_archive_operations")
    op.drop_index(
        "ix_supplier_snapshot_items_snapshot_identifier",
        table_name="supplier_snapshot_items",
    )
    op.drop_index(
        "ix_supplier_snapshot_items_snapshot_record",
        table_name="supplier_snapshot_items",
    )
    op.drop_table("supplier_snapshot_items")
    for name in (
        "ix_supplier_snapshots_status_state",
        "ix_supplier_snapshots_source_state_created",
        "ix_supplier_snapshots_supplier_created",
    ):
        op.drop_index(name, table_name="supplier_snapshots")
    op.drop_table("supplier_snapshots")
    op.execute("DROP SEQUENCE supplier_snapshot_code_seq")
