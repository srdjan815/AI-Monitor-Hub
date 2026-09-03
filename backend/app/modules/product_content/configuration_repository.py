from __future__ import annotations

import uuid

from sqlalchemy import select

from app.modules.product_content.models import (
    ContentType,
    Language,
)
from app.modules.product_content.repository_support import ContentRepositorySupport


class ConfigurationRepository(ContentRepositorySupport):
    async def languages(
        self,
        active_only: bool,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Language]:
        query = select(Language)
        if active_only:
            query = query.where(Language.is_active.is_(True))
        return await self.all(
            query.order_by(Language.name, Language.id).offset(offset).limit(limit)
        )

    async def default_languages(
        self,
        exclude_id: uuid.UUID | None = None,
    ) -> list[Language]:
        query = select(Language).where(Language.is_default.is_(True))
        if exclude_id:
            query = query.where(Language.id != exclude_id)
        return await self.all(query)

    async def language_by_code(self, code: str) -> Language | None:
        return await self.one(select(Language).where(Language.code == code))

    async def content_types(
        self,
        active_only: bool,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ContentType]:
        query = select(ContentType)
        if active_only:
            query = query.where(ContentType.is_active.is_(True))
        return await self.all(
            query.order_by(
                ContentType.sort_order,
                ContentType.name,
                ContentType.id,
            )
            .offset(offset)
            .limit(limit)
        )

    async def content_type_by_slug(self, slug: str) -> ContentType | None:
        return await self.one(select(ContentType).where(ContentType.slug == slug))


__all__ = ["ConfigurationRepository"]
