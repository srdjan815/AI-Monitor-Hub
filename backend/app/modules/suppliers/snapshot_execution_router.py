from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.snapshot_schemas import SnapshotCreate, SnapshotRead
from app.modules.suppliers.snapshot_service import SupplierSnapshotService

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources/{source_id}/snapshots",
    tags=["supplier-snapshot-engine"],
)


@router.post(
    "",
    response_model=SnapshotRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj Snapshot iz Acquisition Run-a",
    description=(
        "Kreira jednu kanonsku, nepromenljivu tačku stanja samo iz prihvaćenih "
        "staged zapisa uspešnog Acquisition Run-a. Ne parsira izvor ponovo, ne "
        "računa Delta i ne upisuje Catalog podatke."
    ),
)
async def create_snapshot(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SnapshotCreate,
    session: AsyncSession = Depends(get_db),
) -> SnapshotRead:
    snapshot = await SupplierSnapshotService(session).create(
        supplier_id,
        source_id,
        payload.acquisition_run_id,
        retention_class=payload.retention_class,
        archive_after_days=payload.archive_after_days,
        preserve_online=payload.preserve_online,
        legal_hold=payload.legal_hold,
        archive_notes=payload.archive_notes,
    )
    return SnapshotRead.model_validate(snapshot)


__all__ = ["router"]
