from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CONTENT_RAW_PREVIEW, require_current_permission
from app.db.session import get_db
from app.modules.product_content.query_services import PreviewService
from app.modules.product_content.schemas import PreviewRequest

router = APIRouter()


@router.get("/products/{product_id:uuid}/variables")
async def resolve_variables(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await PreviewService(session).variables(product_id)


@router.post("/products/{product_id:uuid}/templates/{template_id:uuid}/preview")
async def preview_template(
    product_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: PreviewRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if payload.trusted_raw:
        require_current_permission(CONTENT_RAW_PREVIEW)
    return await PreviewService(session).render(product_id, template_id, payload)
