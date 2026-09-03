from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.suppliers.snapshot_models import SupplierSnapshot
from app.modules.suppliers.snapshot_query_service import SupplierSnapshotQueryService
from app.modules.suppliers.snapshot_repository import SupplierSnapshotRepository


class SupplierSnapshotCandidateService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SupplierSnapshotRepository(session)
        self.queries = SupplierSnapshotQueryService(session)

    async def preview(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
        *,
        created_from: datetime | None,
        created_to: datetime | None,
        older_than: datetime | None,
        storage_state: str | None,
        override_preserve_online: bool,
        limit: int,
    ) -> tuple[list[dict[str, object]], int, int]:
        bounded = min(limit, settings.snapshot_archive_candidate_limit)
        snapshots, _ = await self.queries.list_snapshots(
            supplier_id,
            source_id,
            status=None,
            storage_state=storage_state,
            created_from=created_from,
            created_to=created_to or older_than,
            limit=bounded,
            offset=0,
        )
        rows: list[dict[str, object]] = []
        estimated_items = 0
        estimated_bytes = 0
        for snapshot in snapshots:
            reasons = await self._exclusions(snapshot, override_preserve_online)
            payload_bytes = (
                await self.repository.active_payload_bytes(snapshot.id)
                if snapshot.storage_state == "ONLINE"
                else 0
            )
            eligible = not reasons
            if eligible:
                estimated_items += snapshot.total_items
                estimated_bytes += payload_bytes
            rows.append(
                {
                    "snapshot_id": snapshot.id,
                    "snapshot_code": snapshot.snapshot_code,
                    "created_at": snapshot.created_at,
                    "total_items": snapshot.total_items,
                    "estimated_payload_bytes": payload_bytes,
                    "eligible": eligible,
                    "exclusion_reasons": reasons,
                }
            )
        return rows, estimated_items, estimated_bytes

    async def _exclusions(
        self,
        snapshot: SupplierSnapshot,
        override_preserve_online: bool,
    ) -> list[str]:
        reasons: list[str] = []
        if snapshot.status != "READY":
            reasons.append("snapshot_not_ready")
        if snapshot.storage_state != "ONLINE":
            reasons.append("snapshot_not_online")
        if snapshot.legal_hold:
            reasons.append("snapshot_legal_hold")
        if snapshot.preserve_online and not override_preserve_online:
            reasons.append("snapshot_preserve_online")
        if await self.repository.has_unresolved_operation(snapshot.id):
            reasons.append("snapshot_archive_operation_unresolved")
        if not reasons:
            _, valid, _ = await self.queries.verify_integrity(
                snapshot.supplier_id,
                snapshot.source_connection_id,
                snapshot.id,
            )
            if not valid:
                reasons.append("snapshot_integrity_failed")
        return reasons


__all__ = ["SupplierSnapshotCandidateService"]
