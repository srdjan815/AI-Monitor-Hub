from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.snapshot_archive_service import (
    SupplierSnapshotArchiveService,
)
from app.modules.suppliers.snapshot_models import SupplierSnapshotArchiveOperation


class SupplierSnapshotBulkArchiveService:
    def __init__(self, session: AsyncSession) -> None:
        self.archives = SupplierSnapshotArchiveService(session)

    async def export(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        snapshot_ids: list[uuid.UUID],
        *,
        include_source_artifact: bool,
    ) -> tuple[list[SupplierSnapshotArchiveOperation], list[dict[str, str]]]:
        succeeded: list[SupplierSnapshotArchiveOperation] = []
        failed: list[dict[str, str]] = []
        for snapshot_id in sorted(snapshot_ids, key=str):
            try:
                operation = await self.archives.export(
                    supplier_id,
                    source_id,
                    snapshot_id,
                    include_source_artifact=include_source_artifact,
                )
            except HTTPException as exc:
                detail: dict[object, object] = (
                    exc.detail if isinstance(exc.detail, dict) else {}
                )
                failed.append(
                    {
                        "snapshot_id": str(snapshot_id),
                        "code": str(detail.get("code", "snapshot_archive_failed")),
                    }
                )
                continue
            if operation.status == "VERIFIED":
                succeeded.append(operation)
            else:
                failed.append(
                    {
                        "snapshot_id": str(snapshot_id),
                        "code": operation.failure_code or "snapshot_archive_failed",
                    }
                )
        return succeeded, failed


__all__ = ["SupplierSnapshotBulkArchiveService"]
