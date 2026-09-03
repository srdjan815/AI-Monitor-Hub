from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.modules.product_content.schemas import (
    TemplateConditionWrite,
    TemplateItemWrite,
    TemplateUpdate,
    TemplateWrite,
)
from app.modules.product_content.services import TemplateService, serialize

router = APIRouter()


@router.post("/templates", status_code=201)
async def create_template(
    payload: TemplateWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).create(payload))


@router.get("/templates")
async def list_templates(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = await TemplateService(session).list(
        active_only,
        offset=offset,
        limit=limit,
    )
    return [serialize(row) for row in rows]


@router.get("/templates/{template_id:uuid}")
async def get_template(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await TemplateService(session).detail(template_id)


@router.patch("/templates/{template_id:uuid}")
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).update(template_id, payload))


@router.delete("/templates/{template_id:uuid}")
async def deactivate_template(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).deactivate(template_id))


@router.post("/templates/{template_id:uuid}/items", status_code=201)
async def add_template_item(
    template_id: uuid.UUID,
    payload: TemplateItemWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).add_item(template_id, payload))


@router.patch("/template-items/{item_id:uuid}")
async def update_template_item(
    item_id: uuid.UUID,
    payload: TemplateItemWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).update_item(item_id, payload))


@router.delete("/template-items/{item_id:uuid}", status_code=204)
async def delete_template_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    await TemplateService(session).delete_item(item_id)


@router.post("/template-items/{item_id:uuid}/conditions", status_code=201)
async def add_template_condition(
    item_id: uuid.UUID,
    payload: TemplateConditionWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).add_condition(item_id, payload))


@router.get("/template-items/{item_id:uuid}/conditions")
async def list_template_conditions(
    item_id: uuid.UUID,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = await TemplateService(session).conditions(
        item_id,
        offset=offset,
        limit=limit,
    )
    return [serialize(row) for row in rows]


@router.post("/templates/{template_id:uuid}/clone", status_code=201)
async def clone_template(
    template_id: uuid.UUID,
    name: str = Query(min_length=1, max_length=255),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).clone(template_id, name))


@router.post(
    "/products/{product_id:uuid}/templates/{template_id:uuid}",
    status_code=201,
)
async def assign_template(
    product_id: uuid.UUID,
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await TemplateService(session).assign(product_id, template_id))


@router.get("/templates/{template_id:uuid}/usage")
async def template_usage(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await TemplateService(session).usage(template_id)
