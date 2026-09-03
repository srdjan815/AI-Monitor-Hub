from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierDeltaRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_delta_runs"
    __table_args__ = (
        UniqueConstraint("delta_code", name="uq_supplier_delta_runs_delta_code"),
        Index("ix_supplier_delta_runs_supplier_created", "supplier_id", "created_at"),
        Index("ix_supplier_delta_runs_source_created", "source_connection_id", "created_at"),
        Index("ix_supplier_delta_runs_previous_snapshot", "previous_snapshot_id"),
        Index("ix_supplier_delta_runs_current_snapshot", "current_snapshot_id"),
        Index("ix_supplier_delta_runs_status_created", "status", "created_at"),
        Index(
            "uq_supplier_delta_runs_successful_pair",
            "previous_snapshot_id", "current_snapshot_id", "comparison_version",
            unique=True, postgresql_where=text("status = 'SUCCEEDED'"),
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint("comparison_version >= 1", name="comparison_version_positive"),
    )

    delta_code: Mapped[str] = mapped_column(
        String(50), nullable=False,
        server_default=text(
            "'DLT-' || lpad(nextval('supplier_delta_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    source_connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False)
    previous_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_snapshots.id", ondelete="RESTRICT"), nullable=False)
    current_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_snapshots.id", ondelete="RESTRICT"), nullable=False)
    previous_snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    current_snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_schema_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"), nullable=False)
    current_schema_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"), nullable=False)
    previous_mapping_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_mapping_profiles.id", ondelete="RESTRICT"), nullable=False)
    current_mapping_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_mapping_profiles.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    comparison_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    total_previous_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_current_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    modified_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_increased_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_decreased_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_unchanged_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_increased_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_decreased_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    became_available_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    became_unavailable_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_changed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    identifier_changed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomaly_signals: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SupplierDeltaItem(UUIDMixin, Base):
    __tablename__ = "supplier_delta_items"
    __table_args__ = (
        Index("ix_supplier_delta_items_run_type", "delta_run_id", "change_type"),
        Index("ix_supplier_delta_items_matching_key", "delta_run_id", "matching_key_type", "matching_key_value"),
        Index("ix_supplier_delta_items_flags", "delta_run_id", "has_price_change", "has_stock_change", "has_image_change", "has_identifier_change"),
    )
    delta_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_delta_runs.id", ondelete="CASCADE"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    matching_key_type: Mapped[str] = mapped_column(String(32), nullable=False)
    matching_key_value: Mapped[str] = mapped_column(Text, nullable=False)
    previous_snapshot_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_snapshot_items.id", ondelete="SET NULL"))
    current_snapshot_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_snapshot_items.id", ondelete="SET NULL"))
    previous_item_fingerprint: Mapped[str | None] = mapped_column(String(64))
    current_item_fingerprint: Mapped[str | None] = mapped_column(String(64))
    changed_field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_price_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_stock_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_image_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_identifier_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    change_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    anomaly_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class SupplierDeltaFieldChange(UUIDMixin, Base):
    __tablename__ = "supplier_delta_field_changes"
    __table_args__ = (Index("ix_supplier_delta_field_changes_item_path", "delta_item_id", "field_path"),)
    delta_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_delta_items.id", ondelete="CASCADE"), nullable=False)
    field_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    field_role: Mapped[str | None] = mapped_column(String(50))
    change_type: Mapped[str] = mapped_column(String(24), nullable=False)
    previous_value_type: Mapped[str | None] = mapped_column(String(32))
    current_value_type: Mapped[str | None] = mapped_column(String(32))
    previous_value_hash: Mapped[str | None] = mapped_column(String(64))
    current_value_hash: Mapped[str | None] = mapped_column(String(64))
    previous_value_preview: Mapped[str | None] = mapped_column(String(500))
    current_value_preview: Mapped[str | None] = mapped_column(String(500))
    previous_numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    current_numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    absolute_numeric_change: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    percentage_numeric_change: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


__all__ = ["SupplierDeltaFieldChange", "SupplierDeltaItem", "SupplierDeltaRun"]
