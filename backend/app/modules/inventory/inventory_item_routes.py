from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.inventory.schemas import InventoryRead, InventoryUpdate
from app.modules.inventory.service import InventoryService

router = APIRouter()


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
