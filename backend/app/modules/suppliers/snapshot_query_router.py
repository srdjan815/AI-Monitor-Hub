from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.enums import SnapshotStatus, SnapshotStorageState
from app.modules.suppliers.snapshot_query_service import SupplierSnapshotQueryService
from app.modules.suppliers.snapshot_schemas import (
    SnapshotImageLinks,
    SnapshotItemListResponse,
    SnapshotItemRead,
    SnapshotItemSummary,
    SnapshotListResponse,
    SnapshotRead,
    SnapshotStatistics,
)

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources/{source_id}/snapshots",
    tags=["supplier-snapshot-engine"],
)


@router.get(
    "",
    response_model=SnapshotListResponse,
    summary="Prikaži Snapshot-e",
    description="Vraća ograničenu listu bez velikog mapped_data sadržaja.",
)
async def list_snapshots(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_status: SnapshotStatus | None = Query(default=None, alias="status"),
    storage_state: SnapshotStorageState | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> SnapshotListResponse:
    rows, total = await SupplierSnapshotQueryService(session).list_snapshots(
        supplier_id,
        source_id,
        status=snapshot_status.value if snapshot_status else None,
        storage_state=storage_state.value if storage_state else None,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return SnapshotListResponse(
        items=[SnapshotRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{snapshot_id}",
    response_model=SnapshotRead,
    summary="Prikaži Snapshot",
    description=(
        "Vraća trajni identitet, lifecycle, fingerprint, retention i archive "
        "metapodatke Snapshot-a."
    ),
)
async def get_snapshot(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotRead:
    return SnapshotRead.model_validate(
        await SupplierSnapshotQueryService(session).get(
            supplier_id, source_id, snapshot_id
        )
    )


@router.get(
    "/{snapshot_id}/statistics",
    response_model=SnapshotStatistics,
    summary="Prikaži Snapshot statistiku",
    description=(
        "Razdvaja trajni broj stavki od trenutno aktivnog payload-a. ARCHIVED "
        "Snapshot zadržava total_items iako su teške stavke offload-ovane."
    ),
)
async def snapshot_statistics(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotStatistics:
    service = SupplierSnapshotQueryService(session)
    snapshot, active_items, active_bytes = await service.statistics(
        supplier_id, source_id, snapshot_id
    )
    return SnapshotStatistics(
        snapshot_id=snapshot.id,
        status=SnapshotStatus(snapshot.status),
        storage_state=SnapshotStorageState(snapshot.storage_state),
        total_items=snapshot.total_items,
        active_item_count=active_items,
        estimated_active_payload_bytes=active_bytes,
    )


@router.get(
    "/{snapshot_id}/items",
    response_model=SnapshotItemListResponse,
    summary="Prikaži Snapshot Items",
    description=(
        "Vraća sažetu paginiranu listu samo za ONLINE Snapshot. ARCHIVED Snapshot "
        "mora prvo biti obnovljen."
    ),
)
async def list_snapshot_items(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> SnapshotItemListResponse:
    rows, total = await SupplierSnapshotQueryService(session).list_items(
        supplier_id,
        source_id,
        snapshot_id,
        limit=limit,
        offset=offset,
    )
    return SnapshotItemListResponse(
        items=[SnapshotItemSummary.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{snapshot_id}/items/{item_id}",
    response_model=SnapshotItemRead,
    summary="Prikaži Snapshot Item",
    description=(
        "Vraća potpuni immutable mapped_data, uključujući dugačke Unicode, HTML "
        "i višelinijske vrednosti."
    ),
)
async def get_snapshot_item(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotItemRead:
    return SnapshotItemRead.model_validate(
        await SupplierSnapshotQueryService(session).get_item(
            supplier_id, source_id, snapshot_id, item_id
        )
    )


@router.get(
    "/{snapshot_id}/items/{item_id}/image-links",
    response_model=SnapshotImageLinks,
    summary="Prikaži supplier image linkove",
    description=(
        "Vraća normalizovane reference bez preuzimanja ili čuvanja binarnih slika."
    ),
)
async def get_snapshot_image_links(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotImageLinks:
    item = await SupplierSnapshotQueryService(session).get_item(
        supplier_id, source_id, snapshot_id, item_id
    )
    return SnapshotImageLinks(snapshot_item_id=item.id, links=item.source_image_links)


__all__ = ["router"]
