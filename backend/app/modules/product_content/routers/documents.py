from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.core.api_pagination import (
    require_cursor_mode,
    time_page,
)
from app.modules.product_content.schemas import LinkCheckWrite, ReferenceWrite
from app.modules.product_content.services import ReferenceService, serialize

router = APIRouter()


@router.post("/products/{product_id:uuid}/documents", status_code=201)
async def create_document(
    product_id: uuid.UUID,
    payload: ReferenceWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await ReferenceService(session).create_document(product_id, payload)
    return {"id": row.id, "url": row.url}


@router.get("/documents")
async def list_documents(
    response: Response,
    product_id: uuid.UUID | None = None,
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = ReferenceService(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows = await service.list_references(
            "document",
            product_id,
            active_only,
            offset=offset,
            limit=limit,
        )
        return [serialize(row) for row in rows]

    require_cursor_mode(pagination=pagination, offset=offset)
    filters = {
        "product_id": str(product_id) if product_id else None,
        "active_only": active_only,
        "limit": limit,
        "order": "created_at_desc,id_desc",
    }
    rows = await time_page(
        session,
        response,
        cursor=cursor,
        resource="content.documents",
        filters=filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: service.list_references(
            "document",
            product_id,
            active_only,
            offset=0,
            limit=page_limit,
            snapshot_at=snapshot_at,
            after=after,
        ),
        timestamp_of=lambda row: row.created_at,
        id_of=lambda row: row.id,
    )
    return [serialize(row) for row in rows]


@router.get("/documents/{reference_id:uuid}")
async def get_document(
    reference_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).get_reference("document", reference_id)
    )


@router.patch("/documents/{reference_id:uuid}")
async def update_document(
    reference_id: uuid.UUID,
    payload: ReferenceWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).update_reference(
            "document", reference_id, payload
        )
    )


@router.delete("/documents/{reference_id:uuid}")
async def delete_document(
    reference_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).deactivate_reference("document", reference_id)
    )


@router.patch("/documents/{reference_id:uuid}/link")
async def update_document_link_check(
    reference_id: uuid.UUID,
    payload: LinkCheckWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).update_link("document", reference_id, payload)
    )
