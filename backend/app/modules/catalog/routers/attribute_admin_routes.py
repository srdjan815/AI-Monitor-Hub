from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_pagination import require_cursor_mode, time_page
from app.core.limits import (
    MAX_CURSOR_CHARS,
    MAX_LEGACY_OFFSET,
    MAX_SEARCH_CHARS,
)
from app.db.session import get_db
from app.modules.catalog.attribute_models import (
    AttributeGroup,
)
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.models import AttributeDefinition
from app.modules.catalog.schemas.product_attributes import (
    AttributeDefinitionCreate,
    AttributeDefinitionRead,
    AttributeDefinitionUpdate,
    AttributeGroupCreate,
    AttributeGroupRead,
    AttributeGroupUpdate,
    ReorderRequest,
)
from app.modules.catalog.seed_attributes import seed_global_attributes

router = APIRouter(prefix="/catalog", tags=["product-attributes"])


@router.post("/attribute-seed")
async def seed_attributes(
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await seed_global_attributes(session)


@router.get("/attribute-dashboard")
async def attribute_dashboard(
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ProductAttributeService(session).dashboard()


@router.post(
    "/attribute-groups",
    response_model=AttributeGroupRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    payload: AttributeGroupCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeGroup:
    return await ProductAttributeService(session).create_group(payload)


@router.get("/attribute-groups", response_model=list[AttributeGroupRead])
async def list_groups(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeGroup]:
    return await ProductAttributeRepository(session).list_groups(
        active_only,
        offset=offset,
        limit=limit,
    )


@router.get("/attribute-groups/{group_id:uuid}", response_model=AttributeGroupRead)
async def get_group(
    group_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> AttributeGroup:
    return await ProductAttributeService(session)._required(
        AttributeGroup, group_id, "Attribute group"
    )


@router.patch("/attribute-groups/{group_id:uuid}", response_model=AttributeGroupRead)
async def update_group(
    group_id: uuid.UUID,
    payload: AttributeGroupUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeGroup:
    return await ProductAttributeService(session).update_group(group_id, payload)


@router.delete(
    "/attribute-groups/{group_id:uuid}", status_code=status.HTTP_204_NO_CONTENT
)
async def deactivate_group(
    group_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await ProductAttributeService(session).deactivate_group(group_id)
    return Response(status_code=204)


@router.post("/attribute-groups/reorder", response_model=list[AttributeGroupRead])
async def reorder_groups(
    payload: ReorderRequest, session: AsyncSession = Depends(get_db)
) -> list[AttributeGroup]:
    return await ProductAttributeService(session).reorder_groups(payload)


@router.post(
    "/attribute-definitions",
    response_model=AttributeDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_definition(
    payload: AttributeDefinitionCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeDefinition:
    return await ProductAttributeService(session).create_definition(payload)


@router.get("/attribute-definitions", response_model=list[AttributeDefinitionRead])
async def list_definitions(
    response: Response,
    active_only: bool = True,
    scope: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, max_length=MAX_SEARCH_CHARS),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[AttributeDefinition]:
    repository = ProductAttributeRepository(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        return await repository.list_definitions(
            active_only=active_only,
            scope=scope,
            search=search,
            offset=offset,
            limit=limit,
        )

    require_cursor_mode(pagination=pagination, offset=offset)
    return await time_page(
        session,
        response,
        cursor=cursor,
        resource="catalog.attribute_definitions",
        filters={
            "active_only": active_only,
            "scope": scope,
            "search": search,
            "limit": limit,
            "order": "created_at_desc,id_desc",
        },
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: (
            repository.list_definitions(
                active_only=active_only,
                scope=scope,
                search=search,
                offset=0,
                limit=page_limit,
                snapshot_at=snapshot_at,
                after=after,
            )
        ),
        timestamp_of=lambda row: row.created_at,
        id_of=lambda row: row.id,
    )


@router.get(
    "/attribute-definitions/{attribute_id:uuid}",
    response_model=AttributeDefinitionRead,
)
async def get_definition(
    attribute_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> AttributeDefinition:
    return await ProductAttributeService(session)._required(
        AttributeDefinition, attribute_id, "Attribute definition"
    )


@router.patch(
    "/attribute-definitions/{attribute_id:uuid}",
    response_model=AttributeDefinitionRead,
)
async def update_definition(
    attribute_id: uuid.UUID,
    payload: AttributeDefinitionUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeDefinition:
    return await ProductAttributeService(session).update_definition(
        attribute_id, payload
    )


@router.delete(
    "/attribute-definitions/{attribute_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_definition(
    attribute_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> Response:
    await ProductAttributeService(session).deactivate_definition(attribute_id)
    return Response(status_code=204)


@router.post(
    "/attribute-definitions/reorder",
    response_model=list[AttributeDefinitionRead],
)
async def reorder_definitions(
    payload: ReorderRequest, session: AsyncSession = Depends(get_db)
) -> list[AttributeDefinition]:
    return await ProductAttributeService(session).reorder_definitions(payload)
