from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionIssue,
    SupplierAcquisitionRun,
    SupplierStagedRecord,
)
from app.modules.suppliers.acquisition_repository import SupplierAcquisitionRepository
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository


class SupplierAcquisitionQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SupplierAcquisitionRepository(session)
        self.suppliers = SupplierRepository(session)
        self.sources = SupplierSourceRepository(session)

    async def list_runs(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        *,
        status: str | None = None,
        trigger_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierAcquisitionRun], int]:
        await self._parent(supplier_id, source_id)
        return await self.repository.list_runs(
            supplier_id,
            source_id,
            status=status,
            trigger_type=trigger_type,
            limit=limit,
            offset=offset,
        )

    async def get_run(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> SupplierAcquisitionRun:
        await self._parent(supplier_id, source_id)
        run = await self.repository.get_run(supplier_id, source_id, run_id)
        if run is None:
            supplier_error(
                404,
                "acquisition_run_not_found",
                "Acquisition Run nije pronađen",
            )
        return run

    async def list_records(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierStagedRecord], int]:
        await self.get_run(supplier_id, source_id, run_id)
        return await self.repository.list_records(
            run_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_record(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> SupplierStagedRecord:
        await self.get_run(supplier_id, source_id, run_id)
        record = await self.repository.get_record(run_id, record_id)
        if record is None:
            supplier_error(
                404,
                "acquisition_record_not_found",
                "Staged Acquisition Record nije pronađen",
            )
        return record

    async def list_issues(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SupplierAcquisitionIssue], int]:
        await self.get_run(supplier_id, source_id, run_id)
        return await self.repository.list_issues(
            run_id,
            severity=severity,
            limit=limit,
            offset=offset,
        )

    async def _parent(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> None:
        if await self.suppliers.get_supplier(supplier_id) is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if await self.sources.get_source(supplier_id, source_id) is None:
            supplier_error(404, "supplier_source_not_found", "Izvor nije pronađen")


__all__ = ["SupplierAcquisitionQueryService"]
