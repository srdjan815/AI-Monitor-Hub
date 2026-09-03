from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.delta_models import (
    SupplierDeltaFieldChange, SupplierDeltaItem, SupplierDeltaRun,
)
from app.modules.suppliers.acquisition_models import SupplierStagedRecord
from app.modules.suppliers.snapshot_models import SupplierSnapshot, SupplierSnapshotItem


class SupplierDeltaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def snapshot(self, snapshot_id: uuid.UUID) -> SupplierSnapshot | None:
        return await self.session.get(SupplierSnapshot, snapshot_id)

    async def items(self, snapshot_id: uuid.UUID) -> list[SupplierSnapshotItem]:
        rows = await self.session.execute(
            select(SupplierSnapshotItem)
            .where(SupplierSnapshotItem.snapshot_id == snapshot_id)
            .order_by(SupplierSnapshotItem.record_number, SupplierSnapshotItem.id)
        )
        return list(rows.scalars())

    async def rejected_records(self, run_id: uuid.UUID) -> list[SupplierStagedRecord]:
        rows = await self.session.execute(
            select(SupplierStagedRecord)
            .where(
                SupplierStagedRecord.acquisition_run_id == run_id,
                SupplierStagedRecord.validation_status == "REJECTED",
            )
            .order_by(SupplierStagedRecord.record_number, SupplierStagedRecord.id)
        )
        return list(rows.scalars())

    async def previous_ready(self, current: SupplierSnapshot) -> SupplierSnapshot | None:
        return (
            await self.session.execute(
                select(SupplierSnapshot)
                .where(
                    SupplierSnapshot.supplier_id == current.supplier_id,
                    SupplierSnapshot.source_connection_id == current.source_connection_id,
                    SupplierSnapshot.status == "READY",
                    SupplierSnapshot.created_at < current.created_at,
                )
                .order_by(SupplierSnapshot.created_at.desc(), SupplierSnapshot.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def successful(
        self, previous_id: uuid.UUID, current_id: uuid.UUID, version: int,
    ) -> SupplierDeltaRun | None:
        return (
            await self.session.execute(
                select(SupplierDeltaRun).where(
                    SupplierDeltaRun.previous_snapshot_id == previous_id,
                    SupplierDeltaRun.current_snapshot_id == current_id,
                    SupplierDeltaRun.comparison_version == version,
                    SupplierDeltaRun.status == "SUCCEEDED",
                )
            )
        ).scalar_one_or_none()

    async def by_idempotency(
        self, supplier_id: uuid.UUID, source_id: uuid.UUID, key: str,
    ) -> SupplierDeltaRun | None:
        return (
            await self.session.execute(
                select(SupplierDeltaRun).where(
                    SupplierDeltaRun.supplier_id == supplier_id,
                    SupplierDeltaRun.source_connection_id == source_id,
                    SupplierDeltaRun.idempotency_key == key,
                )
            )
        ).scalar_one_or_none()

    async def add_run(self, run: SupplierDeltaRun) -> None:
        self.session.add(run)
        await self.session.flush()

    async def mutate_run(self, run: SupplierDeltaRun, changes: dict[str, object]) -> None:
        for name, value in changes.items():
            setattr(run, name, value)
        await self.session.flush()

    async def add_results(
        self, items: list[SupplierDeltaItem], fields: list[SupplierDeltaFieldChange],
    ) -> None:
        self.session.add_all(items)
        await self.session.flush()
        self.session.add_all(fields)
        await self.session.flush()

    async def get_run(self, run_id: uuid.UUID, *, lock: bool = False) -> SupplierDeltaRun | None:
        query = select(SupplierDeltaRun).where(SupplierDeltaRun.id == run_id)
        if lock:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def list_runs(self, supplier_id: uuid.UUID, source_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[SupplierDeltaRun], int]:
        filters = [SupplierDeltaRun.supplier_id == supplier_id, SupplierDeltaRun.source_connection_id == source_id]
        total = await self.session.scalar(select(func.count(SupplierDeltaRun.id)).where(*filters))
        rows = await self.session.execute(select(SupplierDeltaRun).where(*filters).order_by(SupplierDeltaRun.created_at.desc(), SupplierDeltaRun.id.desc()).limit(limit).offset(offset))
        return list(rows.scalars()), int(total or 0)

    async def list_delta_items(self, run_id: uuid.UUID, *, change_type: str | None, price: bool | None, stock: bool | None, image: bool | None, identifier: bool | None, anomaly_flag: str | None, limit: int, offset: int) -> tuple[list[SupplierDeltaItem], int]:
        filters = [SupplierDeltaItem.delta_run_id == run_id]
        for column, value in ((SupplierDeltaItem.change_type, change_type), (SupplierDeltaItem.has_price_change, price), (SupplierDeltaItem.has_stock_change, stock), (SupplierDeltaItem.has_image_change, image), (SupplierDeltaItem.has_identifier_change, identifier)):
            if value is not None:
                filters.append(column == value)
        if anomaly_flag:
            filters.append(SupplierDeltaItem.anomaly_flags.contains([anomaly_flag]))
        total = await self.session.scalar(select(func.count(SupplierDeltaItem.id)).where(*filters))
        rows = await self.session.execute(select(SupplierDeltaItem).where(*filters).order_by(SupplierDeltaItem.created_at, SupplierDeltaItem.id).limit(limit).offset(offset))
        return list(rows.scalars()), int(total or 0)

    async def get_delta_item(self, run_id: uuid.UUID, item_id: uuid.UUID) -> SupplierDeltaItem | None:
        return (await self.session.execute(select(SupplierDeltaItem).where(SupplierDeltaItem.id == item_id, SupplierDeltaItem.delta_run_id == run_id))).scalar_one_or_none()

    async def field_changes(self, item_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[SupplierDeltaFieldChange], int]:
        total = await self.session.scalar(select(func.count(SupplierDeltaFieldChange.id)).where(SupplierDeltaFieldChange.delta_item_id == item_id))
        rows = await self.session.execute(select(SupplierDeltaFieldChange).where(SupplierDeltaFieldChange.delta_item_id == item_id).order_by(SupplierDeltaFieldChange.field_path).limit(limit).offset(offset))
        return list(rows.scalars()), int(total or 0)


__all__ = ["SupplierDeltaRepository"]
