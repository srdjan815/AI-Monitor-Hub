from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.inventory.enums import MovementType
from app.modules.inventory.pagination import after_keyset, list_keyset, set_page_headers
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    InventoryMovementCreate,
    InventoryMovementList,
    InventoryMovementRead,
)
from app.modules.inventory.service import InventoryService

router = APIRouter()


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
