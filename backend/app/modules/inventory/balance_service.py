from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.inventory.inventory_service_support import InventoryServiceSupport
from app.modules.inventory.models import Inventory, Warehouse
from app.modules.inventory.schemas import (
    InventoryCreate,
    InventoryUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)


class WarehouseBalanceService(InventoryServiceSupport):
    """Warehouse administration and current-balance commands."""

    async def create_warehouse(
        self,
        data: WarehouseCreate,
    ) -> Warehouse:
        code = data.code.strip().lower()
        name = data.name.strip()
        if not code or not name:
            raise HTTPException(
                status_code=422,
                detail="Kod i naziv skladišta su obavezni",
            )
        if await self.repository.get_warehouse_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod skladišta već postoji",
            )

        warehouse = Warehouse(
            code=code,
            name=name,
            description=self._normalize_optional(data.description),
            is_active=data.is_active,
        )
        try:
            await self.repository.create_warehouse(warehouse)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kod skladišta već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(warehouse)
        return warehouse

    async def get_warehouse(
        self,
        warehouse_id: uuid.UUID,
    ) -> Warehouse:
        return await self._get_warehouse_or_404(warehouse_id)

    async def update_warehouse(
        self,
        warehouse_id: uuid.UUID,
        data: WarehouseUpdate,
    ) -> Warehouse:
        warehouse = await self._get_warehouse_or_404(warehouse_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv skladišta je obavezan",
                )
        if "description" in changes:
            changes["description"] = self._normalize_optional(changes["description"])

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(warehouse, field) != value
        }
        if actual_changes:
            actual_changes["version"] = warehouse.version + 1

        try:
            await self.repository.update_warehouse(
                warehouse,
                actual_changes,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(warehouse)
        return warehouse

    async def deactivate_warehouse(self, warehouse_id: uuid.UUID) -> None:
        warehouse = await self._get_warehouse_or_404(warehouse_id)
        if not warehouse.is_active:
            return
        try:
            await self.repository.deactivate_warehouse(warehouse)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(warehouse)

    async def create_inventory(
        self,
        data: InventoryCreate,
    ) -> Inventory:
        await self._get_warehouse_or_404(data.warehouse_id)
        await self._get_product_or_404(data.product_id)
        self._validate_quantities(
            quantity_on_hand=data.quantity_on_hand,
            quantity_reserved=data.quantity_reserved,
            minimum_stock=data.minimum_stock,
            reorder_point=data.reorder_point,
        )
        if await self.repository.get_inventory_by_pair(
            data.warehouse_id,
            data.product_id,
        ):
            raise HTTPException(
                status_code=409,
                detail="Zaliha za skladište i proizvod već postoji",
            )

        inventory = Inventory(**data.model_dump())
        try:
            await self.repository.create_inventory(inventory)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Zaliha za skladište i proizvod već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(inventory)
        return inventory

    async def get_inventory(
        self,
        inventory_id: uuid.UUID,
    ) -> Inventory:
        return await self._get_inventory_or_404(inventory_id)

    async def update_inventory(
        self,
        inventory_id: uuid.UUID,
        data: InventoryUpdate,
    ) -> Inventory:
        inventory = await self._get_inventory_or_404(inventory_id)
        changes = data.model_dump(exclude_unset=True)

        warehouse_id = changes.get("warehouse_id", inventory.warehouse_id)
        product_id = changes.get("product_id", inventory.product_id)
        if warehouse_id is None or product_id is None:
            raise HTTPException(
                status_code=422,
                detail="Skladište i proizvod su obavezni",
            )
        if "warehouse_id" in changes:
            await self._get_warehouse_or_404(warehouse_id)
        if "product_id" in changes:
            await self._get_product_or_404(product_id)

        quantities = {
            "quantity_on_hand": changes.get(
                "quantity_on_hand", inventory.quantity_on_hand
            ),
            "quantity_reserved": changes.get(
                "quantity_reserved", inventory.quantity_reserved
            ),
            "minimum_stock": changes.get("minimum_stock", inventory.minimum_stock),
            "reorder_point": changes.get("reorder_point", inventory.reorder_point),
        }
        if any(value is None for value in quantities.values()):
            raise HTTPException(
                status_code=422,
                detail="Količine ne mogu biti null",
            )
        self._validate_quantities(**quantities)

        if warehouse_id != inventory.warehouse_id or product_id != inventory.product_id:
            existing = await self.repository.get_inventory_by_pair(
                warehouse_id,
                product_id,
            )
            if existing is not None and existing.id != inventory.id:
                raise HTTPException(
                    status_code=409,
                    detail="Zaliha za skladište i proizvod već postoji",
                )

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(inventory, field) != value
        }
        if actual_changes:
            actual_changes["version"] = inventory.version + 1

        try:
            await self.repository.update_inventory(
                inventory,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Zaliha za skladište i proizvod već postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(inventory)
        return inventory

    async def deactivate_inventory(self, inventory_id: uuid.UUID) -> None:
        inventory = await self._get_inventory_or_404(inventory_id)
        if not inventory.is_active:
            return
        try:
            await self.repository.deactivate_inventory(inventory)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(inventory)
