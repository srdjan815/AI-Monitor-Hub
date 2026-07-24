from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.product_content.constants import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)
from app.modules.product_content.models import Language
from app.modules.product_content.schemas import (
    LanguageCreate,
    LanguageRead,
    LanguageUpdate,
)
from app.modules.product_content.services import ConfigurationService

router = APIRouter()


@router.post("/languages", response_model=LanguageRead, status_code=201)
async def create_language(
    payload: LanguageCreate,
    session: AsyncSession = Depends(get_db),
) -> Language:
    return await ConfigurationService(session).create_language(payload)


@router.get("/languages", response_model=list[LanguageRead])
async def list_languages(
    active_only: bool = True,
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> list[Language]:
    return await ConfigurationService(session).list_languages(
        active_only,
        offset=offset,
        limit=limit,
    )


@router.get("/languages/{language_id:uuid}", response_model=LanguageRead)
async def get_language(
    language_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Language:
    return await ConfigurationService(session).get_language(language_id)


@router.patch("/languages/{language_id:uuid}", response_model=LanguageRead)
async def update_language(
    language_id: uuid.UUID,
    payload: LanguageUpdate,
    session: AsyncSession = Depends(get_db),
) -> Language:
    return await ConfigurationService(session).update_language(language_id, payload)


@router.post("/languages/{language_id:uuid}/activate", response_model=LanguageRead)
async def activate_language(
    language_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Language:
    return await ConfigurationService(session).set_language_active(language_id, True)


@router.delete("/languages/{language_id:uuid}", response_model=LanguageRead)
async def deactivate_language(
    language_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Language:
    return await ConfigurationService(session).set_language_active(language_id, False)
