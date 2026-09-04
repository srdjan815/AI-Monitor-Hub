from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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


class MonitorCurrencySetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "monitor_currency_settings"
    __table_args__ = (
        UniqueConstraint(
            "singleton_key", name="uq_monitor_currency_settings_singleton"
        ),
        CheckConstraint("singleton_key", name="singleton_true"),
        CheckConstraint("currency_code = 'RSD'", name="currency_rsd"),
        CheckConstraint("rate_to_rsd = 1", name="rate_one"),
    )
    singleton_key: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False, default="RSD", server_default="RSD"
    )
    rate_to_rsd: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, default=Decimal("1"), server_default="1"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class SupplierCurrencySetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_currency_settings"
    __table_args__ = (
        Index(
            "uq_supplier_currency_settings_active",
            "supplier_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_supplier_currency_settings_currency_active",
            "currency_code",
            "is_active",
        ),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_iso_format"),
        CheckConstraint(
            "currency_source IN ('CONFIGURED','PRICE_LIST')",
            name="currency_source_valid",
        ),
        CheckConstraint(
            "rate_mode IN ('FIXED','MANUAL','AUTOMATIC')", name="rate_mode_valid"
        ),
        CheckConstraint("max_rate_age_hours BETWEEN 1 AND 8760", name="max_age_valid"),
        CheckConstraint(
            "currency_code <> 'RSD' OR rate_mode = 'FIXED'", name="rsd_rate_fixed"
        ),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="CONFIGURED"
    )
    rate_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    automatic_source_url: Mapped[str | None] = mapped_column(String(2000))
    max_rate_age_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=48, server_default="48"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class SupplierExchangeRate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "currency_setting_id",
            "effective_at",
            name="uq_supplier_exchange_rates_setting_effective",
        ),
        Index(
            "ix_supplier_exchange_rates_lookup",
            "currency_setting_id",
            "status",
            "effective_at",
        ),
        CheckConstraint("rate_to_rsd > 0", name="rate_positive"),
        CheckConstraint("status IN ('VERIFIED','REJECTED')", name="status_valid"),
        CheckConstraint(
            "source_type IN ('FIXED','MANUAL','AUTOMATIC')", name="source_type_valid"
        ),
    )
    currency_setting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_currency_settings.id", ondelete="RESTRICT"), nullable=False
    )
    rate_to_rsd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="VERIFIED")
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_checksum: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)


class SupplierCurrencyEvent(UUIDMixin, Base):
    __tablename__ = "supplier_currency_events"
    __table_args__ = (
        Index(
            "ix_supplier_currency_events_supplier_created",
            "supplier_id",
            "created_at",
            "id",
        ),
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    currency_setting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_currency_settings.id", ondelete="RESTRICT")
    )
    exchange_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_exchange_rates.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


__all__ = [
    "MonitorCurrencySetting",
    "SupplierCurrencyEvent",
    "SupplierCurrencySetting",
    "SupplierExchangeRate",
]
