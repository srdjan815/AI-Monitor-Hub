from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import (
    TimeKeyset,
    encode_time_keyset,
    resolve_time_keyset,
)
from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.core.pagination import InvalidCursorError
from app.db.session import get_db
from app.modules.inventory.enums import MovementType, ReservationStatus
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    InventoryCreate,
    InventoryList,
    InventoryMovementCreate,
    InventoryMovementList,
    InventoryMovementRead,
    InventoryReservationCreate,
    InventoryReservationFulfill,
    InventoryReservationList,
    InventoryReservationRead,
    InventoryRead,
    InventoryUpdate,
    WarehouseCreate,
    WarehouseList,
    WarehouseRead,
    WarehouseUpdate,
    ReservationCancelResponse,
    ReservationExpireSummary,
    ReservationReleaseResponse,
)
from app.modules.inventory.service import InventoryService

router = APIRouter(tags=["inventory"])


async def _list_keyset(
    session: AsyncSession,
    *,
    cursor: str | None,
    pagination: Literal["offset", "cursor"] | None,
    offset: int,
    resource: str,
    filters: dict[str, Any],
) -> TimeKeyset | None:
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        return None
    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CURSOR",
                "message": "Cursor pagination cannot use offset mode or offset",
            },
        )

    try:
        return await resolve_time_keyset(
            session,
            cursor=cursor,
            resource=resource,
            filters=filters,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc


def _after(keyset: TimeKeyset) -> tuple[datetime, uuid.UUID] | None:
    if keyset.after_at is None or keyset.after_id is None:
        return None
    return keyset.after_at, keyset.after_id


def _set_page_headers(
    response: Response,
    *,
    resource: str,
    filters: dict[str, Any],
    keyset: TimeKeyset,
    last_at: datetime | None,
    last_id: uuid.UUID | None,
) -> None:
    response.headers["X-Snapshot-At"] = keyset.snapshot_at.isoformat()
    if last_at is None or last_id is None:
        return
    response.headers["X-Next-Cursor"] = encode_time_keyset(
        resource=resource,
        filters=filters,
        after_at=last_at,
        after_id=last_id,
        snapshot_at=keyset.snapshot_at,
    )


@router.post(
    "/warehouses",
    response_model=WarehouseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_warehouse(
    payload: WarehouseCreate,
    session: AsyncSession = Depends(get_db),
) -> WarehouseRead:
    warehouse = await InventoryService(session).create_warehouse(payload)
    return WarehouseRead.model_validate(warehouse)


@router.get("/warehouses", response_model=WarehouseList)
async def list_warehouses(
    response: Response,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> WarehouseList:
    resource = "inventory.warehouses"
    cursor_filters = {
        "active_only": active_only,
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    keyset = await _list_keyset(
        session,
        cursor=cursor,
        pagination=pagination,
        offset=offset,
        resource=resource,
        filters=cursor_filters,
    )
    if keyset is None:
        rows, total = await InventoryRepository(session).list_warehouses(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        return WarehouseList(
            items=[WarehouseRead.model_validate(row) for row in rows],
            total=total,
        )

    rows, total = await InventoryRepository(session).list_warehouses(
        active_only=active_only,
        limit=limit + 1,
        offset=offset,
        snapshot_at=keyset.snapshot_at,
        after=_after(keyset),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if has_more else None
    _set_page_headers(
        response,
        resource=resource,
        filters=cursor_filters,
        keyset=keyset,
        last_at=last.created_at if last is not None else None,
        last_id=last.id if last is not None else None,
    )
    return WarehouseList(
        items=[WarehouseRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseRead)
async def get_warehouse(
    warehouse_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> WarehouseRead:
    warehouse = await InventoryService(session).get_warehouse(warehouse_id)
    return WarehouseRead.model_validate(warehouse)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseRead)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    session: AsyncSession = Depends(get_db),
) -> WarehouseRead:
    warehouse = await InventoryService(session).update_warehouse(
        warehouse_id,
        payload,
    )
    return WarehouseRead.model_validate(warehouse)


@router.delete(
    "/warehouses/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_warehouse(
    warehouse_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await InventoryService(session).deactivate_warehouse(warehouse_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/inventory",
    response_model=InventoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory(
    payload: InventoryCreate,
    session: AsyncSession = Depends(get_db),
) -> InventoryRead:
    inventory = await InventoryService(session).create_inventory(payload)
    return InventoryRead.model_validate(inventory)


@router.get("/inventory", response_model=InventoryList)
async def list_inventory(
    response: Response,
    warehouse_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> InventoryList:
    resource = "inventory.balances"
    cursor_filters = {
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "active_only": active_only,
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    keyset = await _list_keyset(
        session,
        cursor=cursor,
        pagination=pagination,
        offset=offset,
        resource=resource,
        filters=cursor_filters,
    )
    if keyset is None:
        rows, total = await InventoryRepository(session).list_inventory(
            warehouse_id=warehouse_id,
            product_id=product_id,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
        return InventoryList(
            items=[InventoryRead.model_validate(row) for row in rows],
            total=total,
        )

    rows, total = await InventoryRepository(session).list_inventory(
        warehouse_id=warehouse_id,
        product_id=product_id,
        active_only=active_only,
        limit=limit + 1,
        offset=offset,
        snapshot_at=keyset.snapshot_at,
        after=_after(keyset),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if has_more else None
    _set_page_headers(
        response,
        resource=resource,
        filters=cursor_filters,
        keyset=keyset,
        last_at=last.created_at if last is not None else None,
        last_id=last.id if last is not None else None,
    )
    return InventoryList(
        items=[InventoryRead.model_validate(row) for row in rows],
        total=total,
    )


@router.post(
    "/inventory/movements",
    response_model=InventoryMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_movement(
    payload: InventoryMovementCreate,
    session: AsyncSession = Depends(get_db),
) -> InventoryMovementRead:
    movement = await InventoryService(session).create_movement(payload)
    return InventoryMovementRead.model_validate(movement)


@router.get(
    "/inventory/movements",
    response_model=InventoryMovementList,
)
async def list_movements(
    response: Response,
    movement_type: MovementType | None = None,
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    source_warehouse_id: uuid.UUID | None = None,
    destination_warehouse_id: uuid.UUID | None = None,
    external_reference: str | None = Query(default=None, max_length=255),
    is_reversed: bool | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> InventoryMovementList:
    movement_type_value = movement_type.value if movement_type is not None else None
    resource = "inventory.movements"
    cursor_filters = {
        "movement_type": movement_type_value,
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "source_warehouse_id": source_warehouse_id,
        "destination_warehouse_id": destination_warehouse_id,
        "external_reference": external_reference,
        "is_reversed": is_reversed,
        "occurred_from": (
            occurred_from.isoformat() if occurred_from is not None else None
        ),
        "occurred_to": (occurred_to.isoformat() if occurred_to is not None else None),
        "limit": limit,
        "pagination": "cursor",
        "order": "occurred_at_desc,id_desc",
    }
    keyset = await _list_keyset(
        session,
        cursor=cursor,
        pagination=pagination,
        offset=offset,
        resource=resource,
        filters=cursor_filters,
    )
    repository = InventoryRepository(session)
    if keyset is None:
        rows, total = await repository.list_movements(
            movement_type=movement_type_value,
            product_id=product_id,
            warehouse_id=warehouse_id,
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=destination_warehouse_id,
            external_reference=external_reference,
            is_reversed=is_reversed,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
        return InventoryMovementList(
            items=[InventoryMovementRead.model_validate(row) for row in rows],
            total=total,
        )

    rows, total = await repository.list_movements(
        movement_type=movement_type_value,
        product_id=product_id,
        warehouse_id=warehouse_id,
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        external_reference=external_reference,
        is_reversed=is_reversed,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        limit=limit + 1,
        offset=offset,
        snapshot_at=keyset.snapshot_at,
        after=_after(keyset),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if has_more else None
    _set_page_headers(
        response,
        resource=resource,
        filters=cursor_filters,
        keyset=keyset,
        last_at=last.occurred_at if last is not None else None,
        last_id=last.id if last is not None else None,
    )
    return InventoryMovementList(
        items=[InventoryMovementRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/inventory/movements/{movement_id}",
    response_model=InventoryMovementRead,
)
async def get_movement(
    movement_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> InventoryMovementRead:
    movement = await InventoryService(session).get_movement(movement_id)
    return InventoryMovementRead.model_validate(movement)


@router.post(
    "/inventory/movements/{movement_id}/reverse",
    response_model=InventoryMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def reverse_movement(
    movement_id: uuid.UUID,
    created_by: str | None = Query(default=None, max_length=120),
    session: AsyncSession = Depends(get_db),
) -> InventoryMovementRead:
    movement = await InventoryService(session).reverse_movement(
        movement_id,
        created_by=created_by,
    )
    return InventoryMovementRead.model_validate(movement)


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
    keyset = await _list_keyset(
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
        after=_after(keyset),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if has_more else None
    _set_page_headers(
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


@router.get("/inventory/{inventory_id}", response_model=InventoryRead)
async def get_inventory(
    inventory_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> InventoryRead:
    inventory = await InventoryService(session).get_inventory(inventory_id)
    return InventoryRead.model_validate(inventory)


@router.patch("/inventory/{inventory_id}", response_model=InventoryRead)
async def update_inventory(
    inventory_id: uuid.UUID,
    payload: InventoryUpdate,
    session: AsyncSession = Depends(get_db),
) -> InventoryRead:
    inventory = await InventoryService(session).update_inventory(
        inventory_id,
        payload,
    )
    return InventoryRead.model_validate(inventory)


@router.delete(
    "/inventory/{inventory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_inventory(
    inventory_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await InventoryService(session).deactivate_inventory(inventory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
