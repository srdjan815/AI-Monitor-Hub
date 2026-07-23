from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    InventoryReservation,
    Warehouse,
)


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_product(
        self,
        product_id: uuid.UUID,
    ) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_product_for_update(
        self,
        product_id: uuid.UUID,
    ) -> Product | None:
        result = await self.session.execute(
            select(Product)
            .where(Product.id == product_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_warehouse(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse | None:
        return await self.session.get(Warehouse, warehouse_id)

    async def get_warehouse_by_code(
        self,
        code: str,
    ) -> Warehouse | None:
        result = await self.session.execute(
            select(Warehouse).where(Warehouse.code == code)
        )
        return result.scalar_one_or_none()

    async def get_warehouse_for_update(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse | None:
        result = await self.session.execute(
            select(Warehouse)
            .where(Warehouse.id == warehouse_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_warehouses(
        self,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Warehouse], int]:
        filters = []
        if active_only:
            filters.append(Warehouse.is_active.is_(True))

        query = select(Warehouse).where(*filters)
        count_query = select(func.count(Warehouse.id)).where(*filters)
        rows = await self.session.execute(
            query.order_by(Warehouse.name).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def create_warehouse(self, warehouse: Warehouse) -> Warehouse:
        self.session.add(warehouse)
        await self.session.flush()
        return warehouse

    async def update_warehouse(
        self,
        warehouse: Warehouse,
        changes: dict[str, object],
    ) -> Warehouse:
        for field, value in changes.items():
            setattr(warehouse, field, value)
        await self.session.flush()
        return warehouse

    async def deactivate_warehouse(
        self,
        warehouse: Warehouse,
    ) -> Warehouse:
        warehouse.is_active = False
        warehouse.version += 1
        await self.session.flush()
        return warehouse

    async def get_inventory(
        self,
        inventory_id: uuid.UUID,
    ) -> Inventory | None:
        return await self.session.get(Inventory, inventory_id)

    async def get_inventory_by_pair(
        self,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Inventory | None:
        result = await self.session.execute(
            select(Inventory).where(
                Inventory.warehouse_id == warehouse_id,
                Inventory.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_inventory(
        self,
        *,
        warehouse_id: uuid.UUID | None = None,
        product_id: uuid.UUID | None = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Inventory], int]:
        filters = []
        if warehouse_id is not None:
            filters.append(Inventory.warehouse_id == warehouse_id)
        if product_id is not None:
            filters.append(Inventory.product_id == product_id)
        if active_only:
            filters.append(Inventory.is_active.is_(True))

        query = select(Inventory).where(*filters)
        count_query = select(func.count(Inventory.id)).where(*filters)
        rows = await self.session.execute(
            query.order_by(Inventory.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def create_inventory(self, inventory: Inventory) -> Inventory:
        self.session.add(inventory)
        await self.session.flush()
        return inventory

    async def update_inventory(
        self,
        inventory: Inventory,
        changes: dict[str, object],
    ) -> Inventory:
        for field, value in changes.items():
            setattr(inventory, field, value)
        await self.session.flush()
        return inventory

    async def deactivate_inventory(
        self,
        inventory: Inventory,
    ) -> Inventory:
        inventory.is_active = False
        inventory.version += 1
        await self.session.flush()
        return inventory

    async def get_inventory_for_update(
        self,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Inventory | None:
        result = await self.session.execute(
            select(Inventory)
            .where(
                Inventory.warehouse_id == warehouse_id,
                Inventory.product_id == product_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

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
                InventoryMovement.external_reference
                == external_reference
            )
        )
        return result.scalar_one_or_none()

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
    ) -> tuple[list[InventoryMovement], int]:
        filters = []
        if movement_type is not None:
            filters.append(
                InventoryMovement.movement_type == movement_type
            )
        if product_id is not None:
            filters.append(InventoryMovement.product_id == product_id)
        if warehouse_id is not None:
            filters.append(
                or_(
                    InventoryMovement.source_warehouse_id == warehouse_id,
                    InventoryMovement.destination_warehouse_id
                    == warehouse_id,
                )
            )
        if source_warehouse_id is not None:
            filters.append(
                InventoryMovement.source_warehouse_id
                == source_warehouse_id
            )
        if destination_warehouse_id is not None:
            filters.append(
                InventoryMovement.destination_warehouse_id
                == destination_warehouse_id
            )
        if external_reference is not None:
            filters.append(
                InventoryMovement.external_reference
                == external_reference
            )
        if is_reversed is not None:
            filters.append(
                InventoryMovement.is_reversed.is_(is_reversed)
            )
        if occurred_from is not None:
            filters.append(
                InventoryMovement.occurred_at >= occurred_from
            )
        if occurred_to is not None:
            filters.append(
                InventoryMovement.occurred_at <= occurred_to
            )

        query = select(InventoryMovement).where(*filters)
        count_query = select(func.count(InventoryMovement.id)).where(
            *filters
        )
        rows = await self.session.execute(
            query.order_by(InventoryMovement.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def add_inventory(self, inventory: Inventory) -> Inventory:
        self.session.add(inventory)
        await self.session.flush()
        return inventory

    async def add_movement(
        self,
        movement: InventoryMovement,
    ) -> InventoryMovement:
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def flush_balance(self, inventory: Inventory) -> Inventory:
        await self.session.flush()
        return inventory

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

    async def get_reservation(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation | None:
        return await self.session.get(InventoryReservation, reservation_id)

    async def get_reservation_for_update(
        self, reservation_id: uuid.UUID
    ) -> InventoryReservation | None:
        result = await self.session.execute(
            select(InventoryReservation)
            .where(InventoryReservation.id == reservation_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_reservation_by_external_reference(
        self, external_reference: str
    ) -> InventoryReservation | None:
        result = await self.session.execute(
            select(InventoryReservation).where(
                InventoryReservation.external_reference
                == external_reference
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
    ) -> tuple[list[InventoryReservation], int]:
        filters = []
        values = (
            (InventoryReservation.reservation_number, reservation_number),
            (InventoryReservation.product_id, product_id),
            (InventoryReservation.warehouse_id, warehouse_id),
            (InventoryReservation.status, status),
            (InventoryReservation.reference_type, reference_type),
            (InventoryReservation.reference_id, reference_id),
            (InventoryReservation.external_reference, external_reference),
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
                InventoryReservation.status.in_(
                    ("ACTIVE", "PARTIALLY_FULFILLED")
                )
            )
        rows = await self.session.execute(
            select(InventoryReservation)
            .where(*filters)
            .order_by(InventoryReservation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(
            select(func.count(InventoryReservation.id)).where(*filters)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def list_expired_reservations_for_update(
        self, now: datetime, limit: int
    ) -> list[InventoryReservation]:
        rows = await self.session.execute(
            select(InventoryReservation)
            .where(
                InventoryReservation.status.in_(
                    ("ACTIVE", "PARTIALLY_FULFILLED")
                ),
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
        self, reservation: InventoryReservation
    ) -> InventoryReservation:
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def flush_reservation(
        self, reservation: InventoryReservation
    ) -> InventoryReservation:
        await self.session.flush()
        return reservation
