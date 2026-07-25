from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionRun,
    SupplierStagedRecord,
)
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
    SupplierSnapshotItem,
)


class SupplierSnapshotRepository:
    """Snapshot queries and flush-only persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acquisition_for_update(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> SupplierAcquisitionRun | None:
        return (
            await self.session.execute(
                select(SupplierAcquisitionRun)
                .where(
                    SupplierAcquisitionRun.id == run_id,
                    SupplierAcquisitionRun.supplier_id == supplier_id,
                    SupplierAcquisitionRun.source_connection_id == source_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def acquisition(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> SupplierAcquisitionRun | None:
        return (
            await self.session.execute(
                select(SupplierAcquisitionRun).where(
                    SupplierAcquisitionRun.id == run_id,
                    SupplierAcquisitionRun.supplier_id == supplier_id,
                    SupplierAcquisitionRun.source_connection_id == source_id,
                )
            )
        ).scalar_one_or_none()

    async def accepted_records(self, run_id: uuid.UUID) -> list[SupplierStagedRecord]:
        rows = await self.session.execute(
            select(SupplierStagedRecord)
            .where(
                SupplierStagedRecord.acquisition_run_id == run_id,
                SupplierStagedRecord.validation_status == "ACCEPTED",
            )
            .order_by(SupplierStagedRecord.record_number)
        )
        return list(rows.scalars())

    async def by_acquisition(
        self,
        run_id: uuid.UUID,
    ) -> SupplierSnapshot | None:
        return (
            await self.session.execute(
                select(SupplierSnapshot).where(
                    SupplierSnapshot.acquisition_run_id == run_id
                )
            )
        ).scalar_one_or_none()

    async def add_snapshot(self, snapshot: SupplierSnapshot) -> None:
        self.session.add(snapshot)
        await self.session.flush()

    async def add_items(self, items: list[SupplierSnapshotItem]) -> None:
        self.session.add_all(items)
        await self.session.flush()

    async def mutate_snapshot(
        self,
        snapshot: SupplierSnapshot,
        changes: dict[str, object],
    ) -> None:
        for field, value in changes.items():
            setattr(snapshot, field, value)
        await self.session.flush()

    async def get_snapshot(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> SupplierSnapshot | None:
        query = select(SupplierSnapshot).where(
            SupplierSnapshot.id == snapshot_id,
            SupplierSnapshot.supplier_id == supplier_id,
            SupplierSnapshot.source_connection_id == source_id,
        )
        if for_update:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def list_snapshots(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
        *,
        status: str | None,
        storage_state: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SupplierSnapshot], int]:
        filters = [SupplierSnapshot.supplier_id == supplier_id]
        if source_id:
            filters.append(SupplierSnapshot.source_connection_id == source_id)
        if status:
            filters.append(SupplierSnapshot.status == status)
        if storage_state:
            filters.append(SupplierSnapshot.storage_state == storage_state)
        if created_from:
            filters.append(SupplierSnapshot.created_at >= created_from)
        if created_to:
            filters.append(SupplierSnapshot.created_at <= created_to)
        total = await self.session.scalar(
            select(func.count(SupplierSnapshot.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierSnapshot)
            .where(*filters)
            .order_by(SupplierSnapshot.created_at.desc(), SupplierSnapshot.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def list_items(
        self,
        snapshot_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupplierSnapshotItem], int]:
        total = await self.session.scalar(
            select(func.count(SupplierSnapshotItem.id)).where(
                SupplierSnapshotItem.snapshot_id == snapshot_id
            )
        )
        rows = await self.session.execute(
            select(SupplierSnapshotItem)
            .where(SupplierSnapshotItem.snapshot_id == snapshot_id)
            .order_by(SupplierSnapshotItem.record_number)
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def all_items(self, snapshot_id: uuid.UUID) -> list[SupplierSnapshotItem]:
        rows = await self.session.execute(
            select(SupplierSnapshotItem)
            .where(SupplierSnapshotItem.snapshot_id == snapshot_id)
            .order_by(SupplierSnapshotItem.record_number)
        )
        return list(rows.scalars())

    async def get_item(
        self,
        snapshot_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> SupplierSnapshotItem | None:
        return (
            await self.session.execute(
                select(SupplierSnapshotItem).where(
                    SupplierSnapshotItem.id == item_id,
                    SupplierSnapshotItem.snapshot_id == snapshot_id,
                )
            )
        ).scalar_one_or_none()

    async def delete_items(self, snapshot_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(SupplierSnapshotItem).where(
                SupplierSnapshotItem.snapshot_id == snapshot_id
            )
        )
        await self.session.flush()

    async def active_payload_bytes(self, snapshot_id: uuid.UUID) -> int:
        value = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.pg_column_size(SupplierSnapshotItem.mapped_data)
                        + func.pg_column_size(SupplierSnapshotItem.source_image_links)
                    ),
                    0,
                )
            ).where(SupplierSnapshotItem.snapshot_id == snapshot_id)
        )
        return int(value or 0)

    async def add_operation(
        self,
        operation: SupplierSnapshotArchiveOperation,
    ) -> None:
        self.session.add(operation)
        await self.session.flush()

    async def mutate_operation(
        self,
        operation: SupplierSnapshotArchiveOperation,
        changes: dict[str, object],
    ) -> None:
        for field, value in changes.items():
            setattr(operation, field, value)
        await self.session.flush()

    async def get_operation(
        self,
        snapshot_id: uuid.UUID,
        operation_id: uuid.UUID,
    ) -> SupplierSnapshotArchiveOperation | None:
        return (
            await self.session.execute(
                select(SupplierSnapshotArchiveOperation).where(
                    SupplierSnapshotArchiveOperation.id == operation_id,
                    SupplierSnapshotArchiveOperation.snapshot_id == snapshot_id,
                )
            )
        ).scalar_one_or_none()

    async def latest_operation(
        self,
        snapshot_id: uuid.UUID,
    ) -> SupplierSnapshotArchiveOperation | None:
        return (
            await self.session.execute(
                select(SupplierSnapshotArchiveOperation)
                .where(SupplierSnapshotArchiveOperation.snapshot_id == snapshot_id)
                .order_by(
                    SupplierSnapshotArchiveOperation.created_at.desc(),
                    SupplierSnapshotArchiveOperation.id.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    async def has_unresolved_operation(self, snapshot_id: uuid.UUID) -> bool:
        value = await self.session.scalar(
            select(func.count(SupplierSnapshotArchiveOperation.id)).where(
                SupplierSnapshotArchiveOperation.snapshot_id == snapshot_id,
                SupplierSnapshotArchiveOperation.status == "EXPORTING",
            )
        )
        return bool(value)


__all__ = ["SupplierSnapshotRepository"]
