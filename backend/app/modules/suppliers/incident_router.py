from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.incident_query_service import SupplierIncidentQueryService
from app.modules.suppliers.incident_schemas import (
    CommentCreate, CommentList, CommentRead, EventList, EventRead, IncidentList,
    IncidentRead, ManualIncidentCreate, SummaryRead,
)
from app.modules.suppliers.incident_service import SupplierIncidentService

router = APIRouter(prefix="/supplier-incidents", tags=["supplier-incident-center"])


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED, summary="Kreiraj ručni Incident", description="Kreira MANUAL operativni Incident bez izmene dobavljačkih ili Catalog podataka.")
async def create_manual(payload: ManualIncidentCreate, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentService(session).manual(payload))


@router.get("", response_model=IncidentList, summary="Prikaži Incidente", description="Ograničena pretraga bez source fajlova, tajni i kompletnog tehničkog konteksta.")
async def list_incidents(
    supplier_id: uuid.UUID | None = None,
    source_connection_id: uuid.UUID | None = None,
    incident_status: str | None = Query(default=None, alias="status", max_length=20),
    severity: str | None = Query(default=None, max_length=16),
    priority: str | None = Query(default=None, max_length=4),
    incident_type: str | None = Query(default=None, max_length=64),
    source_domain: str | None = Query(default=None, max_length=32),
    assigned_user_id: str | None = Query(default=None, max_length=255),
    unassigned: bool | None = None,
    overdue: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> IncidentList:
    rows, total = await SupplierIncidentQueryService(session).repository.list_incidents(
        supplier_id=supplier_id, source_id=source_connection_id,
        status=incident_status, severity=severity, priority=priority,
        incident_type=incident_type, source_domain=source_domain,
        assigned_user=assigned_user_id, unassigned=unassigned, overdue=overdue,
        created_from=created_from, created_to=created_to, search=search,
        limit=limit, offset=offset,
    )
    return IncidentList(items=[IncidentRead.model_validate(row) for row in rows], total=total)


@router.get("/summary", response_model=SummaryRead, summary="Prikaži Incident sažetak", description="Vraća aktivne statuse, prioritete, kašnjenje i raspodelu za budući dashboard.")
async def summary(supplier_id: uuid.UUID | None = None, session: AsyncSession = Depends(get_db)) -> SummaryRead:
    return SummaryRead.model_validate(await SupplierIncidentQueryService(session).summary(supplier_id))


@router.get("/{incident_id}", response_model=IncidentRead, summary="Prikaži Incident", description="Incident je operativni workflow; izvorni Acquisition, Snapshot i Delta ostaju nepromenjeni.")
async def get_incident(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return IncidentRead.model_validate(await SupplierIncidentQueryService(session).get(incident_id))


@router.get("/{incident_id}/evidence", response_model=IncidentRead, summary="Prikaži reference dokaza", description="Vraća bezbedne reference, bez source payload-a, stack trace-a ili tajni.")
async def evidence(incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    return await get_incident(incident_id, session)


@router.get("/{incident_id}/events", response_model=EventList, summary="Prikaži audit događaje", description="Immutable istorija pojave, statusa, dodele, komentara i korelacije.")
async def events(incident_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET), session: AsyncSession = Depends(get_db)) -> EventList:
    service = SupplierIncidentQueryService(session)
    await service.get(incident_id)
    rows, total = await service.repository.events(incident_id, limit=limit, offset=offset)
    return EventList(items=[EventRead.model_validate(row) for row in rows], total=total)


@router.get("/{incident_id}/comments", response_model=CommentList, summary="Prikaži komentare", description="Paginirani bezbedni plain-text komentari.")
async def comments(incident_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET), session: AsyncSession = Depends(get_db)) -> CommentList:
    service = SupplierIncidentQueryService(session)
    await service.get(incident_id)
    rows, total = await service.repository.comments(incident_id, limit=limit, offset=offset)
    return CommentList(items=[CommentRead.model_validate(row) for row in rows], total=total)


@router.post("/{incident_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED, summary="Dodaj komentar", description="Dodaje sanitizovan komentar i atomarni COMMENT_ADDED audit događaj.")
async def add_comment(incident_id: uuid.UUID, payload: CommentCreate, session: AsyncSession = Depends(get_db)) -> CommentRead:
    return CommentRead.model_validate(await SupplierIncidentService(session).comment(incident_id, payload.body))


__all__ = ["router"]
