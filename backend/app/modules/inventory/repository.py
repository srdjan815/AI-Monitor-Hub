from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.balance_repository import (
    WarehouseBalanceRepository,
)
from app.modules.inventory.movement_repository import MovementRepository
from app.modules.inventory.reservation_repository import (
    ReservationRepository,
)


class InventoryRepository(
    WarehouseBalanceRepository,
    MovementRepository,
    ReservationRepository,
):
    """Backward-compatible façade over responsibility-specific repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session


__all__ = ["InventoryRepository"]
