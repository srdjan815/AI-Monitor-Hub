from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.modules.product_content.models import ContentType
from app.modules.product_content.schemas import (
    ContentTypeCreate,
    ContentTypeRead,
    ContentTypeUpdate,
)
from app.modules.product_content.services import ConfigurationService

router = APIRouter()


@router.post("/types", response_model=ContentTypeRead, status_code=201)
async def create_type(
    payload: ContentTypeCreate,
    session: AsyncSession = Depends(get_db),
) -> ContentType:
    return await ConfigurationService(session).create_type(payload)


@router.get("/types", response_model=list[ContentTypeRead])
async def list_types(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> list[ContentType]:
    return await ConfigurationService(session).list_types(
        active_only,
        offset=offset,
        limit=limit,
    )


@router.get("/types/{type_id:uuid}", response_model=ContentTypeRead)
async def get_type(
    type_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ContentType:
    return await ConfigurationService(session).get_type(type_id)


@router.patch("/types/{type_id:uuid}", response_model=ContentTypeRead)
async def update_type(
    type_id: uuid.UUID,
    payload: ContentTypeUpdate,
    session: AsyncSession = Depends(get_db),
) -> ContentType:
    return await ConfigurationService(session).update_type(type_id, payload)


@router.post("/types/{type_id:uuid}/activate", response_model=ContentTypeRead)
async def activate_type(
    type_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ContentType:
    return await ConfigurationService(session).set_type_active(type_id, True)


@router.delete("/types/{type_id:uuid}", response_model=ContentTypeRead)
async def deactivate_type(
    type_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ContentType:
    return await ConfigurationService(session).set_type_active(type_id, False)


@router.post("/seed")
async def seed_content(
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await ConfigurationService(session).seed()
