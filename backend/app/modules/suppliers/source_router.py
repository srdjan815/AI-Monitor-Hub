from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import encode_time_keyset, resolve_time_keyset
from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.core.pagination import InvalidCursorError
from app.db.session import get_db
from app.modules.suppliers.enums import SupplierSourceStatus, SupplierSourceType
from app.modules.suppliers.source_schemas import (
    SupplierSourceCreate,
    SupplierSourceListResponse,
    SupplierSourceRead,
    SupplierSourceUpdate,
    SupplierSourceValidationResponse,
)
from app.modules.suppliers.source_service import SupplierSourceService

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources",
    tags=["supplier-source-connections"],
)


@router.post(
    "",
    response_model=SupplierSourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj izvor dobavljača",
    description=(
        "Čuva strogo proverenu konfiguraciju bez povezivanja, preuzimanja ili uvoza."
    ),
)
async def create_source(
    supplier_id: uuid.UUID,
    payload: SupplierSourceCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> SupplierSourceRead:
    source = await SupplierSourceService(session).create_source(supplier_id, payload)
    response.headers["Location"] = (
        f"/api/v1/suppliers/{supplier_id}/sources/{source.id}"
    )
    return SupplierSourceRead.model_validate(source)


@router.get(
    "",
    response_model=SupplierSourceListResponse,
    summary="Prikaži izvore dobavljača",
    description="Vraća filtriranu i deterministički sortiranu listu konfiguracija.",
)
async def list_sources(
    supplier_id: uuid.UUID,
    response: Response,
    active_only: bool = Query(
        default=True,
        description="Kada je true, prikazuje samo aktivne zapise.",
    ),
    source_type: SupplierSourceType | None = Query(
        default=None,
        description="Filtrira prema vrsti izvora.",
    ),
    source_status: SupplierSourceStatus | None = Query(
        default=None,
        alias="status",
        description="Filtrira prema operativnom statusu konfiguracije.",
    ),
    name: str | None = Query(default=None, min_length=1, max_length=255),
    source_code: str | None = Query(default=None, min_length=1, max_length=50),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> SupplierSourceListResponse:
    service = SupplierSourceService(session)
    common = {
        "active_only": active_only,
        "source_type": source_type.value if source_type is not None else None,
        "status": source_status.value if source_status is not None else None,
        "name": name.strip() if name else None,
        "source_code": source_code.strip() if source_code else None,
    }
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows, total = await service.list_sources(
            supplier_id,
            **common,
            limit=limit,
            offset=offset,
        )
        return SupplierSourceListResponse(
            items=[SupplierSourceRead.model_validate(row) for row in rows],
            total=total,
        )
    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_CURSOR",
                "message": "Cursor paginacija ne može koristiti offset",
            },
        )
    cursor_filters = {
        **common,
        "supplier_id": str(supplier_id),
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    try:
        keyset = await resolve_time_keyset(
            session,
            cursor=cursor,
            resource="supplier-sources",
            filters=cursor_filters,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc
    rows, total = await service.list_sources(
        supplier_id,
        **common,
        limit=limit + 1,
        offset=0,
        snapshot_at=keyset.snapshot_at,
        after=(
            (keyset.after_at, keyset.after_id)
            if keyset.after_at is not None and keyset.after_id is not None
            else None
        ),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    response.headers["X-Snapshot-At"] = keyset.snapshot_at.isoformat()
    if has_more:
        last = rows[-1]
        response.headers["X-Next-Cursor"] = encode_time_keyset(
            resource="supplier-sources",
            filters=cursor_filters,
            after_at=last.created_at,
            after_id=last.id,
            snapshot_at=keyset.snapshot_at,
        )
    return SupplierSourceListResponse(
        items=[SupplierSourceRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{source_id}",
    response_model=SupplierSourceRead,
    summary="Prikaži izvor dobavljača",
    description="Vraća izvor samo kada pripada dobavljaču iz putanje.",
)
async def get_source(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SupplierSourceRead:
    return SupplierSourceRead.model_validate(
        await SupplierSourceService(session).get_source(supplier_id, source_id)
    )


@router.patch(
    "/{source_id}",
    response_model=SupplierSourceRead,
    summary="Izmeni izvor dobavljača",
    description=(
        "Menja dozvoljena polja uz očekivanu version vrednost. Vrsta i interna "
        "šifra izvora su nepromenljive."
    ),
)
async def update_source(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SupplierSourceUpdate,
    session: AsyncSession = Depends(get_db),
) -> SupplierSourceRead:
    return SupplierSourceRead.model_validate(
        await SupplierSourceService(session).update_source(
            supplier_id,
            source_id,
            payload,
        )
    )


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Arhiviraj izvor dobavljača",
    description="Soft delete čuva istorijsku konfiguraciju i ne izvršava spoljnu akciju.",
)
async def deactivate_source(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierSourceService(session).deactivate_source(supplier_id, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{source_id}/validate",
    response_model=SupplierSourceValidationResponse,
    summary="Proveri konfiguraciju izvora",
    description=(
        "Proverava ispravnost sačuvane konfiguracije bez povezivanja sa spoljnim "
        "sistemom i bez preuzimanja podataka."
    ),
)
async def validate_source(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SupplierSourceValidationResponse:
    return await SupplierSourceService(session).validate_source(
        supplier_id,
        source_id,
    )


__all__ = ["router"]
