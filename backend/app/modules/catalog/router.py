from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate,
    AttributeList,
    AttributeRead,
    AttributeUpdate,
    CategoryAttributeRead,
    CategoryAttributeReorder,
    CategoryCreate,
    CategoryList,
    CategoryRead,
    CategoryUpdate,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(tags=["catalog"])


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    payload: CategoryCreate,
    session: AsyncSession = Depends(get_db),
) -> CategoryRead:
    category = await CatalogService(session).create_category(payload)
    return CategoryRead.model_validate(category)


@router.get("/categories", response_model=CategoryList)
async def list_categories(
    active_only: bool = True,
    parent_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> CategoryList:
    rows, total = await CatalogRepository(session).list_categories(
        active_only=active_only,
        parent_id=parent_id,
        limit=limit,
        offset=offset,
    )

    return CategoryList(
        items=[CategoryRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get("/categories/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CategoryRead:
    category = await CatalogRepository(session).get_category(category_id)

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategorija nije pronađena",
        )

    return CategoryRead.model_validate(category)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    session: AsyncSession = Depends(get_db),
) -> CategoryRead:
    category = await CatalogService(session).update_category(
        category_id,
        payload,
    )

    return CategoryRead.model_validate(category)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_category(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await CatalogService(session).deactivate_category(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/attributes",
    response_model=AttributeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_attribute(
    payload: AttributeCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeRead:
    attribute = await CatalogService(session).create_attribute(payload)
    return AttributeRead.model_validate(attribute)


@router.get("/attributes", response_model=AttributeList)
async def list_attributes(
    scope: str | None = None,
    active_only: bool = True,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> AttributeList:
    rows, total = await CatalogRepository(session).list_attributes(
        scope=scope,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return AttributeList(
        items=[AttributeRead.model_validate(row) for row in rows],
        total=total,
    )


@router.patch("/attributes/{attribute_id}", response_model=AttributeRead)
async def update_attribute(
    attribute_id: uuid.UUID,
    payload: AttributeUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeRead:
    attribute = await CatalogService(session).update_attribute(
        attribute_id,
        payload,
    )

    return AttributeRead.model_validate(attribute)


@router.get(
    "/categories/{category_id}/attributes",
    response_model=list[CategoryAttributeRead],
)
async def list_category_attributes(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[CategoryAttributeRead]:
    repository = CatalogRepository(session)

    if not await repository.get_category(category_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategorija nije pronađena",
        )

    links = await repository.list_category_attributes(category_id)

    return [
        CategoryAttributeRead(
            id=link.id,
            category_id=link.category_id,
            attribute_id=link.attribute_id,
            group_name=link.group_name,
            position=link.position,
            is_required=(
                link.is_required_override
                if link.is_required_override is not None
                else link.attribute.is_required
            ),
            is_visible=(
                link.is_visible_override
                if link.is_visible_override is not None
                else link.attribute.is_visible
            ),
            ai_prompt=link.ai_prompt_override or link.attribute.ai_prompt,
            validation_rules=(
                link.validation_rules_override
                if link.validation_rules_override is not None
                else link.attribute.validation_rules
            ),
            is_active=link.is_active,
            attribute=AttributeRead.model_validate(link.attribute),
        )
        for link in links
    ]


@router.patch(
    "/categories/{category_id}/attributes/reorder",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reorder_category_attributes(
    category_id: uuid.UUID,
    payload: CategoryAttributeReorder,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await CatalogService(session).reorder_category_attributes(
        category_id,
        payload,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)