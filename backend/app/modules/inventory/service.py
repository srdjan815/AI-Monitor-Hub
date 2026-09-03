from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.balance_service import WarehouseBalanceService
from app.modules.inventory.inventory_service_support import InventoryServiceSupport
from app.modules.inventory.movement_service import InventoryMovementService
from app.modules.inventory.reservation_service import ReservationService


class InventoryService(
    WarehouseBalanceService,
    InventoryMovementService,
    ReservationService,
):
    """Backward-compatible façade over cohesive Inventory transaction domains."""

    def __init__(self, session: AsyncSession) -> None:
        InventoryServiceSupport.__init__(self, session)


__all__ = ["InventoryService"]
