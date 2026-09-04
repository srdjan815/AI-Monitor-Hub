from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.inventory.pagination import after_keyset, list_keyset, set_page_headers
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    WarehouseCreate,
    WarehouseList,
    WarehouseRead,
    WarehouseUpdate,
)
from app.modules.inventory.service import InventoryService

router = APIRouter()


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
    keyset = await list_keyset(
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
