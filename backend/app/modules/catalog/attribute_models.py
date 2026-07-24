from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AttributeGroup(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_groups"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_attribute_groups_slug"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_attribute_groups_order", "sort_order", "slug"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class AttributeOption(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_options"
    __table_args__ = (
        UniqueConstraint(
            "attribute_definition_id",
            "canonical_value",
            name="uq_attribute_options_canonical",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index(
            "ix_attribute_options_order",
            "attribute_definition_id",
            "sort_order",
        ),
    )

    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_value: Mapped[str] = mapped_column(String(500), nullable=False)
    display_value: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    option_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    aliases: Mapped[list[AttributeOptionAlias]] = relationship(
        back_populates="option", cascade="all, delete-orphan", lazy="selectin"
    )


class AttributeOptionAlias(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_option_aliases"
    __table_args__ = (
        UniqueConstraint(
            "attribute_definition_id",
            "normalized_alias",
            name="uq_attribute_option_aliases_normalized",
        ),
    )

    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_options.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(500), nullable=False)
    option: Mapped[AttributeOption] = relationship(back_populates="aliases")


class AttributeNormalizationRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_normalization_rules"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="priority_nonnegative"),
        Index(
            "ix_attribute_normalization_rules_order",
            "attribute_definition_id",
            "priority",
        ),
    )

    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    replacement: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text)


class ProductAttributeValue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_attribute_values"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR "
            "(confidence_score >= 0 AND confidence_score <= 1)",
            name="confidence_range",
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        Index("ix_product_attribute_values_product", "product_id"),
        Index(
            "ix_product_attribute_values_attribute",
            "attribute_definition_id",
        ),
        Index(
            "ix_product_attribute_values_review",
            "validation_status",
            "approval_status",
        ),
        Index("ix_product_attribute_values_numeric", "numeric_value"),
        Index("ix_product_attribute_values_text", "text_value"),
        Index(
            "ix_product_attribute_values_single",
            "product_id",
            "attribute_definition_id",
            unique=True,
            postgresql_where="is_active AND value_key = 'single'",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    value_key: Mapped[str] = mapped_column(String(64), nullable=False, default="single")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    canonical_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    display_value: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(80))
    text_value: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    date_value: Mapped[date | None] = mapped_column(Date)
    datetime_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    json_value: Mapped[Any | None] = mapped_column(JSONB)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_message: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_by: Mapped[str | None] = mapped_column(String(255))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_reason: Mapped[str | None] = mapped_column(Text)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class ProductAttributeValueHistory(UUIDMixin, Base):
    __tablename__ = "product_attribute_value_history"
    __table_args__ = (
        Index(
            "ix_product_attribute_history_product",
            "product_id",
            "occurred_at",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_attribute_value_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_attribute_values.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_raw_value: Mapped[Any | None] = mapped_column(JSONB)
    previous_canonical_value: Mapped[Any | None] = mapped_column(JSONB)
    new_raw_value: Mapped[Any | None] = mapped_column(JSONB)
    new_canonical_value: Mapped[Any | None] = mapped_column(JSONB)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    actor_identifier: Mapped[str | None] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class AttributeChangeEvent(UUIDMixin, Base):
    __tablename__ = "attribute_change_events"
    __table_args__ = (
        Index("ix_attribute_change_events_product", "product_id", "cursor"),
        Index("ix_attribute_change_events_occurred", "occurred_at"),
    )

    cursor: Mapped[int] = mapped_column(
        BigInteger, Identity(), nullable=False, unique=True
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
