from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product


class ProductRepository:
    """Product persistence, uniqueness lookups, and list pagination."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_products(
        self,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Product], int]:
        filters: list[ColumnElement[bool]] = []

        if active_only:
            filters.append(Product.is_active.is_(True))

        if snapshot_at is not None:
            filters.append(Product.created_at <= snapshot_at)

        count_query = select(func.count(Product.id)).where(*filters)
        page_filters = list(filters)

        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    Product.created_at < after_at,
                    and_(
                        Product.created_at == after_at,
                        Product.id < after_id,
                    ),
                )
            )

        query = select(Product).where(*page_filters)
        if snapshot_at is None and after is None:
            query = query.order_by(
                Product.name,
                Product.id,
            )
        else:
            query = query.order_by(
                Product.created_at.desc(),
                Product.id.desc(),
            )

        rows = await self.session.execute(query.limit(limit).offset(offset))

        total = await self.session.scalar(count_query)

        return (
            list(rows.scalars().all()),
            int(total or 0),
        )

    async def get_product(
        self,
        product_id: uuid.UUID,
    ) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_product_by_code(
        self,
        code: str,
    ) -> Product | None:
        result = await self.session.execute(select(Product).where(Product.code == code))
        return result.scalar_one_or_none()

    async def get_product_by_sku(
        self,
        sku: str,
    ) -> Product | None:
        result = await self.session.execute(select(Product).where(Product.sku == sku))
        return result.scalar_one_or_none()

    async def get_product_by_ean(
        self,
        ean: str,
    ) -> Product | None:
        result = await self.session.execute(select(Product).where(Product.ean == ean))
        return result.scalar_one_or_none()

    async def create_product(
        self,
        product: Product,
    ) -> Product:
        self.session.add(product)
        await self.session.flush()
        return product

    async def update_product(
        self,
        product: Product,
        changes: dict[str, object],
    ) -> Product:
        for field, value in changes.items():
            setattr(product, field, value)

        await self.session.flush()
        return product

    async def deactivate_product(
        self,
        product: Product,
    ) -> Product:
        product.is_active = False
        product.version += 1
        await self.session.flush()
        return product


__all__ = ["ProductRepository"]
