from __future__ import annotations

import uuid
from typing import cast

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.incident_schemas import IncidentRead, IncidentSyncCandidateResponse
from app.modules.suppliers.incident_sync_service import SupplierIncidentSyncService

router = APIRouter(prefix="/supplier-incidents/sync", tags=["supplier-incident-center"])


async def _sync(domain: str, source_id: uuid.UUID, preview: bool, session: AsyncSession) -> list[IncidentRead] | IncidentSyncCandidateResponse:
    service = SupplierIncidentSyncService(session)
    result = await (
        service.sync_acquisition(source_id, preview=preview)
        if domain == "acquisition"
        else service.sync_snapshot(source_id, preview=preview)
        if domain == "snapshot"
        else service.sync_delta(source_id, preview=preview)
    )
    if preview:
        return IncidentSyncCandidateResponse(source_domain=domain.upper(), source_id=source_id, candidates=cast(list[dict[str, object]], result))
    return [IncidentRead.model_validate(row) for row in cast(list[object], result)]


@router.get("/acquisition-runs/{source_id}/preview", response_model=IncidentSyncCandidateResponse, summary="Pregled Acquisition Incident kandidata", description="Čita persisted činjenice bez retry-a ili izmene Acquisition Run-a.")
async def preview_acquisition(source_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentSyncCandidateResponse:
    return cast(IncidentSyncCandidateResponse, await _sync("acquisition", source_id, True, session))


@router.post("/acquisition-runs/{source_id}", response_model=list[IncidentRead], summary="Sinhronizuj Acquisition Incidente", description="Kreira ili deduplikuje Incidente iz persisted failure činjenica.")
async def sync_acquisition(source_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> list[IncidentRead]:
    return cast(list[IncidentRead], await _sync("acquisition", source_id, False, session))


@router.get("/snapshot-records/{source_id}/preview", response_model=IncidentSyncCandidateResponse, summary="Pregled Snapshot Incident kandidata", description="Ne obnavlja Snapshot niti menja archive operaciju.")
async def preview_snapshot(source_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentSyncCandidateResponse:
    return cast(IncidentSyncCandidateResponse, await _sync("snapshot", source_id, True, session))


@router.post("/snapshot-records/{source_id}", response_model=list[IncidentRead], summary="Sinhronizuj Snapshot Incidente", description="Kreira workflow samo iz postojećih Snapshot failure činjenica.")
async def sync_snapshot(source_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> list[IncidentRead]:
    return cast(list[IncidentRead], await _sync("snapshot", source_id, False, session))


@router.get("/delta-runs/{source_id}/preview", response_model=IncidentSyncCandidateResponse, summary="Pregled Delta Incident kandidata", description="Anomaly signal je činjenica; pregled ne računa novi Delta.")
async def preview_delta(source_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentSyncCandidateResponse:
    return cast(IncidentSyncCandidateResponse, await _sync("delta", source_id, True, session))


@router.post("/delta-runs/{source_id}", response_model=list[IncidentRead], summary="Sinhronizuj Delta Incidente", description="Pretvara omogućene anomaly signale u Incidente bez izmene Delta podataka.")
async def sync_delta(source_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> list[IncidentRead]:
    return cast(list[IncidentRead], await _sync("delta", source_id, False, session))


__all__ = ["router"]
