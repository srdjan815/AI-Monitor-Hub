from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_pagination import require_cursor_mode, time_page
from app.core.limits import (
    MAX_CURSOR_CHARS,
    MAX_LEGACY_OFFSET,
)
from app.db.session import get_db
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_orchestration import AttributeMutationCoordinator
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.models import Product
from app.modules.catalog.schemas.product_attributes import (
    ApprovalRequest,
    BulkValueWrite,
    ProductAttributeValueRead,
    ProductAttributeValueWrite,
    ResolvedAttribute,
    ResolvedAttributePage,
    ValidationResult,
)

router = APIRouter(prefix="/catalog", tags=["product-attributes"])


@router.put(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}",
    response_model=ProductAttributeValueRead,
)
async def write_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: ProductAttributeValueWrite,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await AttributeMutationCoordinator(session).write_value(
        product_id, attribute_id, payload
    )


@router.patch(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}",
    response_model=ProductAttributeValueRead,
)
async def patch_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: ProductAttributeValueWrite,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await AttributeMutationCoordinator(session).write_value(
        product_id, attribute_id, payload
    )


@router.get(
    "/products/{product_id:uuid}/attributes",
    response_model=list[ResolvedAttribute],
)
async def product_attributes(
    product_id: uuid.UUID,
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
    service = ProductAttributeService(session)
    product = await service._required(Product, product_id, "Product")
    page = await service.resolved_page(
        product.category_id,
        product=product,
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


@router.get(
    "/products/{product_id:uuid}/attributes/resolved",
    response_model=ResolvedAttributePage,
)
async def resolved_product_attributes(
    product_id: uuid.UUID,
    include_unset: bool = False,
    scope: str | None = Query(default=None, max_length=32),
    group_id: uuid.UUID | None = None,
    family_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> ResolvedAttributePage:
    service = ProductAttributeService(session)
    product = await service._required(Product, product_id, "Product")
    return await service.resolved_page(
        product.category_id,
        product=product,
        include_unset=include_unset,
        scope=scope,
        group_id=group_id,
        family_id=family_id,
        template_id=template_id,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/products/{product_id:uuid}/attributes/resolved/export",
    response_class=StreamingResponse,
)
async def export_resolved_product_attributes(
    product_id: uuid.UUID,
    scope: str | None = Query(default=None, max_length=32),
    group_id: uuid.UUID | None = None,
    family_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    service = ProductAttributeService(session)
    product = await service._required(Product, product_id, "Product")

    async def rows() -> AsyncIterator[bytes]:
        cursor: str | None = None
        while True:
            page = await service.resolved_page(
                product.category_id,
                product=product,
                include_unset=True,
                scope=scope,
                group_id=group_id,
                family_id=family_id,
                template_id=template_id,
                limit=500,
                cursor=cursor,
            )
            for item in page.items:
                yield item.model_dump_json().encode() + b"\n"
            cursor = page.next_cursor
            if cursor is None:
                break

    return StreamingResponse(
        rows(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": (
                f'attachment; filename="product-{product_id}-attributes.ndjson"'
            )
        },
    )


@router.get(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}",
    response_model=list[ProductAttributeValueRead],
)
async def get_product_attribute(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[Any]:
    return await ProductAttributeRepository(session).values(
        product_id,
        attribute_id,
        offset=offset,
        limit=limit,
    )


@router.delete(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await ProductAttributeService(session).deactivate_value(product_id, attribute_id)
    return Response(status_code=204)


@router.post(
    "/products/{product_id:uuid}/attributes/bulk",
    response_model=list[ProductAttributeValueRead],
)
async def bulk_values(
    product_id: uuid.UUID,
    payload: BulkValueWrite,
    session: AsyncSession = Depends(get_db),
) -> list[Any]:
    return await AttributeMutationCoordinator(session).bulk_write(product_id, payload)


@router.post(
    "/products/{product_id:uuid}/attributes/validate",
    response_model=list[ValidationResult],
)
async def validate_bulk_values(
    product_id: uuid.UUID,
    payload: BulkValueWrite,
    session: AsyncSession = Depends(get_db),
) -> list[ValidationResult]:
    service = ProductAttributeService(session)
    return [
        await service.validate_value(
            product_id,
            item.attribute_id,
            ProductAttributeValueWrite(**item.model_dump(exclude={"attribute_id"})),
        )
        for item in payload.items
    ]


@router.post(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}/validate",
    response_model=ValidationResult,
)
async def validate_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: ProductAttributeValueWrite,
    session: AsyncSession = Depends(get_db),
) -> ValidationResult:
    return await ProductAttributeService(session).validate_value(
        product_id, attribute_id, payload
    )


@router.post(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}/approve",
    response_model=ProductAttributeValueRead,
)
async def approve_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: ApprovalRequest,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await ProductAttributeService(session).change_approval(
        product_id, attribute_id, True, payload
    )


@router.post(
    "/products/{product_id:uuid}/attributes/{attribute_id:uuid}/reject",
    response_model=ProductAttributeValueRead,
)
async def reject_value(
    product_id: uuid.UUID,
    attribute_id: uuid.UUID,
    payload: ApprovalRequest,
    session: AsyncSession = Depends(get_db),
) -> Any:
    return await ProductAttributeService(session).change_approval(
        product_id, attribute_id, False, payload
    )


@router.get("/products/{product_id:uuid}/attributes/history")
async def value_history(
    product_id: uuid.UUID,
    response: Response,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    repository = ProductAttributeRepository(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows = await repository.history(
            product_id,
            offset=offset,
            limit=limit,
        )
    else:
        require_cursor_mode(pagination=pagination, offset=offset)
        rows = await time_page(
            session,
            response,
            cursor=cursor,
            resource="catalog.product_attribute_history",
            filters={
                "product_id": str(product_id),
                "limit": limit,
                "order": "occurred_at_asc,id_asc",
            },
            limit=limit,
            loader=lambda page_limit, snapshot_at, after: repository.history(
                product_id,
                offset=0,
                limit=page_limit,
                snapshot_at=snapshot_at,
                after=after,
            ),
            timestamp_of=lambda row: row.occurred_at,
            id_of=lambda row: row.id,
        )
    return [
        {column.name: getattr(row, column.name) for column in row.__table__.columns}
        for row in rows
    ]
