from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.schema_profile_models import (
    SupplierSchemaField,
    SupplierSchemaProfile,
)


class SupplierSchemaRepository:
    """Schema Profile queries and flush-only mutations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_profiles(
        self,
        source_id: uuid.UUID,
        *,
        active_only: bool = True,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierSchemaProfile], int]:
        filters = [SupplierSchemaProfile.source_connection_id == source_id]
        if active_only:
            filters.append(SupplierSchemaProfile.is_active.is_(True))
        if status is not None:
            filters.append(SupplierSchemaProfile.status == status)
        total = await self.session.scalar(
            select(func.count(SupplierSchemaProfile.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierSchemaProfile)
            .where(*filters)
            .order_by(
                SupplierSchemaProfile.version_number.desc(),
                SupplierSchemaProfile.id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def get_profile(
        self,
        source_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSchemaProfile | None:
        query = select(SupplierSchemaProfile).where(
            SupplierSchemaProfile.id == profile_id,
            SupplierSchemaProfile.source_connection_id == source_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def next_version_number(self, source_id: uuid.UUID, name: str) -> int:
        value = await self.session.scalar(
            select(func.max(SupplierSchemaProfile.version_number)).where(
                SupplierSchemaProfile.source_connection_id == source_id,
                func.lower(SupplierSchemaProfile.name) == name.lower(),
            )
        )
        return int(value or 0) + 1

    async def active_profile(
        self,
        source_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSchemaProfile | None:
        query = select(SupplierSchemaProfile).where(
            SupplierSchemaProfile.source_connection_id == source_id,
            SupplierSchemaProfile.status == "ACTIVE",
            SupplierSchemaProfile.is_active.is_(True),
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def add(self, entity: SupplierSchemaProfile | SupplierSchemaField) -> None:
        self.session.add(entity)
        await self.session.flush()

    async def mutate(
        self,
        entity: SupplierSchemaProfile | SupplierSchemaField,
        changes: dict[str, object],
    ) -> None:
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.flush()

    async def list_fields(
        self,
        profile_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[SupplierSchemaField]:
        filters = [SupplierSchemaField.schema_profile_id == profile_id]
        if active_only:
            filters.append(SupplierSchemaField.is_active.is_(True))
        rows = await self.session.execute(
            select(SupplierSchemaField)
            .where(*filters)
            .order_by(SupplierSchemaField.position, SupplierSchemaField.id)
        )
        return list(rows.scalars().all())

    async def deactivate_fields(self, profile_id: uuid.UUID) -> None:
        for field in await self.list_fields(profile_id):
            field.is_active = False
            field.version += 1
        await self.session.flush()

    async def get_field(
        self,
        profile_id: uuid.UUID,
        field_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSchemaField | None:
        query = select(SupplierSchemaField).where(
            SupplierSchemaField.id == field_id,
            SupplierSchemaField.schema_profile_id == profile_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def field_conflicts(
        self,
        profile_id: uuid.UUID,
        *,
        code: str,
        position: int,
        is_key: bool,
        is_price: bool,
        exclude_id: uuid.UUID | None = None,
    ) -> set[str]:
        filters = [
            SupplierSchemaField.schema_profile_id == profile_id,
            SupplierSchemaField.is_active.is_(True),
        ]
        if exclude_id is not None:
            filters.append(SupplierSchemaField.id != exclude_id)
        rows = await self.session.execute(select(SupplierSchemaField).where(*filters))
        conflicts: set[str] = set()
        for row in rows.scalars():
            if row.field_code.lower() == code.lower():
                conflicts.add("code")
            if row.position == position:
                conflicts.add("position")
            if is_key and row.is_key:
                conflicts.add("key")
            if is_price and row.is_price:
                conflicts.add("price")
        return conflicts


__all__ = ["SupplierSchemaRepository"]
