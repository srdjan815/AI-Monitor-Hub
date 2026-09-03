from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.api_schemas import (
    BulkIncidentAssignRequest,
    BulkIncidentPriorityRequest,
    BulkOperationResponse,
    CANONICAL_ERROR_RESPONSES,
    SupplierApiPage,
    SupplierPlatformOverview,
    SupplierPlatformSearchResponse,
)
from app.modules.suppliers.api_service import SupplierApiService
from app.modules.suppliers.incident_query_service import SupplierIncidentQueryService
from app.modules.suppliers.incident_schemas import IncidentRead

router = APIRouter(
    prefix="/suppliers/platform",
    tags=["supplier-platform-api"],
    responses=CANONICAL_ERROR_RESPONSES,
)


@router.get(
    "/overview",
    response_model=SupplierPlatformOverview,
    summary="Prikaži pregled Supplier Platforme",
    description=(
        "Vraća ograničene agregate samo za domene koje prijavljeni korisnik sme "
        "da čita. Ne učitava sirove datoteke, payload-e ni tehničke dokaze."
    ),
)
async def supplier_platform_overview(
    range_from: datetime | None = Query(
        default=None,
        description="Početak vremenskog opsega; podrazumevano poslednjih 30 dana.",
    ),
    range_to: datetime | None = Query(
        default=None,
        description="Kraj vremenskog opsega; najviše 366 dana od početka.",
    ),
    session: AsyncSession = Depends(get_db),
) -> SupplierPlatformOverview:
    return await SupplierApiService(session).overview(
        range_from=range_from,
        range_to=range_to,
    )


@router.get(
    "/search",
    response_model=SupplierPlatformSearchResponse,
    summary="Pretraži Supplier Platformu",
    description=(
        "Bezbedno pretražuje samo šifre i kratke nazive dozvoljenih resursa. "
        "Tajne, sirovi zapisi, mapirani payload-i i dugi opisi nisu obuhvaćeni."
    ),
)
async def supplier_platform_search(
    query: str = Query(
        min_length=2,
        max_length=100,
        description="Šifra ili kratak naziv; najmanje dva znaka.",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=settings.supplier_api_max_search_results,
        description="Najveći broj rezultata.",
    ),
    session: AsyncSession = Depends(get_db),
) -> SupplierPlatformSearchResponse:
    return await SupplierApiService(session).search(query, limit=limit)


@router.get(
    "/incidents",
    response_model=SupplierApiPage,
    summary="Prikaži Incidente kroz objedinjeni API",
    description=(
        "Kanonska, ograničena Incident kolekcija sa doslednom paginacijom, "
        "dozvoljenim sortiranjem i bez kompletnog tehničkog konteksta."
    ),
)
async def canonical_incidents(
    supplier_id: uuid.UUID | None = None,
    source_connection_id: uuid.UUID | None = None,
    incident_status: str | None = Query(default=None, alias="status", max_length=20),
    severity: str | None = Query(default=None, max_length=16),
    priority: str | None = Query(default=None, max_length=4),
    assigned_user_id: str | None = Query(default=None, max_length=255),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    query: str | None = Query(default=None, min_length=2, max_length=100),
    sort_by: Literal[
        "created_at",
        "updated_at",
        "incident_code",
        "severity",
        "priority",
        "status",
        "due_at",
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: int = Query(
        default=50,
        ge=1,
        le=settings.supplier_api_max_page_size,
    ),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> SupplierApiPage:
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(
            422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "created_from ne sme biti posle created_to",
            },
        )
    rows, total = await SupplierIncidentQueryService(
        session
    ).repository.list_incidents(
        supplier_id=supplier_id,
        source_id=source_connection_id,
        status=incident_status,
        severity=severity,
        priority=priority,
        incident_type=None,
        source_domain=None,
        assigned_user=assigned_user_id,
        unassigned=None,
        overdue=None,
        created_from=created_from,
        created_to=created_to,
        search=query,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return SupplierApiPage(
        items=[IncidentRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(rows) < total,
    )


@router.post(
    "/bulk/incidents/assign",
    response_model=BulkOperationResponse,
    summary="Grupno dodeli Incidente",
    description=(
        "Obrađuje najviše konfigurisani broj Incidenata, po jednoj transakciji "
        "za svaku stavku, i vraća iskren rezultat za svaku referencu."
    ),
)
async def bulk_assign_incidents(
    payload: BulkIncidentAssignRequest,
    session: AsyncSession = Depends(get_db),
) -> BulkOperationResponse:
    return await SupplierApiService(session).bulk_assign(payload)


@router.post(
    "/bulk/incidents/priority",
    response_model=BulkOperationResponse,
    summary="Grupno promeni prioritet Incidenata",
    description=(
        "Menja samo operativni prioritet izabranih Incidenata. Severity i "
        "izvorni Acquisition, Snapshot i Delta ostaju nepromenjeni."
    ),
)
async def bulk_prioritize_incidents(
    payload: BulkIncidentPriorityRequest,
    session: AsyncSession = Depends(get_db),
) -> BulkOperationResponse:
    return await SupplierApiService(session).bulk_priority(payload)


__all__ = ["router"]
