from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.attribute_models import ProductAttributeValue
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.platform_service import AttributePlatformService
from app.modules.catalog.schemas.product_attributes import (
    BulkValueWrite,
    ProductAttributeValueWrite,
)


class AttributeMutationCoordinator:
    """Explicit transaction coordinator for base and derived attribute writes."""

    def __init__(self, session: AsyncSession) -> None:
        self.platform = AttributePlatformService(session)
        self.attributes = ProductAttributeService(
            session,
            recalculate=self._recalculate,
        )

    async def _recalculate(
        self, product_id: uuid.UUID, changed_attribute_id: uuid.UUID
    ) -> None:
        await self.platform.recalculate_product(
            product_id,
            changed_attribute_id=changed_attribute_id,
            commit=False,
        )

    async def write_value(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        payload: ProductAttributeValueWrite,
    ) -> ProductAttributeValue:
        return await self.attributes.write_value(
            product_id,
            attribute_id,
            payload,
        )

    async def bulk_write(
        self,
        product_id: uuid.UUID,
        payload: BulkValueWrite,
    ) -> list[ProductAttributeValue]:
        return await self.attributes.bulk_write(product_id, payload)
