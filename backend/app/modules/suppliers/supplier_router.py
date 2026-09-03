from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import encode_time_keyset, resolve_time_keyset
from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.core.pagination import InvalidCursorError
from app.db.session import get_db
from app.modules.suppliers.enums import SupplierStatus
from app.modules.suppliers.schemas import (
    SupplierCreate,
    SupplierListResponse,
    SupplierRead,
    SupplierUpdate,
)
from app.modules.suppliers.service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["supplier-administration"])


@router.post(
    "",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registruj dobavljača",
    description=(
        "Kreira dobavljača i automatski mu dodeljuje nepromenljivu šifru u "
        "formatu SUP-000001. Zahteva dozvolu suppliers.write."
    ),
)
async def create_supplier(
    payload: SupplierCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> SupplierRead:
    supplier = await SupplierService(session).create_supplier(payload)
    response.headers["Location"] = f"/api/v1/suppliers/{supplier.id}"
    return SupplierRead.model_validate(supplier)


@router.get(
    "",
    response_model=SupplierListResponse,
    summary="Prikaži dobavljače",
    description=(
        "Vraća filtriranu i deterministički sortiranu listu dobavljača. "
        "Podržava kompatibilnu offset i potpisanu cursor paginaciju."
    ),
)
async def list_suppliers(
    response: Response,
    active_only: bool = Query(
        default=True,
        description="Kada je true, prikazuje samo aktivne zapise.",
    ),
    supplier_status: SupplierStatus | None = Query(
        default=None,
        alias="status",
        description="Ograničava rezultate na izabrani operativni status.",
    ),
    company_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=500,
        description="Pretraga po delu poslovnog naziva dobavljača.",
    ),
    supplier_code: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
        description="Pretraga po automatski generisanoj šifri dobavljača.",
    ),
    tax_identifier: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description="Tačna pretraga po poreskom identifikacionom broju.",
    ),
    registration_number: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description="Tačna pretraga po registracionom ili matičnom broju.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Najveći broj zapisa u jednoj stranici.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=MAX_LEGACY_OFFSET,
        description="Broj preskočenih zapisa u kompatibilnom offset režimu.",
    ),
    cursor: str | None = Query(
        default=None,
        max_length=MAX_CURSOR_CHARS,
        description="Potpisani pokazivač sledeće stranice.",
    ),
    pagination: Literal["offset", "cursor"] | None = Query(
        default=None,
        description="Izbor offset ili cursor režima paginacije.",
    ),
    session: AsyncSession = Depends(get_db),
) -> SupplierListResponse:
    service = SupplierService(session)
    normalized_tax = tax_identifier.strip().upper() if tax_identifier else None
    normalized_registration = (
        registration_number.strip().upper() if registration_number else None
    )
    cursor_mode = cursor is not None or pagination == "cursor"
    common = {
        "active_only": active_only,
        "status": supplier_status.value if supplier_status is not None else None,
        "company_name": company_name.strip() if company_name else None,
        "supplier_code": supplier_code.strip() if supplier_code else None,
        "tax_identifier": normalized_tax,
        "registration_number": normalized_registration,
    }
    if not cursor_mode:
        rows, total = await service.list_suppliers(
            **common,
            limit=limit,
            offset=offset,
        )
        return SupplierListResponse(
            items=[SupplierRead.model_validate(row) for row in rows],
            total=total,
        )
    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CURSOR",
                "message": "Cursor paginacija ne može koristiti offset",
            },
        )
    cursor_filters = {
        **common,
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    try:
        keyset = await resolve_time_keyset(
            session,
            cursor=cursor,
            resource="suppliers",
            filters=cursor_filters,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc
    rows, total = await service.list_suppliers(
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
            resource="suppliers",
            filters=cursor_filters,
            after_at=last.created_at,
            after_id=last.id,
            snapshot_at=keyset.snapshot_at,
        )
    return SupplierListResponse(
        items=[SupplierRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{supplier_id}",
    response_model=SupplierRead,
    summary="Prikaži dobavljača",
    description="Vraća dobavljača prema internom nepromenljivom UUID identifikatoru.",
)
async def get_supplier(
    supplier_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SupplierRead:
    return SupplierRead.model_validate(
        await SupplierService(session).get_supplier(supplier_id)
    )


@router.patch(
    "/{supplier_id}",
    response_model=SupplierRead,
    summary="Izmeni dobavljača",
    description=(
        "Menja samo prosleđena polja. Obavezna očekivana version vrednost "
        "sprečava prepisivanje paralelnih izmena. Supplier šifra se ne može menjati."
    ),
)
async def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    session: AsyncSession = Depends(get_db),
) -> SupplierRead:
    return SupplierRead.model_validate(
        await SupplierService(session).update_supplier(supplier_id, payload)
    )


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deaktiviraj dobavljača",
    description=(
        "Soft delete: čuva dobavljača i kontakte radi istorije, postavlja "
        "is_active=false i operativni status INACTIVE."
    ),
)
async def deactivate_supplier(
    supplier_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierService(session).deactivate_supplier(supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
