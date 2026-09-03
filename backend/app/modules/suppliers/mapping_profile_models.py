from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.modules.suppliers.enums import MappingProfileStatus


class SupplierMappingProfile(UUIDMixin, TimestampMixin, Base):
    """One immutable version of field-to-catalog mapping metadata."""

    __tablename__ = "supplier_mapping_profiles"
    __table_args__ = (
        UniqueConstraint(
            "mapping_code", name="uq_supplier_mapping_profiles_mapping_code"
        ),
        Index(
            "uq_supplier_mapping_profiles_active_schema",
            "schema_profile_id",
            unique=True,
            postgresql_where=text("is_active AND status = 'ACTIVE'"),
        ),
        Index(
            "uq_supplier_mapping_profiles_schema_name_version",
            "schema_profile_id",
            func.lower(text("name")),
            "version_number",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_supplier_mapping_profiles_schema_status",
            "schema_profile_id",
            "status",
            "is_active",
        ),
        Index("ix_supplier_mapping_profiles_created_cursor", "created_at", "id"),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ARCHIVED')",
            name="status_valid",
        ),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("rule_count >= 0", name="rule_count_nonnegative"),
        CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name="inactive_not_active_status",
        ),
    )

    schema_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_schema_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mapping_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'MAP-' || lpad(nextval('supplier_mapping_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MappingProfileStatus.DRAFT.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rule_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    optimistic_version: Mapped[int] = mapped_column(
        "version",
        Integer,
        nullable=False,
        default=1,
    )
    __mapper_args__ = {
        "version_id_col": optimistic_version,
        "version_id_generator": False,
    }

    rules: Mapped[list[SupplierMappingRule]] = relationship(
        back_populates="profile",
        lazy="selectin",
        order_by="SupplierMappingRule.priority",
    )


class SupplierMappingRule(UUIDMixin, TimestampMixin, Base):
    """Stored mapping configuration; it never executes transformations."""

    __tablename__ = "supplier_mapping_rules"
    __table_args__ = (
        Index(
            "uq_supplier_mapping_rules_active_field",
            "mapping_profile_id",
            "schema_field_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_supplier_mapping_rules_active_target",
            "mapping_profile_id",
            func.lower(text("target_attribute")),
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_supplier_mapping_rules_active_priority",
            "mapping_profile_id",
            "priority",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_supplier_mapping_rules_profile_active",
            "mapping_profile_id",
            "is_active",
        ),
        Index("ix_supplier_mapping_rules_schema_field", "schema_field_id"),
        CheckConstraint("priority >= 1", name="priority_positive"),
        CheckConstraint(
            "transformation_type IN "
            "('NONE','COPY','DEFAULT_VALUE','CONSTANT','CONCAT','SPLIT','TRIM',"
            "'UPPERCASE','LOWERCASE','REPLACE','REGEX')",
            name="transformation_type_valid",
        ),
    )

    mapping_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_mapping_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schema_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_schema_fields.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_attribute: Mapped[str] = mapped_column(String(255), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_value: Mapped[str | None] = mapped_column(Text)
    transformation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    transformation_config: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    validation_rule: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    optimistic_version: Mapped[int] = mapped_column(
        "version",
        Integer,
        nullable=False,
        default=1,
    )
    __mapper_args__ = {
        "version_id_col": optimistic_version,
        "version_id_generator": False,
    }

    profile: Mapped[SupplierMappingProfile] = relationship(back_populates="rules")


__all__ = ["SupplierMappingProfile", "SupplierMappingRule"]
