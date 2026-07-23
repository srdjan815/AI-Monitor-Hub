from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

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
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> WarehouseList:
    rows, total = await InventoryRepository(session).list_warehouses(
        active_only=active_only,
        limit=limit,
        offset=offset,
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
    warehouse_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> InventoryList:
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
    movement_type: MovementType | None = None,
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    source_warehouse_id: uuid.UUID | None = None,
    destination_warehouse_id: uuid.UUID | None = None,
    external_reference: str | None = None,
    is_reversed: bool | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> InventoryMovementList:
    rows, total = await InventoryRepository(session).list_movements(
        movement_type=(
            movement_type.value if movement_type is not None else None
        ),
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
        items=[
            InventoryMovementRead.model_validate(row) for row in rows
        ],
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
    reservation_number: str | None = None,
    product_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status_filter: ReservationStatus | None = Query(
        default=None, alias="status"
    ),
    reference_type: str | None = None,
    reference_id: str | None = None,
    external_reference: str | None = None,
    expires_before: datetime | None = None,
    expires_after: datetime | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> InventoryReservationList:
    rows, total = await InventoryRepository(session).list_reservations(
        reservation_number=reservation_number,
        product_id=product_id,
        warehouse_id=warehouse_id,
        status=(
            status_filter.value if status_filter is not None else None
        ),
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
        items=[
            InventoryReservationRead.model_validate(row) for row in rows
        ],
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
    processed, skipped = await InventoryService(
        session
    ).expire_reservations(limit)
    return ReservationExpireSummary(processed=processed, skipped=skipped)


@router.get(
    "/inventory/reservations/{reservation_id}",
    response_model=InventoryReservationRead,
)
async def get_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> InventoryReservationRead:
    reservation = await InventoryService(session).get_reservation(
        reservation_id
    )
    return InventoryReservationRead.model_validate(reservation)


@router.post(
    "/inventory/reservations/{reservation_id}/release",
    response_model=ReservationReleaseResponse,
)
async def release_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReservationReleaseResponse:
    reservation = await InventoryService(session).release_reservation(
        reservation_id
    )
    return ReservationReleaseResponse.model_validate(reservation)


@router.post(
    "/inventory/reservations/{reservation_id}/cancel",
    response_model=ReservationCancelResponse,
)
async def cancel_reservation(
    reservation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReservationCancelResponse:
    reservation = await InventoryService(session).cancel_reservation(
        reservation_id
    )
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
