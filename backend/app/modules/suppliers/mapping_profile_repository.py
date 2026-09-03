from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.mapping_profile_models import (
    SupplierMappingProfile,
    SupplierMappingRule,
)


class SupplierMappingRepository:
    """Mapping Profile queries and flush-only mutations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_profiles(
        self,
        schema_profile_id: uuid.UUID,
        *,
        active_only: bool = True,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierMappingProfile], int]:
        filters = [SupplierMappingProfile.schema_profile_id == schema_profile_id]
        if active_only:
            filters.append(SupplierMappingProfile.is_active.is_(True))
        if status is not None:
            filters.append(SupplierMappingProfile.status == status)
        total = await self.session.scalar(
            select(func.count(SupplierMappingProfile.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierMappingProfile)
            .where(*filters)
            .order_by(
                SupplierMappingProfile.version_number.desc(),
                SupplierMappingProfile.id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def get_profile(
        self,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierMappingProfile | None:
        query = select(SupplierMappingProfile).where(
            SupplierMappingProfile.id == mapping_profile_id,
            SupplierMappingProfile.schema_profile_id == schema_profile_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def next_version_number(
        self,
        schema_profile_id: uuid.UUID,
        name: str,
    ) -> int:
        value = await self.session.scalar(
            select(func.max(SupplierMappingProfile.version_number)).where(
                SupplierMappingProfile.schema_profile_id == schema_profile_id,
                func.lower(SupplierMappingProfile.name) == name.lower(),
            )
        )
        return int(value or 0) + 1

    async def active_profile(
        self,
        schema_profile_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierMappingProfile | None:
        query = select(SupplierMappingProfile).where(
            SupplierMappingProfile.schema_profile_id == schema_profile_id,
            SupplierMappingProfile.status == "ACTIVE",
            SupplierMappingProfile.is_active.is_(True),
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def archive_active_for_schema(
        self,
        schema_profile_id: uuid.UUID,
    ) -> None:
        profile = await self.active_profile(schema_profile_id, for_update=True)
        if profile is not None:
            profile.status = "ARCHIVED"
            profile.optimistic_version += 1
            await self.session.flush()

    async def add(self, entity: SupplierMappingProfile | SupplierMappingRule) -> None:
        self.session.add(entity)
        await self.session.flush()

    async def mutate(
        self,
        entity: SupplierMappingProfile | SupplierMappingRule,
        changes: dict[str, object],
    ) -> None:
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.flush()

    async def list_rules(
        self,
        mapping_profile_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[SupplierMappingRule]:
        filters = [SupplierMappingRule.mapping_profile_id == mapping_profile_id]
        if active_only:
            filters.append(SupplierMappingRule.is_active.is_(True))
        rows = await self.session.execute(
            select(SupplierMappingRule)
            .where(*filters)
            .order_by(SupplierMappingRule.priority, SupplierMappingRule.id)
        )
        return list(rows.scalars().all())

    async def get_rule(
        self,
        mapping_profile_id: uuid.UUID,
        rule_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierMappingRule | None:
        query = select(SupplierMappingRule).where(
            SupplierMappingRule.id == rule_id,
            SupplierMappingRule.mapping_profile_id == mapping_profile_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def rule_conflicts(
        self,
        mapping_profile_id: uuid.UUID,
        *,
        schema_field_id: uuid.UUID,
        target_attribute: str,
        priority: int,
        exclude_id: uuid.UUID | None = None,
    ) -> set[str]:
        filters = [
            SupplierMappingRule.mapping_profile_id == mapping_profile_id,
            SupplierMappingRule.is_active.is_(True),
        ]
        if exclude_id is not None:
            filters.append(SupplierMappingRule.id != exclude_id)
        rows = await self.session.execute(select(SupplierMappingRule).where(*filters))
        conflicts: set[str] = set()
        for rule in rows.scalars():
            if rule.schema_field_id == schema_field_id:
                conflicts.add("field")
            if rule.target_attribute.lower() == target_attribute.lower():
                conflicts.add("target")
            if rule.priority == priority:
                conflicts.add("priority")
        return conflicts


__all__ = ["SupplierMappingRepository"]
