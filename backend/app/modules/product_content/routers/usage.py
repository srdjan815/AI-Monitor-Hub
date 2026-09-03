from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.product_content.services import ReferenceService

router = APIRouter()


@router.get("/seo/{entity_id:uuid}/usage")
async def seo_usage(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ReferenceService(session).usage("seo", entity_id)


@router.get("/landing-pages/{entity_id:uuid}/usage")
async def landing_usage(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ReferenceService(session).usage("landing", entity_id)


@router.get("/documents/{entity_id:uuid}/usage")
async def document_usage(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ReferenceService(session).usage("document", entity_id)


@router.get("/videos/{entity_id:uuid}/usage")
async def video_usage(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ReferenceService(session).usage("video", entity_id)
