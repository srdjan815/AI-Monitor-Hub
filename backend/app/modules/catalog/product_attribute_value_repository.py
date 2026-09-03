from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.modules.catalog.attribute_models import (
    AttributeChangeEvent,
    ProductAttributeValue,
    ProductAttributeValueHistory,
)

from app.modules.catalog.attribute_repository_support import (
    ProductAttributeRepositorySupport,
)


class ProductAttributeValueRepository(ProductAttributeRepositorySupport):
    async def values(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID | None = None,
        active_only: bool = True,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[ProductAttributeValue]:
        query = select(ProductAttributeValue).where(
            ProductAttributeValue.product_id == product_id
        )
        if attribute_id:
            query = query.where(
                ProductAttributeValue.attribute_definition_id == attribute_id
            )
        if active_only:
            query = query.where(ProductAttributeValue.is_active.is_(True))
        query = query.order_by(
            ProductAttributeValue.attribute_definition_id,
            ProductAttributeValue.position,
            ProductAttributeValue.created_at,
            ProductAttributeValue.id,
        ).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def values_for_attributes(
        self,
        product_id: uuid.UUID,
        attribute_ids: list[uuid.UUID],
    ) -> list[ProductAttributeValue]:
        if not attribute_ids:
            return []
        result = await self.session.scalars(
            select(ProductAttributeValue)
            .where(
                ProductAttributeValue.product_id == product_id,
                ProductAttributeValue.attribute_definition_id.in_(attribute_ids),
                ProductAttributeValue.is_active.is_(True),
            )
            .order_by(
                ProductAttributeValue.attribute_definition_id,
                ProductAttributeValue.position,
                ProductAttributeValue.created_at,
                ProductAttributeValue.id,
            )
        )
        return list(result.all())

    async def value(
        self, product_id: uuid.UUID, attribute_id: uuid.UUID, value_key: str
    ) -> ProductAttributeValue | None:
        result = await self.session.scalars(
            select(ProductAttributeValue).where(
                ProductAttributeValue.product_id == product_id,
                ProductAttributeValue.attribute_definition_id == attribute_id,
                ProductAttributeValue.value_key == value_key,
                ProductAttributeValue.is_active.is_(True),
            )
        )
        return result.first()

    async def history(
        self,
        product_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 100,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[ProductAttributeValueHistory]:
        query = select(ProductAttributeValueHistory).where(
            ProductAttributeValueHistory.product_id == product_id
        )
        if snapshot_at is not None:
            query = query.where(ProductAttributeValueHistory.occurred_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    ProductAttributeValueHistory.occurred_at > after_at,
                    and_(
                        ProductAttributeValueHistory.occurred_at == after_at,
                        ProductAttributeValueHistory.id > after_id,
                    ),
                )
            )
        result = await self.session.execute(
            query.order_by(
                ProductAttributeValueHistory.occurred_at,
                ProductAttributeValueHistory.id,
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def changes(
        self,
        *,
        cursor: int,
        limit: int,
        product_id: uuid.UUID | None,
        entity_type: str | None,
    ) -> list[AttributeChangeEvent]:
        query = select(AttributeChangeEvent).where(AttributeChangeEvent.cursor > cursor)
        if product_id:
            query = query.where(AttributeChangeEvent.product_id == product_id)
        if entity_type:
            query = query.where(AttributeChangeEvent.entity_type == entity_type)
        result = await self.session.execute(
            query.order_by(AttributeChangeEvent.cursor).limit(limit)
        )
        return list(result.scalars())

    async def latest_cursor(self) -> int:
        return int(
            await self.session.scalar(select(func.max(AttributeChangeEvent.cursor)))
            or 0
        )


__all__ = ["ProductAttributeValueRepository"]
