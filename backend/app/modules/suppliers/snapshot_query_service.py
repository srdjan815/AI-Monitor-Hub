from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.snapshot_fingerprints import (
    item_fingerprint,
    payload_checksum,
    snapshot_fingerprint,
)
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
    SupplierSnapshotItem,
)
from app.modules.suppliers.snapshot_repository import SupplierSnapshotRepository
from app.modules.suppliers.source_repository import SupplierSourceRepository


class SupplierSnapshotQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SupplierSnapshotRepository(session)
        self.suppliers = SupplierRepository(session)
        self.sources = SupplierSourceRepository(session)

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
        await self._parent(supplier_id, source_id)
        return await self.repository.list_snapshots(
            supplier_id,
            source_id,
            status=status,
            storage_state=storage_state,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )

    async def get(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> SupplierSnapshot:
        await self._parent(supplier_id, source_id)
        snapshot = await self.repository.get_snapshot(
            supplier_id, source_id, snapshot_id
        )
        if snapshot is None:
            supplier_error(404, "snapshot_not_found", "Snapshot nije pronađen")
        return snapshot

    async def list_items(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SupplierSnapshotItem], int]:
        snapshot = await self.get(supplier_id, source_id, snapshot_id)
        self._require_online(snapshot)
        return await self.repository.list_items(snapshot.id, limit=limit, offset=offset)

    async def get_item(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> SupplierSnapshotItem:
        snapshot = await self.get(supplier_id, source_id, snapshot_id)
        self._require_online(snapshot)
        item = await self.repository.get_item(snapshot.id, item_id)
        if item is None:
            supplier_error(
                404, "snapshot_item_not_found", "Snapshot Item nije pronađen"
            )
        return item

    async def verify_integrity(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> tuple[SupplierSnapshot, bool, str]:
        snapshot = await self.get(supplier_id, source_id, snapshot_id)
        self._require_online(snapshot)
        items = await self.repository.all_items(snapshot.id)
        if len(items) != snapshot.total_items:
            return snapshot, False, "snapshot_item_count_mismatch"
        payloads: list[dict[str, object]] = []
        fingerprints: list[str] = []
        for item in items:
            calculated = item_fingerprint(
                item.mapped_data,
                item.source_image_links,
                item.source_key,
                item.source_identifier,
            )
            if calculated != item.item_fingerprint:
                return snapshot, False, "snapshot_item_fingerprint_mismatch"
            fingerprints.append(calculated)
            payloads.append(
                {
                    "record_number": item.record_number,
                    "item_fingerprint": calculated,
                    "mapped_data": item.mapped_data,
                    "source_image_links": item.source_image_links,
                }
            )
        complete = snapshot_fingerprint(
            item_fingerprints=fingerprints,
            supplier_id=snapshot.supplier_id,
            source_id=snapshot.source_connection_id,
            acquisition_run_id=snapshot.acquisition_run_id,
            schema_version=snapshot.schema_version_reference,
            mapping_version=snapshot.mapping_version_reference,
        )
        valid = (
            complete == snapshot.snapshot_fingerprint
            and payload_checksum(payloads) == snapshot.payload_checksum
        )
        return (
            snapshot,
            valid,
            "snapshot_integrity_ok" if valid else "snapshot_checksum_mismatch",
        )

    async def statistics(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
    ) -> tuple[SupplierSnapshot, int, int]:
        snapshot = await self.get(supplier_id, source_id, snapshot_id)
        if snapshot.storage_state != "ONLINE":
            return snapshot, 0, 0
        _, active_items = await self.repository.list_items(
            snapshot.id, limit=1, offset=0
        )
        active_bytes = await self.repository.active_payload_bytes(snapshot.id)
        return snapshot, active_items, active_bytes

    async def archive_operation(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        operation_id: uuid.UUID,
    ) -> SupplierSnapshotArchiveOperation:
        snapshot = await self.get(supplier_id, source_id, snapshot_id)
        operation = await self.repository.get_operation(snapshot.id, operation_id)
        if operation is None:
            supplier_error(
                404,
                "snapshot_archive_operation_not_found",
                "Operacija arhiviranja nije pronađena",
            )
        return operation

    async def _parent(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
    ) -> None:
        if await self.suppliers.get_supplier(supplier_id) is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if source_id and await self.sources.get_source(supplier_id, source_id) is None:
            supplier_error(404, "supplier_source_not_found", "Izvor nije pronađen")

    @staticmethod
    def _require_online(snapshot: SupplierSnapshot) -> None:
        if snapshot.storage_state != "ONLINE":
            supplier_error(
                409,
                "snapshot_restore_required",
                "Snapshot je arhiviran; stavke zahtevaju obnovu",
            )


__all__ = ["SupplierSnapshotQueryService"]
