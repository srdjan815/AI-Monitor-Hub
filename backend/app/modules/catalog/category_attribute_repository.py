from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import (
    AttributeDefinition,
    CategoryAttribute,
)

from app.modules.catalog.attribute_repository_support import (
    ProductAttributeRepositorySupport,
)


class CategoryAttributeRepository(ProductAttributeRepositorySupport):
    async def list_assignments(
        self,
        category_ids: list[uuid.UUID],
        active_only: bool = True,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[CategoryAttribute]:
        query = (
            select(CategoryAttribute)
            .join(CategoryAttribute.attribute)
            .options(selectinload(CategoryAttribute.attribute))
            .where(CategoryAttribute.category_id.in_(category_ids))
        )
        if active_only:
            query = query.where(
                CategoryAttribute.is_active.is_(True),
                AttributeDefinition.is_active.is_(True),
            )
        query = query.order_by(
            CategoryAttribute.position,
            CategoryAttribute.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def list_page_assignments(
        self,
        category_ids: list[uuid.UUID],
        attribute_ids: list[uuid.UUID],
    ) -> list[CategoryAttribute]:
        if not category_ids or not attribute_ids:
            return []
        result = await self.session.scalars(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id.in_(category_ids),
                CategoryAttribute.attribute_id.in_(attribute_ids),
                CategoryAttribute.is_active.is_(True),
            )
        )
        return list(result.all())

    async def assignment(
        self, category_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> CategoryAttribute | None:
        result = await self.session.scalars(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id == category_id,
                CategoryAttribute.id == assignment_id,
            )
        )
        return result.first()

    async def assignment_for_attribute(
        self, category_id: uuid.UUID, attribute_id: uuid.UUID
    ) -> CategoryAttribute | None:
        result = await self.session.scalars(
            select(CategoryAttribute).where(
                CategoryAttribute.category_id == category_id,
                CategoryAttribute.attribute_id == attribute_id,
            )
        )
        return result.first()

    async def has_active_assignment(
        self,
        category_ids: list[uuid.UUID],
        attribute_id: uuid.UUID,
    ) -> bool:
        if not category_ids:
            return False
        return bool(
            await self.session.scalar(
                select(
                    select(CategoryAttribute.id)
                    .where(
                        CategoryAttribute.category_id.in_(category_ids),
                        CategoryAttribute.attribute_id == attribute_id,
                        CategoryAttribute.is_active.is_(True),
                    )
                    .exists()
                )
            )
        )


__all__ = ["CategoryAttributeRepository"]
