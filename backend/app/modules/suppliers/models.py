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
from app.modules.suppliers.enums import (
    SupplierContactType,
    SupplierSourceStatus,
    SupplierStatus,
)


class Supplier(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("supplier_code", name="uq_suppliers_supplier_code"),
        Index(
            "uq_suppliers_active_tax_identifier",
            "tax_identifier",
            unique=True,
            postgresql_where=text("is_active AND tax_identifier IS NOT NULL"),
        ),
        Index(
            "uq_suppliers_active_registration_number",
            "registration_number",
            unique=True,
            postgresql_where=text("is_active AND registration_number IS NOT NULL"),
        ),
        Index("ix_suppliers_active_status", "is_active", "status"),
        Index("ix_suppliers_company_name_id", "company_name", "id"),
        Index("ix_suppliers_created_cursor", "created_at", "id"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')",
            name="status_valid",
        ),
        CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name="archived_not_operationally_active",
        ),
    )

    supplier_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'SUP-' || lpad(nextval('supplier_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    tax_identifier: Mapped[str | None] = mapped_column(String(120))
    registration_number: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SupplierStatus.ACTIVE.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    contacts: Mapped[list[SupplierContact]] = relationship(
        back_populates="supplier",
        lazy="selectin",
    )


class SupplierContact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_contacts"
    __table_args__ = (
        Index(
            "uq_supplier_contacts_active_primary_type",
            "supplier_id",
            "contact_type",
            unique=True,
            postgresql_where=text("is_active AND is_primary"),
        ),
        Index(
            "ix_supplier_contacts_supplier_active",
            "supplier_id",
            "is_active",
        ),
        Index(
            "ix_supplier_contacts_order",
            "supplier_id",
            "is_primary",
            "contact_type",
            "name",
            "id",
        ),
        CheckConstraint(
            "contact_type IN "
            "('GENERAL', 'TECHNICAL', 'COMMERCIAL', 'BILLING', 'OTHER')",
            name="contact_type_valid",
        ),
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="email_or_phone_required",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    contact_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SupplierContactType.GENERAL.value,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    supplier: Mapped[Supplier] = relationship(back_populates="contacts")


class SupplierSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_sources"
    __table_args__ = (
        UniqueConstraint("source_code", name="uq_supplier_sources_source_code"),
        Index(
            "uq_supplier_sources_active_supplier_name",
            "supplier_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_supplier_sources_supplier_active",
            "supplier_id",
            "is_active",
        ),
        Index(
            "ix_supplier_sources_supplier_type_status",
            "supplier_id",
            "source_type",
            "status",
        ),
        Index("ix_supplier_sources_name_id", "supplier_id", "name", "id"),
        Index("ix_supplier_sources_created_cursor", "created_at", "id"),
        CheckConstraint(
            "source_type IN "
            "('API','CSV','EXCEL','XML','FTP','SFTP','HTTP',"
            "'GOOGLE_DRIVE','EMAIL','MANUAL_UPLOAD')",
            name="source_type_valid",
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','INACTIVE','ERROR')",
            name="status_valid",
        ),
        CheckConstraint(
            "is_active OR status <> 'ACTIVE'",
            name="archived_not_operationally_active",
        ),
        CheckConstraint(
            "last_validation_status IS NULL OR "
            "last_validation_status IN ('VALID','INVALID')",
            name="validation_status_valid",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text(
            "'SRC-' || lpad(nextval('supplier_source_code_seq'::regclass)::text, 6, '0')"
        ),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SupplierSourceStatus.DRAFT.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    secret_reference: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(String(2000))
    portal_supplier_code: Mapped[str | None] = mapped_column(String(128))
    last_validation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validation_status: Mapped[str | None] = mapped_column(String(32))
    last_validation_message: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    @property
    def has_secret_reference(self) -> bool:
        return self.secret_reference is not None


__all__ = ["Supplier", "SupplierContact", "SupplierSource"]
