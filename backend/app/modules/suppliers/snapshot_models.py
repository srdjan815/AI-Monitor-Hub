from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierSnapshot(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_code", name="uq_supplier_snapshots_snapshot_code"),
        UniqueConstraint(
            "acquisition_run_id",
            name="uq_supplier_snapshots_acquisition_run_id",
        ),
        Index(
            "ix_supplier_snapshots_supplier_created",
            "supplier_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_supplier_snapshots_source_state_created",
            "source_connection_id",
            "storage_state",
            "created_at",
        ),
        Index("ix_supplier_snapshots_status_state", "status", "storage_state"),
        CheckConstraint(
            "status IN ('BUILDING','READY','FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "storage_state IN ('ONLINE','ARCHIVED','RESTORING')",
            name="storage_state_valid",
        ),
        CheckConstraint("total_items >= 0", name="total_items_nonnegative"),
        CheckConstraint(
            "archive_size_bytes IS NULL OR archive_size_bytes >= 0",
            name="archive_size_nonnegative",
        ),
        CheckConstraint(
            "archive_after_days IS NULL OR archive_after_days >= 1",
            name="archive_after_days_positive",
        ),
    )

    snapshot_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'SNP-' || lpad(nextval('supplier_snapshot_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False
    )
    acquisition_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_acquisition_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schema_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mapping_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_mapping_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schema_version_reference: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_version_reference: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_state: Mapped[str] = mapped_column(String(16), nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_fingerprint: Mapped[str | None] = mapped_column(String(64))
    payload_checksum: Mapped[str | None] = mapped_column(String(64))
    source_artifact_checksum: Mapped[str | None] = mapped_column(String(64))
    created_from_acquisition_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_reference: Mapped[str | None] = mapped_column(String(1000))
    archive_checksum: Mapped[str | None] = mapped_column(String(64))
    archive_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    archive_format_version: Mapped[int | None] = mapped_column(Integer)
    archive_manifest_version: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_class: Mapped[str] = mapped_column(
        String(50), nullable=False, default="STANDARD"
    )
    archive_after_days: Mapped[int | None] = mapped_column(Integer)
    preserve_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archive_notes: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class SupplierSnapshotItem(UUIDMixin, Base):
    __tablename__ = "supplier_snapshot_items"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "source_staged_record_id",
            name="uq_supplier_snapshot_items_staged_record",
        ),
        UniqueConstraint(
            "snapshot_id",
            "record_number",
            name="uq_supplier_snapshot_items_record_number",
        ),
        Index(
            "ix_supplier_snapshot_items_snapshot_record",
            "snapshot_id",
            "record_number",
        ),
        Index(
            "ix_supplier_snapshot_items_snapshot_identifier",
            "snapshot_id",
            "source_identifier",
        ),
        CheckConstraint("record_number >= 1", name="record_number_positive"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    source_staged_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_staged_acquisition_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    record_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_key: Mapped[str | None] = mapped_column(Text)
    source_identifier: Mapped[str | None] = mapped_column(Text)
    item_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    mapped_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_image_links: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SupplierSnapshotArchiveOperation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_snapshot_archive_operations"
    __table_args__ = (
        Index(
            "ix_supplier_snapshot_archive_operations_snapshot_created",
            "snapshot_id",
            "created_at",
        ),
        CheckConstraint(
            "status IN ('EXPORTING','VERIFIED','FAILED','OFFLOADED','RESTORED')",
            name="status_valid",
        ),
        CheckConstraint(
            "archive_size_bytes IS NULL OR archive_size_bytes >= 0",
            name="archive_size_nonnegative",
        ),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    archive_reference: Mapped[str | None] = mapped_column(String(1000))
    archive_checksum: Mapped[str | None] = mapped_column(String(64))
    archive_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    format_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    manifest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    include_source_artifact: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)


__all__ = [
    "SupplierSnapshot",
    "SupplierSnapshotArchiveOperation",
    "SupplierSnapshotItem",
]
