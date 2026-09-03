from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
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
    AttributeNormalizationRule,
    AttributeOption,
)
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_orchestration import AttributeMutationCoordinator
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.models import AttributeDefinition, Category, Product
from app.modules.catalog.schemas.product_attributes import (
    ApprovalRequest,
    AttributeAliasCreate,
    AttributeAliasRead,
    AttributeDefinitionCreate,
    AttributeDefinitionRead,
    AttributeDefinitionUpdate,
    AttributeGroupCreate,
    AttributeGroupRead,
    AttributeGroupUpdate,
    AttributeOptionCreate,
    AttributeOptionRead,
    AttributeOptionUpdate,
    BulkValueWrite,
    CategoryAssignmentCreate,
    CategoryAssignmentRead,
    CategoryAssignmentUpdate,
    ChangeEventRead,
    FilterMetadata,
    NormalizationRuleCreate,
    NormalizationRuleRead,
    NormalizationRuleUpdate,
    ProductAttributeValueRead,
    ProductAttributeValueWrite,
    ProductExport,
    ReorderRequest,
    ResolvedAttribute,
    ResolvedAttributePage,
    ValidationResult,
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


@router.get("/attribute-changes", response_model=list[ChangeEventRead])
async def attribute_changes(
    cursor: int = Query(
        default=0,
        ge=0,
        le=9_223_372_036_854_775_807,
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    product_id: uuid.UUID | None = None,
    entity_type: str | None = Query(default=None, max_length=80),
    session: AsyncSession = Depends(get_db),
) -> list[Any]:
    return await ProductAttributeRepository(session).changes(
        cursor=cursor,
        limit=limit,
        product_id=product_id,
        entity_type=entity_type,
    )


@router.get(
    "/products/{product_id:uuid}/export",
    response_model=ProductExport,
    deprecated=True,
)
async def product_export(
    product_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=500, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> ProductExport:
    service = ProductAttributeService(session)
    product = await service._required(Product, product_id, "Product")
    chain = await service.repository.list_category_chain(product.category_id)
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
    return ProductExport(
        product={
            "id": product.id,
            "name": product.name,
            "code": product.code,
            "sku": product.sku,
            "ean": product.ean,
            "mpn": product.mpn,
            "brand": product.brand,
            "manufacturer": product.manufacturer,
        },
        category_path=[
            {"id": category.id, "name": category.name, "code": category.code}
            for category in chain
        ],
        attributes=page.items,
        cursor=page.snapshot_cursor,
    )


@router.get("/attribute-admin", response_class=HTMLResponse, include_in_schema=False)
async def attribute_admin() -> str:
    return """<!doctype html>
<html lang="sr"><head><meta charset="utf-8"><title>Product Attributes</title>
<style>body{font:15px system-ui;margin:2rem;max-width:1200px}nav button{margin:.2rem}
section{border:1px solid #ddd;padding:1rem;margin:1rem 0}input,select,textarea{margin:.2rem}
table{border-collapse:collapse;width:100%}td,th{padding:.4rem;border-bottom:1px solid #ddd}
.muted{color:#666}</style></head><body>
<h1>Product Attribute Administration</h1>
<p class="muted">Uses the canonical Catalog API. Access follows current application security.</p>
<nav><button onclick="loadDashboard()">Dashboard</button>
<button onclick="loadGroups()">Groups</button><button onclick="newGroup()">New group</button>
<button onclick="loadDefinitions()">Definitions</button><button onclick="newDefinition()">New definition</button>
<button onclick="loadCategory()">Category layout</button>
<button onclick="loadProduct()">Product editor</button><button onclick="loadReview()">Review queue</button></nav>
<nav><a href="/api/v1/catalog/attribute-admin/families">Families</a> ·
<a href="/api/v1/catalog/attribute-admin/templates">Templates</a> ·
<a href="/api/v1/catalog/attribute-admin/formulas">Formulas</a> ·
<a href="/api/v1/catalog/attribute-admin/derived">Derived</a> ·
<a href="/api/v1/catalog/attribute-admin/dependencies">Dependencies</a> ·
<a href="/api/v1/catalog/attribute-admin/prompts">Prompts</a> ·
<a href="/api/v1/catalog/attribute-admin/usage">Usage</a> ·
<a href="/api/v1/catalog/attribute-admin/bulk">Bulk editor</a> ·
<a href="/api/v1/catalog/attribute-admin/locked">Locked values</a></nav>
<section id="view">Loading…</section>
<script>
const api='/api/v1/catalog', view=document.querySelector('#view');
async function json(path, options){const r=await fetch(api+path,options);if(!r.ok)throw Error(await r.text());return r.json()}
async function loadDashboard(){const d=await json('/attribute-dashboard');
view.innerHTML='<h2>Dashboard</h2>'+Object.entries(d).map(([k,v])=>`<p><b>${k}</b>: ${v??'not yet calculated'}</p>`).join('')}
async function loadGroups(){const d=await json('/attribute-groups?active_only=false');
view.innerHTML='<h2>Groups</h2><table><tr><th>Order</th><th>Name</th><th>Slug</th><th>Active</th></tr>'+
d.map(x=>`<tr><td>${x.sort_order}</td><td>${x.name}</td><td>${x.slug}</td><td>${x.is_active}</td></tr>`).join('')+'</table>'}
async function newGroup(){const name=prompt('Group name');if(!name)return;await json('/attribute-groups',
{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});loadGroups()}
async function loadDefinitions(){const d=await json('/attribute-definitions?active_only=false');
view.innerHTML='<h2>Definitions</h2><input placeholder="Search" oninput="filterRows(this.value)"><table id="defs"><tr><th>Name</th><th>API</th><th>Type</th><th>Storage</th></tr>'+
d.map(x=>`<tr><td>${x.name}</td><td>${x.api_name}</td><td>${x.data_type}</td><td>${x.storage_kind}</td></tr>`).join('')+'</table>'}
async function newDefinition(){const name=prompt('Attribute name');if(!name)return;const slug=prompt('Stable API name');
await json('/attribute-definitions',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({name,slug,scope:'GLOBAL',storage_kind:'ATTRIBUTE_VALUE',data_type:'TEXT'})});loadDefinitions()}
async function loadCategory(){const id=prompt('Category UUID');if(!id)return;const d=await json(`/categories/${id}/attributes/resolved`);
view.innerHTML='<h2>Resolved category layout</h2>'+d.map(x=>`<p>${x.sort_order}. ${x.definition.name} ${x.inherited_from_category_id?'(assigned/inherited)':'(global)'}</p>`).join('')}
async function loadProduct(){const id=prompt('Product UUID');if(!id)return;const d=await json(`/products/${id}/attributes`);
view.innerHTML='<h2>Product attribute editor</h2>'+d.map(x=>`<p><b>${x.definition.name}</b>: ${x.display_value??'—'} ${x.read_only?'🔒':''}</p>`).join('')}
async function loadReview(){const d=await json('/attribute-dashboard');view.innerHTML=`<h2>Review queue</h2>
<p>Pending ${d.pending_review_values}; invalid ${d.invalid_values}; warnings ${d.warning_values};
low confidence ${d.low_confidence_values}</p><p>Use Product editor and approval APIs for decisions.</p>`}
function filterRows(q){for(const r of document.querySelectorAll('#defs tr'))r.hidden=!r.innerText.toLowerCase().includes(q.toLowerCase())}
loadDashboard();</script></body></html>"""
