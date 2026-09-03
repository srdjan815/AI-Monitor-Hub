from __future__ import annotations

import uuid

from app.modules.product_content.models import ProductContent
from app.modules.product_content.repositories import ContentRepository


class ProductContentRepository(ContentRepository):
    """Compatibility name for the canonical Product Content repository."""

    async def history(self, content_key: uuid.UUID) -> list[ProductContent]:
        return await self.content_history(content_key)


__all__ = ["ProductContentRepository"]
