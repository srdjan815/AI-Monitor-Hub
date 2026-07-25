from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.enums import SnapshotStorageState
from app.modules.suppliers.snapshot_archive_service import (
    SupplierSnapshotArchiveService,
)
from app.modules.suppliers.snapshot_candidate_service import (
    SupplierSnapshotCandidateService,
)
from app.modules.suppliers.snapshot_bulk_archive_service import (
    SupplierSnapshotBulkArchiveService,
)
from app.modules.suppliers.snapshot_query_service import SupplierSnapshotQueryService
from app.modules.suppliers.snapshot_schemas import (
    SnapshotArchiveExportRequest,
    SnapshotArchiveOperationRead,
    SnapshotBulkArchiveRequest,
    SnapshotBulkArchiveResult,
    SnapshotCandidateRead,
    SnapshotCandidateResponse,
    SnapshotIntegrityRead,
    SnapshotOffloadConfirm,
    SnapshotRead,
)

router = APIRouter(tags=["supplier-snapshot-archive"])


@router.get(
    "/suppliers/{supplier_id}/snapshots/archive-candidates",
    response_model=SnapshotCandidateResponse,
    summary="Pregledaj kandidate za arhiviranje",
    description=(
        "Prikazuje deterministički ograničene kandidate, procenu payload-a i "
        "razloge isključenja. Legal hold nikada nije kandidat."
    ),
)
async def preview_archive_candidates(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    older_than: datetime | None = None,
    storage_state: SnapshotStorageState | None = None,
    override_preserve_online: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> SnapshotCandidateResponse:
    rows, items, payload_bytes = await SupplierSnapshotCandidateService(
        session
    ).preview(
        supplier_id,
        source_id,
        created_from=created_from,
        created_to=created_to,
        older_than=older_than,
        storage_state=storage_state.value if storage_state else None,
        override_preserve_online=override_preserve_online,
        limit=limit,
    )
    return SnapshotCandidateResponse(
        items=[SnapshotCandidateRead.model_validate(row) for row in rows],
        estimated_item_count=items,
        estimated_active_payload_bytes=payload_bytes,
    )


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/snapshots/{snapshot_id}/verify",
    response_model=SnapshotIntegrityRead,
    summary="Verifikuj Snapshot integritet",
    description="Ponovo računa Item i kompletan Snapshot fingerprint bez Delta analize.",
)
async def verify_snapshot(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotIntegrityRead:
    snapshot, valid, code = await SupplierSnapshotQueryService(
        session
    ).verify_integrity(supplier_id, source_id, snapshot_id)
    return SnapshotIntegrityRead(snapshot_id=snapshot.id, valid=valid, code=code)


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/snapshots/{snapshot_id}/archive",
    response_model=SnapshotArchiveOperationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Izvezi i verifikuj Snapshot arhivu",
    description=(
        "Kreira prenosivi ZIP paket formata 1, proverava checksum-e i registruje "
        "arhivu. Ova operacija ne uklanja aktivne Snapshot Items."
    ),
)
async def export_snapshot(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    payload: SnapshotArchiveExportRequest,
    session: AsyncSession = Depends(get_db),
) -> SnapshotArchiveOperationRead:
    operation = await SupplierSnapshotArchiveService(session).export(
        supplier_id,
        source_id,
        snapshot_id,
        include_source_artifact=payload.include_source_artifact,
    )
    return SnapshotArchiveOperationRead.model_validate(operation)


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/snapshots/archive-bulk",
    response_model=SnapshotBulkArchiveResult,
    summary="Izvezi izabrane Snapshot arhive",
    description=(
        "Obrađuje ograničen skup determinističkim redosledom i odvojeno prijavljuje "
        "uspešne i neuspešne izvoze; delimičan rezultat se ne prikazuje kao potpun."
    ),
)
async def export_snapshots_bulk(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SnapshotBulkArchiveRequest,
    session: AsyncSession = Depends(get_db),
) -> SnapshotBulkArchiveResult:
    succeeded, failed = await SupplierSnapshotBulkArchiveService(session).export(
        supplier_id,
        source_id,
        [uuid.UUID(value) for value in payload.snapshot_ids],
        include_source_artifact=payload.include_source_artifact,
    )
    return SnapshotBulkArchiveResult(
        succeeded=[
            SnapshotArchiveOperationRead.model_validate(operation)
            for operation in succeeded
        ],
        failed=failed,
    )


@router.get(
    "/suppliers/{supplier_id}/sources/{source_id}/snapshots/{snapshot_id}/archives/{operation_id}",
    response_model=SnapshotArchiveOperationRead,
    summary="Prikaži rezultat arhiviranja",
    description="Vraća verifikacioni status i bezbednu relativnu archive referencu.",
)
async def get_archive_operation(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    operation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotArchiveOperationRead:
    return SnapshotArchiveOperationRead.model_validate(
        await SupplierSnapshotQueryService(session).archive_operation(
            supplier_id, source_id, snapshot_id, operation_id
        )
    )


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/snapshots/{snapshot_id}/offload",
    response_model=SnapshotRead,
    summary="Potvrdi offload Snapshot payload-a",
    description=(
        "Zasebna eksplicitna operacija: ponovo proverava arhivu, checksum, legal "
        "hold i identitet, zatim uklanja teške Item redove i označava ARCHIVED."
    ),
)
async def confirm_snapshot_offload(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    payload: SnapshotOffloadConfirm,
    session: AsyncSession = Depends(get_db),
) -> SnapshotRead:
    snapshot = await SupplierSnapshotArchiveService(session).confirm_offload(
        supplier_id,
        source_id,
        snapshot_id,
        payload.operation_id,
        archive_reference=payload.archive_reference,
        archive_checksum=payload.archive_checksum,
        override_preserve_online=payload.override_preserve_online,
    )
    return SnapshotRead.model_validate(snapshot)


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/snapshots/{snapshot_id}/restore",
    response_model=SnapshotRead,
    summary="Obnovi arhivirani Snapshot",
    description=(
        "Verifikuje prenosivu arhivu i transakciono vraća iste Snapshot Items i "
        "isti logički Snapshot identitet u ONLINE stanje."
    ),
)
async def restore_snapshot(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SnapshotRead:
    return SnapshotRead.model_validate(
        await SupplierSnapshotArchiveService(session).restore(
            supplier_id, source_id, snapshot_id
        )
    )


__all__ = ["router"]
