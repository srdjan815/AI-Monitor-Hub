from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.delta_models import SupplierDeltaItem, SupplierDeltaRun
from app.modules.suppliers.delta_repository import SupplierDeltaRepository
from app.modules.suppliers.errors import supplier_error


class SupplierDeltaQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SupplierDeltaRepository(session)

    async def get(self, supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID) -> SupplierDeltaRun:
        run = await self.repository.get_run(run_id)
        if run is None or run.supplier_id != supplier_id or run.source_connection_id != source_id:
            supplier_error(404, "delta_not_found", "Delta Run nije pronađen")
        return run

    async def list_runs(self, supplier_id: uuid.UUID, source_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[SupplierDeltaRun], int]:
        return await self.repository.list_runs(supplier_id, source_id, limit=limit, offset=offset)

    async def items(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID,
        *, change_type: str | None, price: bool | None, stock: bool | None,
        image: bool | None, identifier: bool | None, anomaly_flag: str | None,
        limit: int, offset: int,
    ) -> tuple[list[SupplierDeltaItem], int]:
        await self.get(supplier_id, source_id, run_id)
        return await self.repository.list_delta_items(
            run_id, change_type=change_type, price=price, stock=stock,
            image=image, identifier=identifier, anomaly_flag=anomaly_flag,
            limit=limit, offset=offset,
        )

    async def item(self, supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, item_id: uuid.UUID) -> SupplierDeltaItem:
        await self.get(supplier_id, source_id, run_id)
        item = await self.repository.get_delta_item(run_id, item_id)
        if item is None:
            supplier_error(404, "delta_item_not_found", "Delta stavka nije pronađena")
        return item


__all__ = ["SupplierDeltaQueryService"]
