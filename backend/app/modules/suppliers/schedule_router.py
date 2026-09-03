from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.schedule_schemas import (
    PipelineRunNowRequest,
    PipelineRunQueued,
    SupplierScheduleList,
    SupplierScheduleRead,
    SupplierScheduleWrite,
)
from app.modules.suppliers.incident_schemas import IncidentRead
from app.modules.suppliers.schedule_service import SupplierScheduleService

router = APIRouter(tags=["supplier-automation"])


@router.get(
    "/suppliers/{supplier_id}/sources/{source_id}/schedule",
    response_model=SupplierScheduleRead | None,
    summary="PrikaÅ¾i automatski raspored konekcije",
)
async def get_schedule(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> SupplierScheduleRead | None:
    schedule = await SupplierScheduleService(session).get(supplier_id, source_id)
    if schedule is None:
        response.status_code = status.HTTP_200_OK
    return schedule


@router.put(
    "/suppliers/{supplier_id}/sources/{source_id}/schedule",
    response_model=SupplierScheduleRead,
    summary="Podesi automatsko izvrÅ¡avanje",
)
async def save_schedule(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SupplierScheduleWrite,
    session: AsyncSession = Depends(get_db),
) -> SupplierScheduleRead:
    return await SupplierScheduleService(session).save(
        supplier_id, source_id, payload
    )


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/schedule-readiness-incident",
    response_model=IncidentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Evidentiraj da konekcija nije spremna za automatski raspored",
)
async def report_schedule_readiness_incident(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> IncidentRead:
    incident = await SupplierScheduleService(session).report_not_ready(
        supplier_id, source_id
    )
    return IncidentRead.model_validate(incident)


@router.post(
    "/suppliers/{supplier_id}/sources/{source_id}/pipeline-runs",
    response_model=PipelineRunQueued,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Pokreni Supplier Pipeline sada",
)
async def run_pipeline_now(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: PipelineRunNowRequest,
    session: AsyncSession = Depends(get_db),
) -> PipelineRunQueued:
    return await SupplierScheduleService(session).run_now(
        supplier_id, source_id, payload
    )


@router.get(
    "/suppliers/platform/source-schedules",
    response_model=SupplierScheduleList,
    summary="PrikaÅ¾i sve automatske rasporede",
)
async def list_schedules(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> SupplierScheduleList:
    return await SupplierScheduleService(session).list(limit=limit, offset=offset)


__all__ = ["router"]
