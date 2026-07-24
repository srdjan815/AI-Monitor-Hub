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


@router.post("/products/{product_id:uuid}/videos", status_code=201)
async def create_video(
    product_id: uuid.UUID,
    payload: ReferenceWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await ReferenceService(session).create_video(product_id, payload)
    return {"id": row.id, "url": row.url}


@router.get("/videos")
async def list_videos(
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
            "video",
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
        resource="content.videos",
        filters=filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: service.list_references(
            "video",
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


@router.get("/videos/{reference_id:uuid}")
async def get_video(
    reference_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).get_reference("video", reference_id)
    )


@router.patch("/videos/{reference_id:uuid}")
async def update_video(
    reference_id: uuid.UUID,
    payload: ReferenceWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).update_reference("video", reference_id, payload)
    )


@router.delete("/videos/{reference_id:uuid}")
async def delete_video(
    reference_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).deactivate_reference("video", reference_id)
    )


@router.patch("/videos/{reference_id:uuid}/link")
async def update_video_link_check(
    reference_id: uuid.UUID,
    payload: LinkCheckWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(
        await ReferenceService(session).update_link("video", reference_id, payload)
    )
