from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_DB_INTEGER
from app.modules.catalog.models import Product
from app.modules.inventory.enums import MovementType
from app.modules.inventory.models import Inventory, Warehouse
from app.modules.inventory.repository import InventoryRepository


class InventoryServiceSupport:
    """Shared locking, invariant, identity, and transaction-context helpers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = InventoryRepository(session)

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def _get_warehouse_or_404(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse:
        warehouse = await self.repository.get_warehouse(warehouse_id)
        if warehouse is None:
            raise HTTPException(
                status_code=404,
                detail="Skladište nije pronađeno",
            )
        return warehouse

    async def _get_inventory_or_404(
        self,
        inventory_id: uuid.UUID,
    ) -> Inventory:
        inventory = await self.repository.get_inventory(inventory_id)
        if inventory is None:
            raise HTTPException(
                status_code=404,
                detail="Zaliha nije pronađena",
            )
        return inventory

    async def _get_product_or_404(self, product_id: uuid.UUID) -> Product:
        product = await self.repository.get_product(product_id)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Proizvod nije pronađen",
            )
        return product

    @staticmethod
    def _validate_quantities(
        *,
        quantity_on_hand: int,
        quantity_reserved: int,
        minimum_stock: int,
        reorder_point: int,
    ) -> None:
        if (
            min(
                quantity_on_hand,
                quantity_reserved,
                minimum_stock,
                reorder_point,
            )
            < 0
        ):
            raise HTTPException(
                status_code=422,
                detail="Količine ne mogu biti negativne",
            )
        if quantity_reserved > quantity_on_hand:
            raise HTTPException(
                status_code=422,
                detail="Rezervisana količina ne može biti veća od stanja",
            )

    @staticmethod
    def _movement_number() -> str:
        date_part = datetime.now(UTC).strftime("%Y%m%d")
        random_part = uuid.uuid4().hex[:8].upper()
        return f"MOV-{date_part}-{random_part}"

    @staticmethod
    def _reservation_number() -> str:
        date_part = datetime.now(UTC).strftime("%Y%m%d")
        random_part = uuid.uuid4().hex[:8].upper()
        return f"RES-{date_part}-{random_part}"

    async def _lock_active_product(
        self,
        product_id: uuid.UUID,
    ) -> Product:
        product = await self.repository.get_product_for_update(product_id)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Proizvod nije pronađen",
            )
        if not product.is_active:
            raise HTTPException(
                status_code=422,
                detail="Proizvod nije aktivan",
            )
        return product

    async def _lock_active_warehouses(
        self,
        warehouse_ids: set[uuid.UUID],
    ) -> None:
        for warehouse_id in sorted(warehouse_ids, key=str):
            warehouse = await self.repository.get_warehouse_for_update(warehouse_id)
            if warehouse is None:
                raise HTTPException(
                    status_code=404,
                    detail="Skladište nije pronađeno",
                )
            if not warehouse.is_active:
                raise HTTPException(
                    status_code=422,
                    detail="Skladište nije aktivno",
                )

    async def _apply_balance_changes(
        self,
        *,
        movement_type: MovementType,
        product_id: uuid.UUID,
        source_warehouse_id: uuid.UUID | None,
        destination_warehouse_id: uuid.UUID | None,
        quantity: int,
    ) -> None:
        warehouse_ids = {
            warehouse_id
            for warehouse_id in (
                source_warehouse_id,
                destination_warehouse_id,
            )
            if warehouse_id is not None
        }
        await self._lock_active_warehouses(warehouse_ids)

        balances: dict[uuid.UUID, Inventory | None] = {}
        for warehouse_id in sorted(warehouse_ids, key=str):
            balances[warehouse_id] = await self.repository.get_inventory_for_update(
                warehouse_id,
                product_id,
            )

        if source_warehouse_id is not None:
            source = balances[source_warehouse_id]
            if source is None:
                raise HTTPException(
                    status_code=422,
                    detail="Izvorna zaliha ne postoji",
                )
            new_on_hand = source.quantity_on_hand - quantity
            if new_on_hand < 0:
                raise HTTPException(
                    status_code=422,
                    detail="Nedovoljna količina na stanju",
                )
            if new_on_hand < source.quantity_reserved:
                raise HTTPException(
                    status_code=422,
                    detail="Promena bi ugrozila rezervisanu količinu",
                )
            source.quantity_on_hand = new_on_hand
            source.version += 1
            await self.repository.flush_balance(source)

        if destination_warehouse_id is not None:
            destination = balances[destination_warehouse_id]
            if destination is None:
                destination = Inventory(
                    warehouse_id=destination_warehouse_id,
                    product_id=product_id,
                    quantity_on_hand=quantity,
                )
                await self.repository.add_inventory(destination)
            else:
                new_on_hand = destination.quantity_on_hand + quantity
                if new_on_hand > MAX_DB_INTEGER:
                    raise HTTPException(
                        status_code=422,
                        detail="Promena bi prekoračila dozvoljeno stanje zaliha",
                    )
                destination.quantity_on_hand = new_on_hand
                destination.version += 1
                await self.repository.flush_balance(destination)
