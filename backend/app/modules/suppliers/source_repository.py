from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.models import SupplierSource


def _contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class SupplierSourceRepository:
    """Source Connection queries and flush-only mutations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sources(
        self,
        supplier_id: uuid.UUID,
        *,
        active_only: bool = True,
        source_type: str | None = None,
        status: str | None = None,
        name: str | None = None,
        source_code: str | None = None,
        limit: int = 100,
        offset: int = 0,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[SupplierSource], int]:
        filters: list[ColumnElement[bool]] = [SupplierSource.supplier_id == supplier_id]
        if active_only:
            filters.append(SupplierSource.is_active.is_(True))
        if source_type is not None:
            filters.append(SupplierSource.source_type == source_type)
        if status is not None:
            filters.append(SupplierSource.status == status)
        if name is not None:
            filters.append(SupplierSource.name.ilike(_contains(name), escape="\\"))
        if source_code is not None:
            filters.append(
                SupplierSource.source_code.ilike(_contains(source_code), escape="\\")
            )
        if snapshot_at is not None:
            filters.append(SupplierSource.created_at <= snapshot_at)
        total = await self.session.scalar(
            select(func.count(SupplierSource.id)).where(*filters)
        )
        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    SupplierSource.created_at < after_at,
                    and_(
                        SupplierSource.created_at == after_at,
                        SupplierSource.id < after_id,
                    ),
                )
            )
        query = select(SupplierSource).where(*page_filters)
        if snapshot_at is None and after is None:
            query = query.order_by(SupplierSource.name, SupplierSource.id)
        else:
            query = query.order_by(
                SupplierSource.created_at.desc(),
                SupplierSource.id.desc(),
            )
        rows = await self.session.execute(query.limit(limit).offset(offset))
        return list(rows.scalars().all()), int(total or 0)

    async def get_source(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSource | None:
        query = select(SupplierSource).where(
            SupplierSource.id == source_id,
            SupplierSource.supplier_id == supplier_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def get_active_by_name(
        self,
        supplier_id: uuid.UUID,
        name: str,
    ) -> SupplierSource | None:
        return (
            await self.session.execute(
                select(SupplierSource).where(
                    SupplierSource.supplier_id == supplier_id,
                    func.lower(SupplierSource.name) == name.lower(),
                    SupplierSource.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    async def create_source(self, source: SupplierSource) -> SupplierSource:
        self.session.add(source)
        await self.session.flush()
        return source

    async def update_source(
        self,
        source: SupplierSource,
        changes: dict[str, object],
    ) -> SupplierSource:
        for field, value in changes.items():
            setattr(source, field, value)
        await self.session.flush()
        return source


__all__ = ["SupplierSourceRepository"]
