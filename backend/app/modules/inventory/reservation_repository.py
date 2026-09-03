from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import InventoryReservation


class ReservationRepository:
    """Persistence for reservation lifecycle records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_reservation(
        self,
        reservation_id: uuid.UUID,
    ) -> InventoryReservation | None:
        return await self.session.get(InventoryReservation, reservation_id)

    async def get_reservation_for_update(
        self,
        reservation_id: uuid.UUID,
    ) -> InventoryReservation | None:
        result = await self.session.execute(
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_reservation_by_external_reference(
        self,
        external_reference: str,
    ) -> InventoryReservation | None:
        result = await self.session.execute(
            select(InventoryReservation).where(
                InventoryReservation.external_reference == external_reference
            )
        )
        return result.scalar_one_or_none()

    async def list_reservations(
        self,
        *,
        reservation_number: str | None = None,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        status: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        external_reference: str | None = None,
        expires_before: datetime | None = None,
        expires_after: datetime | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[InventoryReservation], int]:
        filters: list[ColumnElement[bool]] = []
        values = (
            (
                InventoryReservation.reservation_number,
                reservation_number,
            ),
            (InventoryReservation.product_id, product_id),
            (InventoryReservation.warehouse_id, warehouse_id),
            (InventoryReservation.status, status),
            (InventoryReservation.reference_type, reference_type),
            (InventoryReservation.reference_id, reference_id),
            (
                InventoryReservation.external_reference,
                external_reference,
            ),
        )
        filters.extend(column == value for column, value in values if value is not None)
        if expires_before is not None:
            filters.append(InventoryReservation.expires_at <= expires_before)
        if expires_after is not None:
            filters.append(InventoryReservation.expires_at >= expires_after)
        if created_from is not None:
            filters.append(InventoryReservation.created_at >= created_from)
        if created_to is not None:
            filters.append(InventoryReservation.created_at <= created_to)
        if active_only:
            filters.append(
                InventoryReservation.status.in_(("ACTIVE", "PARTIALLY_FULFILLED"))
            )
        if snapshot_at is not None:
            filters.append(InventoryReservation.created_at <= snapshot_at)

        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    InventoryReservation.created_at < after_at,
                    and_(
                        InventoryReservation.created_at == after_at,
                        InventoryReservation.id < after_id,
                    ),
                )
            )

        rows = await self.session.execute(
            select(InventoryReservation)
            .where(*page_filters)
            .order_by(
                InventoryReservation.created_at.desc(),
                InventoryReservation.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(
            select(func.count(InventoryReservation.id)).where(*filters)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def list_expired_reservations_for_update(
        self,
        now: datetime,
        limit: int,
    ) -> list[InventoryReservation]:
        rows = await self.session.execute(
            select(InventoryReservation)
            .where(
                InventoryReservation.status.in_(("ACTIVE", "PARTIALLY_FULFILLED")),
                InventoryReservation.expires_at.is_not(None),
                InventoryReservation.expires_at <= now,
            )
            .order_by(
                InventoryReservation.expires_at,
                InventoryReservation.id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(rows.scalars().all())

    async def add_reservation(
        self,
        reservation: InventoryReservation,
    ) -> InventoryReservation:
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def flush_reservation(
        self,
        reservation: InventoryReservation,
    ) -> InventoryReservation:
        await self.session.flush()
        return reservation
