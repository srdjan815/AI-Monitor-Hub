from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import (
    MAX_CURSOR_CHARS,
)
from app.db.session import get_db
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.models import Product
from app.modules.catalog.schemas.product_attributes import (
    AttributeOptionRead,
    FilterMetadata,
    ResolvedAttribute,
)

router = APIRouter(prefix="/catalog", tags=["product-attributes"])


@router.get(
    "/products/{product_id:uuid}/attribute-layout",
    response_model=list[ResolvedAttribute],
)
async def product_layout(
    product_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=500, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[ResolvedAttribute]:
    service = ProductAttributeService(session)
    product = await service._required(Product, product_id, "Product")
    page = await service.resolved_page(
        product.category_id,
        product=product,
        include_unset=True,
        scope=None,
        group_id=None,
        family_id=None,
        template_id=None,
        limit=limit,
        cursor=cursor,
    )
    response.headers["X-Total-Count"] = str(page.total)
    response.headers["X-Snapshot-Cursor"] = str(page.snapshot_cursor)
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return page.items


@router.get(
    "/categories/{category_id:uuid}/filters",
    response_model=list[FilterMetadata],
)
async def filter_metadata(
    category_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[FilterMetadata]:
    service = ProductAttributeService(session)
    page = await service.resolved_page(
        category_id,
        product=None,
        include_unset=True,
        scope=None,
        group_id=None,
        family_id=None,
        template_id=None,
        limit=limit,
        cursor=cursor,
        filter_only=True,
    )
    repository = ProductAttributeRepository(session)
    result = []
    for item in page.items:
        definition = item.definition
        assignment = item.assignment
        enabled = (
            assignment.is_filter_override
            if assignment and assignment.is_filter_override is not None
            else definition.is_filterable
        )
        if not enabled:
            continue
        filter_type = (
            assignment.filter_type_override
            if assignment and assignment.filter_type_override
            else definition.filter_type
        )
        if not filter_type:
            continue
        result.append(
            FilterMetadata(
                attribute_id=definition.id,
                api_name=definition.api_name,
                label=definition.name,
                data_type=definition.data_type,
                filter_type=filter_type,
                unit=definition.default_unit,
                options=[
                    AttributeOptionRead.model_validate(option)
                    for option in await repository.list_options(definition.id)
                ],
                minimum_value=definition.minimum_value,
                maximum_value=definition.maximum_value,
                sort_order=definition.filter_sort_order,
                allows_multiple=definition.allows_multiple,
            )
        )
    response.headers["X-Total-Count"] = str(page.total)
    response.headers["X-Snapshot-Cursor"] = str(page.snapshot_cursor)
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return sorted(result, key=lambda item: (item.sort_order, item.api_name))


@router.get("/categories/{category_id:uuid}/compatibility")
async def compatibility_metadata(
    category_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    page = await ProductAttributeService(session).resolved_page(
        category_id,
        product=None,
        include_unset=True,
        scope=None,
        group_id=None,
        family_id=None,
        template_id=None,
        limit=limit,
        cursor=cursor,
        compatibility_only=True,
    )
    result = []
    for item in page.items:
        definition = item.definition
        enabled = (
            item.assignment.is_compatibility_override
            if item.assignment and item.assignment.is_compatibility_override is not None
            else definition.is_compatibility_attribute
        )
        if enabled:
            result.append(
                {
                    "attribute_id": definition.id,
                    "api_name": definition.api_name,
                    "name": definition.name,
                    "compatibility_type": definition.compatibility_type,
                    "compatibility_priority": definition.compatibility_priority,
                    "data_type": definition.data_type,
                    "unit": definition.default_unit,
                }
            )
    response.headers["X-Total-Count"] = str(page.total)
    response.headers["X-Snapshot-Cursor"] = str(page.snapshot_cursor)
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return sorted(
        result,
        key=lambda item: (item["compatibility_priority"], item["api_name"]),
    )
