from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierIncident(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_incidents"
    __table_args__ = (
        UniqueConstraint("incident_code", name="uq_supplier_incidents_incident_code"),
        Index(
            "uq_supplier_incidents_active_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where=text(
                "status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','SUPPRESSED')"
            ),
        ),
        Index("ix_supplier_incidents_supplier_status", "supplier_id", "status"),
        Index("ix_supplier_incidents_source_status", "source_connection_id", "status"),
        Index(
            "ix_supplier_incidents_classification",
            "source_domain",
            "incident_type",
            "severity",
            "priority",
        ),
        Index("ix_supplier_incidents_assignment_due", "assigned_user_id", "due_at"),
        Index("ix_supplier_incidents_detected", "last_detected_at", "created_at"),
        Index("ix_supplier_incidents_correlation", "correlation_key"),
        Index("ix_supplier_incidents_acquisition", "source_acquisition_run_id"),
        Index("ix_supplier_incidents_snapshot", "source_snapshot_id"),
        Index("ix_supplier_incidents_delta", "source_delta_run_id"),
        CheckConstraint(
            "severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')",
            name="severity_valid",
        ),
        CheckConstraint("priority IN ('P4','P3','P2','P1')", name="priority_valid"),
        CheckConstraint(
            "status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','RESOLVED','DISMISSED','SUPPRESSED')",
            name="status_valid",
        ),
        CheckConstraint("occurrence_count >= 1", name="occurrence_count_positive"),
    )
    incident_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'INC-' || lpad(nextval('supplier_incident_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="RESTRICT")
    )
    incident_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_key: Mapped[str | None] = mapped_column(String(255))
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppression_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_user_id: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(255))
    resolution_code: Mapped[str | None] = mapped_column(String(100))
    resolution_summary: Mapped[str | None] = mapped_column(String(1000))
    source_acquisition_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_acquisition_runs.id", ondelete="RESTRICT")
    )
    source_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_snapshots.id", ondelete="RESTRICT")
    )
    source_snapshot_archive_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_snapshot_archive_operations.id", ondelete="RESTRICT")
    )
    source_delta_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_delta_runs.id", ondelete="RESTRICT")
    )
    source_delta_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_delta_items.id", ondelete="SET NULL")
    )
    source_row_error_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_acquisition_issues.id", ondelete="SET NULL")
    )
    sanitized_context: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SupplierIncidentEvent(UUIDMixin, Base):
    __tablename__ = "supplier_incident_events"
    __table_args__ = (
        Index(
            "ix_supplier_incident_events_incident_created",
            "incident_id",
            "created_at",
            "id",
        ),
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_incidents.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(20))
    current_status: Mapped[str | None] = mapped_column(String(20))
    event_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SupplierIncidentComment(UUIDMixin, Base):
    __tablename__ = "supplier_incident_comments"
    __table_args__ = (
        Index(
            "ix_supplier_incident_comments_incident_created",
            "incident_id",
            "created_at",
            "id",
        ),
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_incidents.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SupplierIncidentLink(UUIDMixin, Base):
    __tablename__ = "supplier_incident_links"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "related_incident_id",
            "relationship_type",
            name="uq_supplier_incident_links_relation",
        ),
        Index("ix_supplier_incident_links_related", "related_incident_id"),
        CheckConstraint("incident_id <> related_incident_id", name="not_self"),
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_incidents.id", ondelete="RESTRICT"), nullable=False
    )
    related_incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_incidents.id", ondelete="RESTRICT"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SupplierIncidentRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_incident_rules"
    __table_args__ = (
        UniqueConstraint("rule_code", name="uq_supplier_incident_rules_rule_code"),
        Index(
            "ix_supplier_incident_rules_scope",
            "source_connection_id",
            "supplier_id",
            "source_domain",
            "signal_code",
            "enabled",
        ),
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_code: Mapped[str | None] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    minimum_severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default="INFO"
    )
    resulting_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    default_priority: Mapped[str] = mapped_column(String(4), nullable=False)
    threshold_configuration: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    deduplication_window_hours: Mapped[int | None] = mapped_column(Integer)
    auto_reopen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    suppression_compatible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE")
    )
    source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="CASCADE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


__all__ = [
    "SupplierIncident",
    "SupplierIncidentComment",
    "SupplierIncidentEvent",
    "SupplierIncidentLink",
    "SupplierIncidentRule",
]
