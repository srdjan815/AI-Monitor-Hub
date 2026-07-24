from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.models import Supplier, SupplierContact


def _contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class SupplierRepository:
    """Supplier Administration SQL and flush-only mutation boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_suppliers(
        self,
        *,
        active_only: bool = True,
        status: str | None = None,
        company_name: str | None = None,
        supplier_code: str | None = None,
        tax_identifier: str | None = None,
        registration_number: str | None = None,
        limit: int = 100,
        offset: int = 0,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Supplier], int]:
        filters: list[ColumnElement[bool]] = []
        if active_only:
            filters.append(Supplier.is_active.is_(True))
        if status is not None:
            filters.append(Supplier.status == status)
        if company_name is not None:
            filters.append(
                Supplier.company_name.ilike(_contains(company_name), escape="\\")
            )
        if supplier_code is not None:
            filters.append(
                Supplier.supplier_code.ilike(_contains(supplier_code), escape="\\")
            )
        if tax_identifier is not None:
            filters.append(Supplier.tax_identifier == tax_identifier)
        if registration_number is not None:
            filters.append(Supplier.registration_number == registration_number)
        if snapshot_at is not None:
            filters.append(Supplier.created_at <= snapshot_at)

        count = await self.session.scalar(
            select(func.count(Supplier.id)).where(*filters)
        )
        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    Supplier.created_at < after_at,
                    and_(
                        Supplier.created_at == after_at,
                        Supplier.id < after_id,
                    ),
                )
            )

        query = select(Supplier).where(*page_filters)
        if snapshot_at is None and after is None:
            query = query.order_by(Supplier.company_name.asc(), Supplier.id.asc())
        else:
            query = query.order_by(Supplier.created_at.desc(), Supplier.id.desc())
        rows = await self.session.execute(query.limit(limit).offset(offset))
        return list(rows.scalars().all()), int(count or 0)

    async def get_supplier(
        self,
        supplier_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Supplier | None:
        query = select(Supplier).where(Supplier.id == supplier_id)
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def get_supplier_by_tax_identifier(
        self,
        tax_identifier: str,
    ) -> Supplier | None:
        return (
            await self.session.execute(
                select(Supplier).where(
                    Supplier.tax_identifier == tax_identifier,
                    Supplier.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def get_supplier_by_registration_number(
        self,
        registration_number: str,
    ) -> Supplier | None:
        return (
            await self.session.execute(
                select(Supplier).where(
                    Supplier.registration_number == registration_number,
                    Supplier.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def create_supplier(self, supplier: Supplier) -> Supplier:
        self.session.add(supplier)
        await self.session.flush()
        return supplier

    async def update_supplier(
        self,
        supplier: Supplier,
        changes: dict[str, object],
    ) -> Supplier:
        for field, value in changes.items():
            setattr(supplier, field, value)
        await self.session.flush()
        return supplier

    async def list_contacts(
        self,
        supplier_id: uuid.UUID,
        *,
        active_only: bool = True,
        contact_type: str | None = None,
        is_primary: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierContact], int]:
        filters: list[ColumnElement[bool]] = [
            SupplierContact.supplier_id == supplier_id
        ]
        if active_only:
            filters.append(SupplierContact.is_active.is_(True))
        if contact_type is not None:
            filters.append(SupplierContact.contact_type == contact_type)
        if is_primary is not None:
            filters.append(SupplierContact.is_primary.is_(is_primary))
        count = await self.session.scalar(
            select(func.count(SupplierContact.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierContact)
            .where(*filters)
            .order_by(
                SupplierContact.is_primary.desc(),
                SupplierContact.contact_type.asc(),
                SupplierContact.name.asc(),
                SupplierContact.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars().all()), int(count or 0)

    async def get_contact(
        self,
        supplier_id: uuid.UUID,
        contact_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierContact | None:
        query = select(SupplierContact).where(
            SupplierContact.id == contact_id,
            SupplierContact.supplier_id == supplier_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def get_active_primary_contact(
        self,
        supplier_id: uuid.UUID,
        contact_type: str,
    ) -> SupplierContact | None:
        return (
            await self.session.execute(
                select(SupplierContact).where(
                    SupplierContact.supplier_id == supplier_id,
                    SupplierContact.contact_type == contact_type,
                    SupplierContact.is_primary.is_(True),
                    SupplierContact.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def create_contact(self, contact: SupplierContact) -> SupplierContact:
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def update_contact(
        self,
        contact: SupplierContact,
        changes: dict[str, object],
    ) -> SupplierContact:
        for field, value in changes.items():
            setattr(contact, field, value)
        await self.session.flush()
        return contact


__all__ = ["SupplierRepository"]
