from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from app.modules.inventory.models import Inventory, Warehouse


class WarehouseBalanceRepository:
    """Persistence for warehouses, products, and current stock balances."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_product(self, product_id: uuid.UUID) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_product_for_update(
        self,
        product_id: uuid.UUID,
    ) -> Product | None:
        result = await self.session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_warehouse(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse | None:
        return await self.session.get(Warehouse, warehouse_id)

    async def get_warehouse_by_code(self, code: str) -> Warehouse | None:
        result = await self.session.execute(
            select(Warehouse).where(Warehouse.code == code)
        )
        return result.scalar_one_or_none()

    async def get_warehouse_for_update(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse | None:
        result = await self.session.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_warehouses(
        self,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Warehouse], int]:
        filters: list[ColumnElement[bool]] = []
        if active_only:
            filters.append(Warehouse.is_active.is_(True))
        if snapshot_at is not None:
            filters.append(Warehouse.created_at <= snapshot_at)

        count_query = select(func.count(Warehouse.id)).where(*filters)
        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    Warehouse.created_at < after_at,
                    and_(
                        Warehouse.created_at == after_at,
                        Warehouse.id < after_id,
                    ),
                )
            )

        query = select(Warehouse).where(*page_filters)
        if snapshot_at is None and after is None:
            query = query.order_by(Warehouse.name, Warehouse.id)
        else:
            query = query.order_by(
                Warehouse.created_at.desc(),
                Warehouse.id.desc(),
            )

        rows = await self.session.execute(query.limit(limit).offset(offset))
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
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Inventory], int]:
        filters: list[ColumnElement[bool]] = []
        if warehouse_id is not None:
            filters.append(Inventory.warehouse_id == warehouse_id)
        if product_id is not None:
            filters.append(Inventory.product_id == product_id)
        if active_only:
            filters.append(Inventory.is_active.is_(True))
        if snapshot_at is not None:
            filters.append(Inventory.created_at <= snapshot_at)

        count_query = select(func.count(Inventory.id)).where(*filters)
        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    Inventory.created_at < after_at,
                    and_(
                        Inventory.created_at == after_at,
                        Inventory.id < after_id,
                    ),
                )
            )

        query = select(Inventory).where(*page_filters)
        if snapshot_at is None and after is None:
            query = query.order_by(
                Inventory.updated_at.desc(),
                Inventory.id.desc(),
            )
        else:
            query = query.order_by(
                Inventory.created_at.desc(),
                Inventory.id.desc(),
            )

        rows = await self.session.execute(query.limit(limit).offset(offset))
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

    async def add_inventory(self, inventory: Inventory) -> Inventory:
        self.session.add(inventory)
        await self.session.flush()
        return inventory

    async def flush_balance(self, inventory: Inventory) -> Inventory:
        await self.session.flush()
        return inventory
