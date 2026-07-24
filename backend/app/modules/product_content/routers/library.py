from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS, MAX_DB_INTEGER, MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.core.api_pagination import (
    require_cursor_mode,
    revision_page,
    time_page,
)
from app.modules.product_content.schemas import LibraryUpdate, LibraryWrite
from app.modules.product_content.services import LibraryService, serialize

router = APIRouter()


@router.post("/library", status_code=201)
async def create_library_item(
    payload: LibraryWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await LibraryService(session).create(payload))


@router.get("/library")
async def list_library_items(
    response: Response,
    kind: str | None = Query(default=None, max_length=32),
    category: str | None = Query(default=None, max_length=120),
    tag: str | None = Query(default=None, max_length=255),
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = LibraryService(session)
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows = await service.list(
            kind,
            category,
            tag,
            active_only,
            offset=offset,
            limit=limit,
        )
        return [serialize(row) for row in rows]

    require_cursor_mode(pagination=pagination, offset=offset)
    filters = {
        "kind": kind,
        "category": category,
        "tag": tag,
        "active_only": active_only,
        "limit": limit,
        "order": "created_at_desc,id_desc",
    }
    rows = await time_page(
        session,
        response,
        cursor=cursor,
        resource="content.library",
        filters=filters,
        limit=limit,
        loader=lambda page_limit, snapshot_at, after: service.list(
            kind,
            category,
            tag,
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


@router.get("/library/{item_id:uuid}")
async def get_library_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await LibraryService(session).get(item_id))


@router.patch("/library/{item_id:uuid}")
async def update_library_item(
    item_id: uuid.UUID,
    payload: LibraryUpdate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await LibraryService(session).update(item_id, payload))


@router.post("/library/{item_id:uuid}/revisions", status_code=201)
async def revise_library_item(
    item_id: uuid.UUID,
    payload: LibraryWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await LibraryService(session).revise(item_id, payload))


@router.get("/library/{item_id:uuid}/history")
async def library_history(
    item_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = LibraryService(session)
    rows = await revision_page(
        response,
        cursor=cursor,
        resource="content.library_history",
        filters={
            "item_id": str(item_id),
            "limit": limit,
            "order": "revision_desc",
        },
        limit=limit,
        loader=lambda page_limit, after, snapshot: service.history_page(
            item_id,
            limit=page_limit,
            after_revision=after,
            snapshot_revision=snapshot,
        ),
        revision_of=lambda row: row.revision,
    )
    return [serialize(row) for row in rows]


@router.delete("/library/{item_id:uuid}")
async def deactivate_library_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await LibraryService(session).deactivate(item_id))


@router.post(
    "/products/{product_id:uuid}/library/{item_id:uuid}",
    status_code=201,
)
async def assign_library_item(
    product_id: uuid.UUID,
    item_id: uuid.UUID,
    order: int = Query(default=0, ge=0, le=MAX_DB_INTEGER),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await LibraryService(session).assign(product_id, item_id, order))


@router.get("/library/{item_id:uuid}/usage")
async def library_usage(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await LibraryService(session).usage(item_id)
