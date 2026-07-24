from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryMovement


class MovementRepository:
    """Persistence owned by the immutable inventory movement ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_movement(
        self,
        movement_id: uuid.UUID,
    ) -> InventoryMovement | None:
        return await self.session.get(InventoryMovement, movement_id)

    async def get_movement_for_update(
        self,
        movement_id: uuid.UUID,
    ) -> InventoryMovement | None:
        result = await self.session.execute(
            select(InventoryMovement)
            .where(InventoryMovement.id == movement_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_movement_by_external_reference(
        self,
        external_reference: str,
    ) -> InventoryMovement | None:
        result = await self.session.execute(
            select(InventoryMovement).where(
                InventoryMovement.external_reference == external_reference
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _movement_filters(
        *,
        movement_type: str | None,
        product_id: uuid.UUID | None,
        warehouse_id: uuid.UUID | None,
        source_warehouse_id: uuid.UUID | None,
        destination_warehouse_id: uuid.UUID | None,
        external_reference: str | None,
        is_reversed: bool | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        snapshot_at: datetime | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [
            column == value
            for column, value in (
                (InventoryMovement.movement_type, movement_type),
                (InventoryMovement.product_id, product_id),
            )
            if value is not None
        ]
        if warehouse_id is not None:
            filters.append(
                or_(
                    InventoryMovement.source_warehouse_id == warehouse_id,
                    InventoryMovement.destination_warehouse_id == warehouse_id,
                )
            )
        filters.extend(
            column == value
            for column, value in (
                (
                    InventoryMovement.source_warehouse_id,
                    source_warehouse_id,
                ),
                (
                    InventoryMovement.destination_warehouse_id,
                    destination_warehouse_id,
                ),
                (
                    InventoryMovement.external_reference,
                    external_reference,
                ),
            )
            if value is not None
        )
        if is_reversed is not None:
            filters.append(InventoryMovement.is_reversed.is_(is_reversed))
        if occurred_from is not None:
            filters.append(InventoryMovement.occurred_at >= occurred_from)
        if occurred_to is not None:
            filters.append(InventoryMovement.occurred_at <= occurred_to)
        if snapshot_at is not None:
            filters.append(InventoryMovement.created_at <= snapshot_at)
        return filters

    async def list_movements(
        self,
        *,
        movement_type: str | None = None,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        source_warehouse_id: uuid.UUID | None = None,
        destination_warehouse_id: uuid.UUID | None = None,
        external_reference: str | None = None,
        is_reversed: bool | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[InventoryMovement], int]:
        filters = self._movement_filters(
            movement_type=movement_type,
            product_id=product_id,
            warehouse_id=warehouse_id,
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=destination_warehouse_id,
            external_reference=external_reference,
            is_reversed=is_reversed,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            snapshot_at=snapshot_at,
        )
        count_query = select(func.count(InventoryMovement.id)).where(*filters)
        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    InventoryMovement.occurred_at < after_at,
                    and_(
                        InventoryMovement.occurred_at == after_at,
                        InventoryMovement.id < after_id,
                    ),
                )
            )

        rows = await self.session.execute(
            select(InventoryMovement)
            .where(*page_filters)
            .order_by(
                InventoryMovement.occurred_at.desc(),
                InventoryMovement.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def add_movement(
        self,
        movement: InventoryMovement,
    ) -> InventoryMovement:
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def mark_movement_reversed(
        self,
        movement: InventoryMovement,
        *,
        reversed_at: datetime,
    ) -> InventoryMovement:
        movement.is_reversed = True
        movement.reversed_at = reversed_at
        movement.version += 1
        await self.session.flush()
        return movement
