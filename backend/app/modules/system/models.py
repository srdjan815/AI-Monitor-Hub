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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SystemCleanupAudit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "system_cleanup_audit"
    __table_args__ = (
        Index("ix_system_cleanup_audit_created_at", "created_at"),
        CheckConstraint(
            "status IN ('SUCCEEDED','FAILED','NO_CHANGES')", name="status_valid"
        ),
        CheckConstraint("deleted_files >= 0", name="deleted_files_nonnegative"),
        CheckConstraint("deleted_bytes >= 0", name="deleted_bytes_nonnegative"),
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    older_than_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    deleted_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class ArtifactArchiveSetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "artifact_archive_settings"
    __table_args__ = (
        UniqueConstraint("setting_key", name="uq_artifact_archive_settings_key"),
        CheckConstraint("backend_type IN ('MOUNT')", name="backend_type_valid"),
        CheckConstraint(
            "local_retention_days BETWEEN 1 AND 3650", name="local_retention_valid"
        ),
    )
    setting_key: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PRIMARY"
    )
    backend_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MOUNT"
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    local_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(20))
    last_test_message: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class ArtifactArchiveTransfer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "artifact_archive_transfers"
    __table_args__ = (
        UniqueConstraint("artifact_id", name="uq_artifact_archive_transfers_artifact"),
        CheckConstraint(
            "status IN ('PENDING','VERIFIED','FAILED')", name="status_valid"
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_source_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    setting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_archive_settings.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    archive_reference: Mapped[str | None] = mapped_column(String(1000))
    verified_checksum: Mapped[str | None] = mapped_column(String(64))
    verified_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(500))


__all__ = ["ArtifactArchiveSetting", "ArtifactArchiveTransfer", "SystemCleanupAudit"]
