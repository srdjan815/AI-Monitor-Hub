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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierProductPresence(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_product_presence"
    __table_args__ = (
        UniqueConstraint(
            "source_connection_id",
            "product_code_normalized",
            "identity_key",
            name="uq_supplier_product_presence_source_product_identity",
        ),
        Index(
            "ix_supplier_product_presence_identity_seen", "identity_key", "last_seen_at"
        ),
        Index(
            "ix_supplier_product_presence_supplier_seen", "supplier_id", "last_seen_at"
        ),
        Index(
            "ix_supplier_product_presence_current",
            "is_currently_offered",
            "last_seen_at",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="CASCADE"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(String(500), nullable=False)
    product_code_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(600), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(32))
    product_name: Mapped[str | None] = mapped_column(String(2000))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    is_currently_offered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )


class EolExportBatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "eol_export_batches"
    __table_args__ = (
        UniqueConstraint("batch_code", name="uq_eol_export_batches_batch_code"),
        UniqueConstraint(
            "idempotency_key", name="uq_eol_export_batches_idempotency_key"
        ),
        CheckConstraint(
            "status IN ('PREPARED','PROCESSING','PARTIALLY_SUCCEEDED','SUCCEEDED','FAILED','CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint(
            "inactivity_months BETWEEN 1 AND 12", name="inactivity_months_valid"
        ),
        Index("ix_eol_export_batches_status_created", "status", "created_at"),
    )

    batch_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'EOL-' || lpad(nextval('eol_export_batch_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PREPARED")
    inactivity_months: Mapped[int] = mapped_column(Integer, nullable=False)
    target_systems: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_message: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EolExportItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "eol_export_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "identity_key", name="uq_eol_export_items_batch_identity"
        ),
        CheckConstraint(
            "status IN ('PENDING','SUCCEEDED','FAILED','SKIPPED')", name="status_valid"
        ),
        Index("ix_eol_export_items_batch_status", "batch_id", "status"),
        Index(
            "uq_eol_export_items_pending_identity",
            "identity_key",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eol_export_batches.id", ondelete="RESTRICT"), nullable=False
    )
    identity_key: Mapped[str] = mapped_column(String(600), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(32))
    product_name: Mapped[str | None] = mapped_column(String(2000))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    target_results: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    failure_message: Mapped[str | None] = mapped_column(Text)


__all__ = ["EolExportBatch", "EolExportItem", "SupplierProductPresence"]
