from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierDataRetentionPolicy(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_data_retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "source_connection_id", name="uq_supplier_retention_policy_source"
        ),
        CheckConstraint(
            "staging_retention_days BETWEEN 1 AND 3650",
            name="staging_retention_days_valid",
        ),
        CheckConstraint(
            "snapshot_online_days BETWEEN 1 AND 3650",
            name="snapshot_online_days_valid",
        ),
        CheckConstraint(
            "minimum_online_snapshots BETWEEN 2 AND 100",
            name="minimum_online_snapshots_valid",
        ),
        CheckConstraint(
            "cleanup_batch_size BETWEEN 1 AND 10000",
            name="cleanup_batch_size_valid",
        ),
    )

    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staging_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_online_days: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_online_snapshots: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class SupplierPriceObservation(UUIDMixin, Base):
    __tablename__ = "supplier_price_observations"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_item_id", name="uq_supplier_price_observations_snapshot_item"
        ),
        Index(
            "ix_supplier_price_observations_supplier_observed",
            "supplier_id",
            "observed_at",
            "id",
        ),
        Index(
            "ix_supplier_price_observations_source_product_observed",
            "source_connection_id",
            "product_code_normalized",
            "observed_at",
        ),
        Index("ix_supplier_price_observations_ean_observed", "ean", "observed_at"),
        Index(
            "ix_supplier_price_observations_category_observed",
            "category_name",
            "observed_at",
        ),
        CheckConstraint("price_rsd >= 0", name="price_rsd_nonnegative"),
        CheckConstraint(
            "source_price IS NULL OR source_price >= 0",
            name="source_price_nonnegative",
        ),
        CheckConstraint(
            "exchange_rate_to_rsd IS NULL OR exchange_rate_to_rsd > 0",
            name="exchange_rate_positive",
        ),
        CheckConstraint("stock IS NULL OR stock >= 0", name="stock_nonnegative"),
    )

    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_snapshots.id", ondelete="SET NULL")
    )
    snapshot_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_snapshot_items.id", ondelete="SET NULL")
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="CASCADE"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(Text, nullable=False)
    product_code_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    identity_key: Mapped[str] = mapped_column(Text, nullable=False)
    ean: Mapped[str | None] = mapped_column(Text)
    product_name: Mapped[str | None] = mapped_column(Text)
    category_name: Mapped[str | None] = mapped_column(Text)
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    exchange_rate_to_rsd: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    price_rsd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    stock: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    item_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SupplierRetentionRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_retention_runs"
    __table_args__ = (
        Index(
            "ix_supplier_retention_runs_policy_created",
            "policy_id",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "status IN ('PREVIEWED','RUNNING','SUCCEEDED','FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "candidate_staging_rows >= 0 AND candidate_snapshots >= 0 "
            "AND preserved_observations >= 0 AND deleted_staging_rows >= 0 "
            "AND offloaded_snapshot_items >= 0",
            name="counts_nonnegative",
        ),
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_data_retention_policies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    staging_cutoff: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    snapshot_cutoff: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    candidate_staging_rows: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    candidate_snapshots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preserved_observations: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    deleted_staging_rows: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    offloaded_snapshot_items: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)


__all__ = [
    "SupplierDataRetentionPolicy",
    "SupplierPriceObservation",
    "SupplierRetentionRun",
]
