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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierSourceSchedule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_source_schedules"
    __table_args__ = (
        UniqueConstraint("source_connection_id", name="uq_supplier_source_schedules_source_connection_id"),
        Index("ix_supplier_source_schedules_due", "status", "next_run_at", postgresql_where=text("status = 'ENABLED'")),
        CheckConstraint("status IN ('MANUAL','ENABLED','PAUSED')", name="status_valid"),
        CheckConstraint("schedule_type IS NULL OR schedule_type IN ('DAILY','MULTI_DAILY','INTERVAL','WEEKDAYS','WEEKLY')", name="schedule_type_valid"),
        CheckConstraint("automation_depth IN ('FETCH_ONLY','FETCH_AND_ANALYZE','FULL_PIPELINE')", name="automation_depth_valid"),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 86400", name="timeout_valid"),
        CheckConstraint("max_attempts BETWEEN 1 AND 20", name="attempts_valid"),
        CheckConstraint("last_duration_ms IS NULL OR last_duration_ms >= 0", name="duration_nonnegative"),
        CheckConstraint("consecutive_failures >= 0", name="failures_nonnegative"),
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    schedule_type: Mapped[str | None] = mapped_column(String(24))
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="Europe/Belgrade")
    schedule_configuration: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    automation_depth: Mapped[str] = mapped_column(String(32), nullable=False, default="FETCH_ONLY")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str | None] = mapped_column(String(32))
    last_duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class SupplierSourceArtifact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_source_artifacts"
    __table_args__ = (
        UniqueConstraint("artifact_code", name="uq_supplier_source_artifacts_artifact_code"),
        UniqueConstraint("storage_reference", name="uq_supplier_source_artifacts_storage_reference"),
        Index("ix_supplier_source_artifacts_source_created", "source_connection_id", "created_at", "id"),
        Index("ix_supplier_source_artifacts_source_checksum", "source_connection_id", "checksum_sha256"),
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        CheckConstraint("record_count IS NULL OR record_count >= 0", name="record_count_nonnegative"),
        CheckConstraint("detected_format IN ('CSV','XLSX','XML','JSON')", name="format_valid"),
        CheckConstraint("retention_status IN ('ONLINE','ARCHIVED')", name="retention_status_valid"),
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False)
    artifact_code: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'ART-' || lpad(nextval('supplier_source_artifact_code_seq'::regclass)::text, 8, '0')"))
    storage_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(255))
    detected_format: Mapped[str] = mapped_column(String(16), nullable=False)
    encoding: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int | None] = mapped_column(Integer)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    retention_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ONLINE")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class SupplierSourcePipelineRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_source_pipeline_runs"
    __table_args__ = (
        UniqueConstraint("pipeline_code", name="uq_supplier_source_pipeline_runs_pipeline_code"),
        UniqueConstraint("idempotency_key", name="uq_supplier_source_pipeline_runs_idempotency_key"),
        UniqueConstraint("job_id", name="uq_supplier_source_pipeline_runs_job_id"),
        Index("uq_supplier_source_pipeline_runs_source_active", "source_connection_id", unique=True, postgresql_where=text("status IN ('PENDING','RUNNING')")),
        Index("ix_supplier_source_pipeline_runs_source_created", "source_connection_id", "created_at", "id"),
        Index("ix_supplier_source_pipeline_runs_schedule_occurrence", "schedule_id", "schedule_occurrence_at"),
        Index(
            "uq_supplier_source_pipeline_runs_schedule_occurrence",
            "schedule_id",
            "schedule_occurrence_at",
            unique=True,
            postgresql_where=text("schedule_id IS NOT NULL"),
        ),
        CheckConstraint("trigger_type IN ('MANUAL','SCHEDULED')", name="trigger_type_valid"),
        CheckConstraint("automation_depth IN ('FETCH_ONLY','FETCH_AND_ANALYZE','FULL_PIPELINE')", name="automation_depth_valid"),
        CheckConstraint("status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','SKIPPED','CANCELLED')", name="status_valid"),
        CheckConstraint("current_phase IN ('FETCH','ARTIFACT_SAVE','TECHNICAL_VALIDATE','SCHEMA_ANALYZE','SCHEMA_COMPARE','MAPPING','BUSINESS_VALIDATE','STAGING','COMMIT','SNAPSHOT','DELTA','INCIDENT')", name="phase_valid"),
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_source_schedules.id", ondelete="SET NULL"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    pipeline_code: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'PIP-' || lpad(nextval('supplier_source_pipeline_code_seq'::regclass)::text, 8, '0')"))
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    automation_depth: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    current_phase: Mapped[str] = mapped_column(String(32), nullable=False, default="FETCH")
    phase_results: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_source_artifacts.id", ondelete="RESTRICT"))
    active_schema_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"))
    analyzed_schema_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"))
    active_mapping_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_mapping_profiles.id", ondelete="RESTRICT"))
    acquisition_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_acquisition_runs.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_occurrence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}
    compatibility_report: Mapped[SupplierSchemaCompatibilityReport | None] = relationship(back_populates="pipeline_run", uselist=False)


class SupplierSchemaCompatibilityReport(UUIDMixin, Base):
    __tablename__ = "supplier_schema_compatibility_reports"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", name="uq_supplier_schema_compatibility_reports_pipeline_run_id"),
        Index("ix_supplier_schema_compatibility_reports_active_schema_created", "active_schema_profile_id", "created_at"),
        CheckConstraint("result IN ('COMPATIBLE','COMPATIBLE_WITH_WARNINGS','INCOMPATIBLE')", name="result_valid"),
        CheckConstraint("severity IN ('INFO','WARNING','ERROR','CRITICAL')", name="severity_valid"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_source_pipeline_runs.id", ondelete="RESTRICT"), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_source_artifacts.id", ondelete="RESTRICT"), nullable=False)
    active_schema_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"), nullable=False)
    analyzed_schema_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    changes: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pipeline_run: Mapped[SupplierSourcePipelineRun] = relationship(back_populates="compatibility_report")


__all__ = ["SupplierSchemaCompatibilityReport", "SupplierSourceArtifact", "SupplierSourcePipelineRun", "SupplierSourceSchedule"]
