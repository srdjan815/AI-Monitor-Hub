from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.catalog.attribute_models import (
    AttributeNormalizationRule,
    AttributeOption,
    AttributeOptionAlias,
)

from app.modules.catalog.attribute_repository_support import (
    ProductAttributeRepositorySupport,
)


class AttributeOptionRepository(ProductAttributeRepositorySupport):
    async def list_options(
        self,
        attribute_id: uuid.UUID,
        active_only: bool = True,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeOption]:
        query = (
            select(AttributeOption)
            .options(selectinload(AttributeOption.aliases))
            .where(AttributeOption.attribute_definition_id == attribute_id)
        )
        if active_only:
            query = query.where(AttributeOption.is_active.is_(True))
        query = query.order_by(
            AttributeOption.sort_order,
            AttributeOption.canonical_value,
            AttributeOption.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def list_rules(
        self,
        attribute_id: uuid.UUID,
        active_only: bool = True,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeNormalizationRule]:
        query = select(AttributeNormalizationRule).where(
            AttributeNormalizationRule.attribute_definition_id == attribute_id
        )
        if active_only:
            query = query.where(AttributeNormalizationRule.is_active.is_(True))
        query = query.order_by(
            AttributeNormalizationRule.priority,
            AttributeNormalizationRule.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def alias_by_normalized(
        self, attribute_id: uuid.UUID, normalized_alias: str
    ) -> AttributeOptionAlias | None:
        result = await self.session.scalars(
            select(AttributeOptionAlias).where(
                AttributeOptionAlias.attribute_definition_id == attribute_id,
                AttributeOptionAlias.normalized_alias == normalized_alias,
            )
        )
        return result.first()


__all__ = ["AttributeOptionRepository"]
