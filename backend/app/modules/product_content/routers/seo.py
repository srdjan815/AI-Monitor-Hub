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
from app.modules.product_content.models import ProductSEO
from app.core.api_pagination import (
    require_cursor_mode,
    revision_page,
    time_page,
)
from app.modules.product_content.schemas import RollbackRequest, SEOWrite
from app.modules.product_content.services import ReferenceService, serialize

router = APIRouter()


@router.post("/products/{product_id:uuid}/seo", status_code=201)
async def create_seo(
    product_id: uuid.UUID,
    payload: SEOWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await ReferenceService(session).create_seo(product_id, payload)
    return {"id": row.id, "slug": row.slug, "revision": row.revision}


@router.get("/seo")
async def list_seo(
    response: Response,
    product_id: uuid.UUID | None = None,
    current_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = ReferenceService(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows = await service.list_revisions(
            "seo",
            product_id,
            current_only,
            offset=offset,
            limit=limit,
        )
        return [serialize(row) for row in rows]

    require_cursor_mode(pagination=pagination, offset=offset)
    filters = {
        "product_id": str(product_id) if product_id else None,
        "current_only": current_only,
        "limit": limit,
        "order": "created_at_desc,id_desc",
    }
    rows = await time_page(
        session,
        response,
        cursor=cursor,
        resource="content.seo",
        filters=filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: service.list_revisions(
            "seo",
            product_id,
            current_only,
            offset=0,
            limit=page_limit,
            snapshot_at=snapshot_at,
            after=after,
        ),
        timestamp_of=lambda row: row.created_at,
        id_of=lambda row: row.id,
    )
    return [serialize(row) for row in rows]


@router.get("/seo/{seo_id:uuid}")
async def get_seo(
    seo_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).required(ProductSEO, seo_id, "SEO")
    )


@router.patch("/seo/{seo_id:uuid}", status_code=201)
async def revise_seo(
    seo_id: uuid.UUID,
    payload: SEOWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await ReferenceService(session).revise_seo(seo_id, payload))


@router.delete("/seo/{seo_id:uuid}")
async def delete_seo(
    seo_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await ReferenceService(session).deactivate_revision("seo", seo_id))


@router.get("/seo/{seo_key:uuid}/history")
async def seo_history(
    seo_key: uuid.UUID,
    response: Response,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = ReferenceService(session)
    rows = await revision_page(
        response,
        cursor=cursor,
        resource="content.seo_history",
        filters={
            "seo_key": str(seo_key),
            "limit": limit,
            "order": "revision_desc",
        },
        limit=limit,
        loader=lambda page_limit, after, snapshot: (
            service.revision_history_page(
                "seo",
                seo_key,
                limit=page_limit,
                after_revision=after,
                snapshot_revision=snapshot,
            )
        ),
        revision_of=lambda row: row.revision,
    )
    return [serialize(row) for row in rows]


@router.post("/seo/{seo_key:uuid}/rollback", status_code=201)
async def rollback_seo(
    seo_key: uuid.UUID,
    payload: RollbackRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).rollback_revision(
            "seo", seo_key, payload.revision
        )
    )
