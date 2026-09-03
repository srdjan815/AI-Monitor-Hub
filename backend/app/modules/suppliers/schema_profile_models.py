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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.suppliers.enums import SchemaProfileStatus


class SupplierSchemaProfile(UUIDMixin, TimestampMixin, Base):
    """One immutable structural version of a Source Connection schema."""

    __tablename__ = "supplier_schema_profiles"
    __table_args__ = (
        UniqueConstraint("schema_code", name="uq_supplier_schema_profiles_schema_code"),
        Index(
            "uq_supplier_schema_profiles_active_source",
            "source_connection_id",
            unique=True,
            postgresql_where=text("is_active AND status = 'ACTIVE'"),
        ),
        Index(
            "uq_supplier_schema_profiles_source_name_version",
            "source_connection_id",
            func.lower(text("name")),
            "version_number",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_supplier_schema_profiles_source_status",
            "source_connection_id",
            "status",
            "is_active",
        ),
        Index("ix_supplier_schema_profiles_created_cursor", "created_at", "id"),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ARCHIVED')",
            name="status_valid",
        ),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("field_count >= 0", name="field_count_nonnegative"),
        CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name="inactive_not_active_status",
        ),
    )

    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schema_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'SCH-' || lpad(nextval('supplier_schema_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SchemaProfileStatus.DRAFT.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detected_format: Mapped[str | None] = mapped_column(String(16))
    encoding: Mapped[str | None] = mapped_column(String(100))
    delimiter: Mapped[str | None] = mapped_column(String(10))
    root_path: Mapped[str | None] = mapped_column(String(500))
    record_path: Mapped[str | None] = mapped_column(String(500))
    baseline_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier_source_artifacts.id", ondelete="RESTRICT")
    )
    baseline_checksum: Mapped[str | None] = mapped_column(String(64))
    baseline_record_count: Mapped[int | None] = mapped_column(Integer)
    compatibility_policy: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    analysis_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    fields: Mapped[list[SupplierSchemaField]] = relationship(
        back_populates="profile",
        lazy="selectin",
        order_by="SupplierSchemaField.position",
    )


class SupplierSchemaField(UUIDMixin, TimestampMixin, Base):
    """Metadata for one incoming field; values are never parsed here."""

    __tablename__ = "supplier_schema_fields"
    __table_args__ = (
        Index(
            "uq_supplier_schema_fields_active_code",
            "schema_profile_id",
            func.lower(text("field_code")),
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_supplier_schema_fields_active_position",
            "schema_profile_id",
            "position",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_supplier_schema_fields_active_key",
            "schema_profile_id",
            unique=True,
            postgresql_where=text("is_active AND is_key"),
        ),
        Index(
            "uq_supplier_schema_fields_active_price",
            "schema_profile_id",
            unique=True,
            postgresql_where=text("is_active AND is_price"),
        ),
        Index(
            "ix_supplier_schema_fields_profile_active",
            "schema_profile_id",
            "is_active",
        ),
        CheckConstraint("position >= 1", name="position_positive"),
        CheckConstraint(
            "data_type IN "
            "('STRING','INTEGER','DECIMAL','BOOLEAN','DATE','DATETIME','TIME',"
            "'UUID','EMAIL','URL','PHONE','JSON','ENUM','BINARY')",
            name="data_type_valid",
        ),
        CheckConstraint(
            "NOT required OR NOT nullable",
            name="required_not_nullable",
        ),
        CheckConstraint(
            "max_length IS NULL OR max_length >= 1",
            name="max_length_positive",
        ),
        CheckConstraint(
            "precision IS NULL OR precision >= 1",
            name="precision_positive",
        ),
        CheckConstraint("scale IS NULL OR scale >= 0", name="scale_nonnegative"),
        CheckConstraint(
            "scale IS NULL OR precision IS NOT NULL",
            name="scale_requires_precision",
        ),
        CheckConstraint(
            "scale IS NULL OR scale <= precision",
            name="scale_within_precision",
        ),
    )

    schema_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_value: Mapped[str | None] = mapped_column(Text)
    max_length: Mapped[int | None] = mapped_column(Integer)
    precision: Mapped[int | None] = mapped_column(Integer)
    scale: Mapped[int | None] = mapped_column(Integer)
    example_value: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_identifier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_quantity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_currency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    profile: Mapped[SupplierSchemaProfile] = relationship(back_populates="fields")


__all__ = ["SupplierSchemaField", "SupplierSchemaProfile"]
