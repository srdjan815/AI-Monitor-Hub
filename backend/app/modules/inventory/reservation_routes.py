from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.inventory.enums import ReservationStatus
from app.modules.inventory.pagination import after_keyset, list_keyset, set_page_headers
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    InventoryReservationCreate,
    InventoryReservationFulfill,
    InventoryReservationList,
    InventoryReservationRead,
    ReservationCancelResponse,
    ReservationExpireSummary,
    ReservationReleaseResponse,
)
from app.modules.inventory.service import InventoryService

router = APIRouter()


@router.post(
    "/inventory/reservations",
    response_model=InventoryReservationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    payload: InventoryReservationCreate,
    session: AsyncSession = Depends(get_db),
) -> InventoryReservationRead:
    reservation = await InventoryService(session).create_reservation(payload)
    return InventoryReservationRead.model_validate(reservation)


@router.get(
    "/inventory/reservations",
    response_model=InventoryReservationList,
)
async def list_reservations(
    response: Response,
    reservation_number: str | None = Query(default=None, max_length=32),
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status_filter: ReservationStatus | None = Query(default=None, alias="status"),
    reference_type: str | None = Query(default=None, max_length=100),
    reference_id: str | None = Query(default=None, max_length=255),
    external_reference: str | None = Query(default=None, max_length=255),
    expires_before: datetime | None = None,
    expires_after: datetime | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> InventoryReservationList:
    status_value = status_filter.value if status_filter is not None else None
    resource = "inventory.reservations"
    cursor_filters = {
        "reservation_number": reservation_number,
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "status": status_value,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "external_reference": external_reference,
        "expires_before": (
            expires_before.isoformat() if expires_before is not None else None
        ),
        "expires_after": (
            expires_after.isoformat() if expires_after is not None else None
        ),
        "created_from": (
            created_from.isoformat() if created_from is not None else None
        ),
        "created_to": (created_to.isoformat() if created_to is not None else None),
        "active_only": active_only,
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    keyset = await list_keyset(
        session,
        cursor=cursor,
        pagination=pagination,
        offset=offset,
        resource=resource,
        filters=cursor_filters,
    )
    repository = InventoryRepository(session)
    if keyset is None:
        rows, total = await repository.list_reservations(
            reservation_number=reservation_number,
            product_id=product_id,
            warehouse_id=warehouse_id,
            status=status_value,
            reference_type=reference_type,
            reference_id=reference_id,
            external_reference=external_reference,
            expires_before=expires_before,
            expires_after=expires_after,
            created_from=created_from,
            created_to=created_to,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        return InventoryReservationList(
            items=[InventoryReservationRead.model_validate(row) for row in rows],
            total=total,
        )

    rows, total = await repository.list_reservations(
        reservation_number=reservation_number,
        product_id=product_id,
        warehouse_id=warehouse_id,
        status=status_value,
        reference_type=reference_type,
        reference_id=reference_id,
        external_reference=external_reference,
        expires_before=expires_before,
        expires_after=expires_after,
        created_from=created_from,
        created_to=created_to,
        active_only=active_only,
        limit=limit + 1,
        offset=offset,
        snapshot_at=keyset.snapshot_at,
        after=after_keyset(keyset),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if has_more else None
    set_page_headers(
        response,
        resource=resource,
        filters=cursor_filters,
        keyset=keyset,
        last_at=last.created_at if last is not None else None,
        last_id=last.id if last is not None else None,
    )
    return InventoryReservationList(
        items=[InventoryReservationRead.model_validate(row) for row in rows],
        total=total,
    )


@router.post(
    "/inventory/reservations/expire",
    response_model=ReservationExpireSummary,
)
async def expire_reservations(
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
) -> ReservationExpireSummary:
    processed, skipped = await InventoryService(session).expire_reservations(limit)
    return ReservationExpireSummary(processed=processed, skipped=skipped)


@router.get(
    "/inventory/reservations/{reservation_id}",
    response_model=InventoryReservationRead,
)
async def get_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> InventoryReservationRead:
    reservation = await InventoryService(session).get_reservation(reservation_id)
    return InventoryReservationRead.model_validate(reservation)


@router.post(
    "/inventory/reservations/{reservation_id}/release",
    response_model=ReservationReleaseResponse,
)
async def release_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReservationReleaseResponse:
    reservation = await InventoryService(session).release_reservation(reservation_id)
    return ReservationReleaseResponse.model_validate(reservation)


@router.post(
    "/inventory/reservations/{reservation_id}/cancel",
    response_model=ReservationCancelResponse,
)
async def cancel_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReservationCancelResponse:
    reservation = await InventoryService(session).cancel_reservation(reservation_id)
    return ReservationCancelResponse.model_validate(reservation)


@router.post(
    "/inventory/reservations/{reservation_id}/fulfill",
    response_model=InventoryReservationRead,
)
async def fulfill_reservation(
    reservation_id: uuid.UUID,
    payload: InventoryReservationFulfill,
    session: AsyncSession = Depends(get_db),
) -> InventoryReservationRead:
    reservation = await InventoryService(session).fulfill_reservation(
        reservation_id, payload
    )
    return InventoryReservationRead.model_validate(reservation)
