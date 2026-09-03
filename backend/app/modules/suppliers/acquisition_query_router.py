from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.acquisition_query_service import (
    SupplierAcquisitionQueryService,
)
from app.modules.suppliers.acquisition_schemas import (
    AcquisitionIssueListResponse,
    AcquisitionIssueRead,
    AcquisitionRunListResponse,
    AcquisitionRunRead,
    AcquisitionStatistics,
    StagedRecordListResponse,
    StagedRecordRead,
    StagedRecordSummary,
)
from app.modules.suppliers.enums import (
    AcquisitionIssueSeverity,
    AcquisitionRecordStatus,
    AcquisitionStatus,
    AcquisitionTriggerType,
)

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources/{source_id}/acquisitions",
    tags=["supplier-acquisition-engine"],
)


@router.get(
    "",
    response_model=AcquisitionRunListResponse,
    summary="Prikaži Acquisition Runs",
    description="Vraća ograničenu listu izvršenja bez velikih staged payload-a.",
)
async def list_runs(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_status: AcquisitionStatus | None = Query(default=None, alias="status"),
    trigger_type: AcquisitionTriggerType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> AcquisitionRunListResponse:
    rows, total = await SupplierAcquisitionQueryService(session).list_runs(
        supplier_id,
        source_id,
        status=run_status.value if run_status else None,
        trigger_type=trigger_type.value if trigger_type else None,
        limit=limit,
        offset=offset,
    )
    return AcquisitionRunListResponse(
        items=[AcquisitionRunRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{run_id}",
    response_model=AcquisitionRunRead,
    summary="Prikaži Acquisition Run",
    description="Vraća lifecycle, artifact metadata, brojila i sanitizovan neuspeh.",
)
async def get_run(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AcquisitionRunRead:
    return AcquisitionRunRead.model_validate(
        await SupplierAcquisitionQueryService(session).get_run(
            supplier_id,
            source_id,
            run_id,
        )
    )


@router.get(
    "/{run_id}/statistics",
    response_model=AcquisitionStatistics,
    summary="Prikaži statistiku run-a",
    description=(
        "Brojila tačno odgovaraju persisted staged zapisima i row-level problemima. "
        "PARTIALLY_SUCCEEDED znači da postoje i prihvaćeni i odbijeni redovi."
    ),
)
async def get_statistics(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AcquisitionStatistics:
    run = await SupplierAcquisitionQueryService(session).get_run(
        supplier_id,
        source_id,
        run_id,
    )
    return AcquisitionStatistics(
        run_id=run.id,
        status=AcquisitionStatus(run.status),
        total_record_count=run.total_record_count,
        accepted_record_count=run.accepted_record_count,
        rejected_record_count=run.rejected_record_count,
        warning_count=run.warning_count,
        error_count=run.error_count,
    )


@router.get(
    "/{run_id}/records",
    response_model=StagedRecordListResponse,
    summary="Prikaži staged zapise",
    description=(
        "Lista namerno izostavlja raw_data i mapped_data. Staged zapis nije "
        "Product niti Snapshot; detaljni payload je dostupan pojedinačnim GET-om."
    ),
)
async def list_records(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    record_status: AcquisitionRecordStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> StagedRecordListResponse:
    rows, total = await SupplierAcquisitionQueryService(session).list_records(
        supplier_id,
        source_id,
        run_id,
        status=record_status.value if record_status else None,
        limit=limit,
        offset=offset,
    )
    return StagedRecordListResponse(
        items=[StagedRecordSummary.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{run_id}/records/{record_id}",
    response_model=StagedRecordRead,
    summary="Prikaži staged zapis",
    description="Vraća nepromenljivi raw i mapped JSONB sadržaj jednog reda.",
)
async def get_record(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    record_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> StagedRecordRead:
    return StagedRecordRead.model_validate(
        await SupplierAcquisitionQueryService(session).get_record(
            supplier_id,
            source_id,
            run_id,
            record_id,
        )
    )


@router.get(
    "/{run_id}/issues",
    response_model=AcquisitionIssueListResponse,
    summary="Prikaži row-level upozorenja i greške",
    description=(
        "Vraća stabilne kodove i sanitizovane poruke bez stack trace-a, tajni, "
        "kompletnih fajlova ili dugih opisa."
    ),
)
async def list_issues(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    severity: AcquisitionIssueSeverity | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> AcquisitionIssueListResponse:
    rows, total = await SupplierAcquisitionQueryService(session).list_issues(
        supplier_id,
        source_id,
        run_id,
        severity=severity.value if severity else None,
        limit=limit,
        offset=offset,
    )
    return AcquisitionIssueListResponse(
        items=[AcquisitionIssueRead.model_validate(row) for row in rows],
        total=total,
    )


__all__ = ["router"]
