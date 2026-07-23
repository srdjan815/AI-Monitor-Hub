from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.catalog.schemas import (
    AttributeTypeCreate,
    AttributeTypeList,
    AttributeTypeRead,
    AttributeTypeUpdate,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/attribute-types", tags=["catalog-attribute-types"])


@router.post("", response_model=AttributeTypeRead, status_code=status.HTTP_201_CREATED)
async def create_attribute_type(
    payload: AttributeTypeCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeTypeRead:
    attribute_type = await CatalogService(session).create_attribute_type(payload)
    return AttributeTypeRead.model_validate(attribute_type)


@router.get("", response_model=AttributeTypeList)
async def list_attribute_types(
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> AttributeTypeList:
    rows, total = await CatalogService(session).list_attribute_types(
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return AttributeTypeList(
        items=[AttributeTypeRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get("/{attribute_type_id}", response_model=AttributeTypeRead)
async def get_attribute_type(
    attribute_type_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AttributeTypeRead:
    attribute_type = await CatalogService(session).get_attribute_type(
        attribute_type_id
    )

    return AttributeTypeRead.model_validate(attribute_type)


@router.patch("/{attribute_type_id}", response_model=AttributeTypeRead)
async def update_attribute_type(
    attribute_type_id: uuid.UUID,
    payload: AttributeTypeUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeTypeRead:
    attribute_type = await CatalogService(session).update_attribute_type(
        attribute_type_id,
        payload,
    )

    return AttributeTypeRead.model_validate(attribute_type)


@router.delete("/{attribute_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_attribute_type(
    attribute_type_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await CatalogService(session).deactivate_attribute_type(attribute_type_id)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
