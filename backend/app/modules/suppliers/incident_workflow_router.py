from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.incident_query_service import SupplierIncidentQueryService
from app.modules.suppliers.incident_schemas import (
    AssignRequest, DueDateRequest, IncidentActionReason, IncidentRead, LinkCreate,
    LinkList, LinkRead, PriorityRequest, ResolveRequest, SuppressRequest,
)
from app.modules.suppliers.incident_service import SupplierIncidentService

router = APIRouter(prefix="/supplier-incidents", tags=["supplier-incident-center"])


@router.post("/{incident_id}/acknowledge", response_model=IncidentRead, summary="Potvrdi Incident", description="OPEN Incident prelazi u ACKNOWLEDGED uz audit događaj.")
async def acknowledge(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).transition(incident_id, "ACKNOWLEDGED"))


@router.post("/{incident_id}/start", response_model=IncidentRead, summary="Pokreni istragu", description="Prebacuje dozvoljeni Incident u IN_PROGRESS.")
async def start(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).transition(incident_id, "IN_PROGRESS"))


@router.post("/{incident_id}/assign", response_model=IncidentRead, summary="Dodeli Incident", description="Dodeljuje Foundation autentifikacioni subject i zapisuje audit događaj.")
async def assign(incident_id: uuid.UUID, payload: AssignRequest, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).assign(incident_id, payload.assigned_user_id))


@router.post("/{incident_id}/unassign", response_model=IncidentRead, summary="Ukloni dodelu", description="Uklanja assignee bez brisanja prethodne istorije.")
async def unassign(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).assign(incident_id, None))


@router.post("/{incident_id}/priority", response_model=IncidentRead, summary="Promeni prioritet", description="Menja operativnu hitnost bez promene severity vrednosti.")
async def priority(incident_id: uuid.UUID, payload: PriorityRequest, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).priority(incident_id, payload.priority.value))


@router.post("/{incident_id}/due-date", response_model=IncidentRead, summary="Promeni rok", description="Postavlja ili uklanja due_at uz audit događaj; ne šalje notifikaciju.")
async def due_date(incident_id: uuid.UUID, payload: DueDateRequest, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).due_date(incident_id, payload.due_at))


@router.post("/{incident_id}/resolve", response_model=IncidentRead, summary="Reši Incident", description="Zahteva resolution code i summary; recurrence ponovo otvara isti Incident.")
async def resolve(incident_id: uuid.UUID, payload: ResolveRequest, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).transition(incident_id, "RESOLVED", reason=payload.resolution_summary, resolution_code=payload.resolution_code))


@router.post("/{incident_id}/dismiss", response_model=IncidentRead, summary="Odbaci Incident", description="DISMISSED zahteva razlog i čuva kompletnu istoriju.")
async def dismiss(incident_id: uuid.UUID, payload: IncidentActionReason, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).transition(incident_id, "DISMISSED", reason=payload.reason))


@router.post("/{incident_id}/suppress", response_model=IncidentRead, summary="Potisni Incident", description="Potiskivanje sprečava aktivni duplikat, ali svaka pojava ostaje auditovana.")
async def suppress(incident_id: uuid.UUID, payload: SuppressRequest, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).transition(incident_id, "SUPPRESSED", reason=payload.reason, suppression_until=payload.suppression_until))


@router.post("/{incident_id}/reopen", response_model=IncidentRead, summary="Ponovo otvori Incident", description="Vraća terminalni ili potisnuti Incident u OPEN bez brisanja resolution istorije.")
async def reopen(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).transition(incident_id, "OPEN"))


@router.post("/{incident_id}/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED, summary="Poveži Incidente", description="Dodaje PARENT, CHILD ili RELATED vezu bez destruktivnog spajanja.")
async def link(incident_id: uuid.UUID, payload: LinkCreate, session: AsyncSession = Depends(get_db)) -> LinkRead:
    return LinkRead.model_validate(await SupplierIncidentService(session).link(incident_id, payload.related_incident_id, payload.relationship_type))


@router.get("/{incident_id}/links", response_model=LinkList, summary="Prikaži povezane Incidente", description="Vraća korelacione veze i čuva oba Incidenta.")
async def links(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> LinkList:
    service = SupplierIncidentQueryService(session)
    await service.get(incident_id)
    rows = await service.repository.links(incident_id)
    return LinkList(items=[LinkRead.model_validate(row) for row in rows], total=len(rows))


__all__ = ["router"]
