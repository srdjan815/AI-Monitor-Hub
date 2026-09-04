from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import (
    MAX_CURSOR_CHARS,
    MAX_LEGACY_OFFSET,
)
from app.db.session import get_db
from app.modules.catalog.attribute_models import (
    AttributeNormalizationRule,
    AttributeOption,
)
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.models import Category
from app.modules.catalog.schemas.product_attributes import (
    AttributeAliasCreate,
    AttributeAliasRead,
    AttributeOptionCreate,
    AttributeOptionRead,
    AttributeOptionUpdate,
    CategoryAssignmentCreate,
    CategoryAssignmentRead,
    CategoryAssignmentUpdate,
    NormalizationRuleCreate,
    NormalizationRuleRead,
    NormalizationRuleUpdate,
    ReorderRequest,
    ResolvedAttribute,
)

router = APIRouter(prefix="/catalog", tags=["product-attributes"])


@router.post(
    "/categories/{category_id:uuid}/attributes",
    response_model=CategoryAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    category_id: uuid.UUID,
    payload: CategoryAssignmentCreate,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await ProductAttributeService(session).create_assignment(
        category_id, payload
    )


@router.get(
    "/categories/{category_id:uuid}/attributes",
    response_model=list[CategoryAssignmentRead],
)
async def list_assignments(
    category_id: uuid.UUID,
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[Any]:
    await ProductAttributeService(session)._required(
        Category,
        category_id,
        "Category",
    )
    return await ProductAttributeRepository(session).list_assignments(
        [category_id],
        active_only,
        offset=offset,
        limit=limit,
    )


@router.patch(
    "/categories/{category_id:uuid}/attributes/{assignment_id:uuid}",
    response_model=CategoryAssignmentRead,
)
async def update_assignment(
    category_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: CategoryAssignmentUpdate,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await ProductAttributeService(session).update_assignment(
        category_id, assignment_id, payload
    )


@router.delete(
    "/categories/{category_id:uuid}/attributes/{assignment_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_assignment(
    category_id: uuid.UUID,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await ProductAttributeService(session).deactivate_assignment(
        category_id, assignment_id
    )
    return Response(status_code=204)


@router.post(
    "/categories/{category_id:uuid}/attributes/reorder",
    response_model=list[CategoryAssignmentRead],
)
async def reorder_assignments(
    category_id: uuid.UUID,
    payload: ReorderRequest,
    session: AsyncSession = Depends(get_db),
) -> list[Any]:
    return await ProductAttributeService(session).reorder_assignments(
        category_id, payload
    )


@router.get(
    "/categories/{category_id:uuid}/attributes/resolved",
    response_model=list[ResolvedAttribute],
)
async def resolved_category_layout(
    category_id: uuid.UUID,
    response: Response,
    include_unset: bool = True,
    scope: str | None = Query(default=None, max_length=32),
    group_id: uuid.UUID | None = None,
    family_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[ResolvedAttribute]:
    page = await ProductAttributeService(session).resolved_page(
        category_id,
        product=None,
        include_unset=include_unset,
        scope=scope,
        group_id=group_id,
        family_id=family_id,
        template_id=template_id,
        limit=limit,
        cursor=cursor,
    )
    response.headers["X-Total-Count"] = str(page.total)
    response.headers["X-Snapshot-Cursor"] = str(page.snapshot_cursor)
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return page.items


@router.post(
    "/attribute-definitions/{attribute_id:uuid}/options",
    response_model=AttributeOptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_option(
    attribute_id: uuid.UUID,
    payload: AttributeOptionCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeOption:
    return await ProductAttributeService(session).create_option(attribute_id, payload)


@router.get(
    "/attribute-definitions/{attribute_id:uuid}/options",
    response_model=list[AttributeOptionRead],
)
async def list_options(
    attribute_id: uuid.UUID,
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeOption]:
    return await ProductAttributeRepository(session).list_options(
        attribute_id,
        active_only,
        offset=offset,
        limit=limit,
    )


@router.patch("/attribute-options/{option_id:uuid}", response_model=AttributeOptionRead)
async def update_option(
    option_id: uuid.UUID,
    payload: AttributeOptionUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeOption:
    return await ProductAttributeService(session).update_option(option_id, payload)


@router.delete(
    "/attribute-options/{option_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_option(
    option_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await ProductAttributeService(session).deactivate_option(option_id)
    return Response(status_code=204)


@router.post(
    "/attribute-options/{option_id:uuid}/aliases",
    response_model=AttributeAliasRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_alias(
    option_id: uuid.UUID,
    payload: AttributeAliasCreate,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await ProductAttributeService(session).create_alias(option_id, payload)


@router.delete(
    "/attribute-aliases/{alias_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_alias(
    alias_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await ProductAttributeService(session).delete_alias(alias_id)
    return Response(status_code=204)


@router.post(
    "/attribute-definitions/{attribute_id:uuid}/normalization-rules",
    response_model=NormalizationRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    attribute_id: uuid.UUID,
    payload: NormalizationRuleCreate,
    session: AsyncSession = Depends(get_db),
) -> AttributeNormalizationRule:
    return await ProductAttributeService(session).create_rule(attribute_id, payload)


@router.get(
    "/attribute-definitions/{attribute_id:uuid}/normalization-rules",
    response_model=list[NormalizationRuleRead],
)
async def list_rules(
    attribute_id: uuid.UUID,
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[AttributeNormalizationRule]:
    return await ProductAttributeRepository(session).list_rules(
        attribute_id,
        active_only,
        offset=offset,
        limit=limit,
    )


@router.patch(
    "/normalization-rules/{rule_id:uuid}", response_model=NormalizationRuleRead
)
async def update_rule(
    rule_id: uuid.UUID,
    payload: NormalizationRuleUpdate,
    session: AsyncSession = Depends(get_db),
) -> AttributeNormalizationRule:
    return await ProductAttributeService(session).update_rule(rule_id, payload)


@router.delete(
    "/normalization-rules/{rule_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await ProductAttributeService(session).deactivate_rule(rule_id)
    return Response(status_code=204)
