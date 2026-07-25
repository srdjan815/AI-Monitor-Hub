from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class SupplierAcquisitionRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_acquisition_runs"
    __table_args__ = (
        UniqueConstraint(
            "acquisition_code",
            name="uq_supplier_acquisition_runs_acquisition_code",
        ),
        Index(
            "uq_supplier_acquisition_runs_source_idempotency",
            "source_connection_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_supplier_acquisition_runs_supplier_created",
            "supplier_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_supplier_acquisition_runs_source_status",
            "source_connection_id",
            "status",
        ),
        CheckConstraint(
            "trigger_type IN ('MANUAL','API_REQUEST','MANUAL_UPLOAD')",
            name="trigger_type_valid",
        ),
        CheckConstraint(
            "status IN "
            "('PENDING','RUNNING','SUCCEEDED','PARTIALLY_SUCCEEDED','FAILED','CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint(
            "total_record_count >= 0 AND accepted_record_count >= 0 "
            "AND rejected_record_count >= 0 AND warning_count >= 0 "
            "AND error_count >= 0",
            name="counts_nonnegative",
        ),
        CheckConstraint(
            "artifact_size_bytes IS NULL OR artifact_size_bytes >= 0",
            name="artifact_size_nonnegative",
        ),
    )

    acquisition_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'ACQ-' || lpad(nextval('supplier_acquisition_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="RESTRICT"),
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
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    artifact_reference: Mapped[str | None] = mapped_column(String(1000))
    content_type: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(64))
    artifact_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    total_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rejected_record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class SupplierStagedRecord(UUIDMixin, Base):
    __tablename__ = "supplier_staged_acquisition_records"
    __table_args__ = (
        UniqueConstraint(
            "acquisition_run_id",
            "record_number",
            name="uq_supplier_staged_records_run_number",
        ),
        Index(
            "ix_supplier_staged_records_run_status_number",
            "acquisition_run_id",
            "validation_status",
            "record_number",
        ),
        CheckConstraint("record_number >= 1", name="record_number_positive"),
        CheckConstraint(
            "validation_status IN ('ACCEPTED','REJECTED')",
            name="validation_status_valid",
        ),
        CheckConstraint(
            "warning_count >= 0 AND error_count >= 0",
            name="counts_nonnegative",
        ),
    )

    acquisition_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_acquisition_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    record_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_key: Mapped[str | None] = mapped_column(Text)
    source_identifier: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    mapped_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


class SupplierAcquisitionIssue(UUIDMixin, Base):
    __tablename__ = "supplier_acquisition_issues"
    __table_args__ = (
        Index(
            "ix_supplier_acquisition_issues_run_record",
            "acquisition_run_id",
            "record_number",
            "id",
        ),
        Index(
            "ix_supplier_acquisition_issues_run_severity",
            "acquisition_run_id",
            "severity",
        ),
        CheckConstraint(
            "severity IN ('WARNING','ERROR')",
            name="severity_valid",
        ),
        CheckConstraint("record_number >= 1", name="record_number_positive"),
    )

    acquisition_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_acquisition_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    staged_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_staged_acquisition_records.id", ondelete="RESTRICT"),
    )
    record_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_field_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_schema_fields.id", ondelete="RESTRICT"),
    )
    mapping_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_mapping_rules.id", ondelete="RESTRICT"),
    )
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    technical_context: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


__all__ = [
    "SupplierAcquisitionIssue",
    "SupplierAcquisitionRun",
    "SupplierStagedRecord",
]
