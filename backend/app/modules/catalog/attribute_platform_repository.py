from __future__ import annotations

import uuid

from sqlalchemy import select

from app.modules.catalog.platform_models import (
    AttributeDependency,
    AttributeFormula,
    AttributePromptVersion,
)

from app.modules.catalog.attribute_repository_support import (
    ProductAttributeRepositorySupport,
)


class AttributePlatformRepository(ProductAttributeRepositorySupport):
    async def list_formulas(
        self,
        *,
        kind: str | None,
        active_only: bool,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeFormula]:
        query = select(AttributeFormula)
        if kind:
            query = query.where(AttributeFormula.formula_kind == kind)
        if active_only:
            query = query.where(AttributeFormula.is_active.is_(True))
        query = query.order_by(
            AttributeFormula.created_at,
            AttributeFormula.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        rows = await self.session.execute(query)
        return list(rows.scalars())

    async def list_dependencies(
        self,
        *,
        active_only: bool,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeDependency]:
        query = select(AttributeDependency)
        if active_only:
            query = query.where(AttributeDependency.is_active.is_(True))
        query = query.order_by(
            AttributeDependency.created_at,
            AttributeDependency.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        rows = await self.session.execute(query)
        return list(rows.scalars())

    async def list_prompt_versions(
        self,
        attribute_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributePromptVersion]:
        query = (
            select(AttributePromptVersion)
            .where(AttributePromptVersion.attribute_definition_id == attribute_id)
            .order_by(
                AttributePromptVersion.version_number.desc(),
                AttributePromptVersion.id,
            )
        )
        query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        rows = await self.session.execute(query)
        return list(rows.scalars())


__all__ = ["AttributePlatformRepository"]
