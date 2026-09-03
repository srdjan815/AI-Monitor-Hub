from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_CURSOR_CHARS
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.core.api_pagination import revision_page
from app.modules.product_content.schemas import PromptWrite
from app.modules.product_content.services import PromptService, serialize

router = APIRouter()


@router.post("/types/{type_id:uuid}/prompts", status_code=201)
async def create_prompt(
    type_id: uuid.UUID,
    payload: PromptWrite,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await PromptService(session).create(type_id, payload))


@router.get("/types/{type_id:uuid}/prompts")
async def prompt_history(
    type_id: uuid.UUID,
    response: Response,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    service = PromptService(session)
    rows = await revision_page(
        response,
        cursor=cursor,
        resource="content.prompt_history",
        filters={
            "type_id": str(type_id),
            "limit": limit,
            "order": "version_desc",
        },
        limit=limit,
        loader=lambda page_limit, after, snapshot: service.history_page(
            type_id,
            limit=page_limit,
            after_revision=after,
            snapshot_revision=snapshot,
        ),
        revision_of=lambda row: row.version,
    )
    return [serialize(row) for row in rows]


@router.post("/prompts/{prompt_id:uuid}/activate")
async def activate_prompt(
    prompt_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return serialize(await PromptService(session).activate(prompt_id))
