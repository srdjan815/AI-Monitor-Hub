from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.modules.catalog.attribute_models import ProductAttributeValue
from app.modules.catalog.models import (
    AttributeDefinition,
    CategoryAttribute,
    Product,
)
from app.modules.catalog.platform_models import (
    AttributeFamilyItem,
    AttributeTemplateItem,
)
from app.modules.catalog.platform_service_support import _PlatformServiceSupport


class AttributeUsageService(_PlatformServiceSupport):
    """Owns aggregate usage and data-quality counts for one attribute."""

    async def usage(self, attribute_id: uuid.UUID) -> dict[str, int]:
        definition = await self._required(
            AttributeDefinition,
            attribute_id,
            "Attribute",
        )
        products = int(
            await self.session.scalar(
                select(
                    func.count(func.distinct(ProductAttributeValue.product_id))
                ).where(
                    ProductAttributeValue.attribute_definition_id == attribute_id,
                    ProductAttributeValue.is_active.is_(True),
                )
            )
            or 0
        )
        total_products = int(
            await self.session.scalar(select(func.count(Product.id))) or 0
        )
        return {
            "products_using": products,
            "categories_using": int(
                await self.session.scalar(
                    select(func.count(CategoryAttribute.id)).where(
                        CategoryAttribute.attribute_id == attribute_id,
                        CategoryAttribute.is_active.is_(True),
                    )
                )
                or 0
            ),
            "templates_using": int(
                await self.session.scalar(
                    select(func.count(AttributeTemplateItem.id)).where(
                        AttributeTemplateItem.attribute_definition_id == attribute_id,
                        AttributeTemplateItem.is_active.is_(True),
                    )
                )
                or 0
            ),
            "families_using": int(
                await self.session.scalar(
                    select(func.count(AttributeFamilyItem.id)).where(
                        AttributeFamilyItem.attribute_definition_id == attribute_id,
                        AttributeFamilyItem.is_active.is_(True),
                    )
                )
                or 0
            ),
            "values": int(
                await self.session.scalar(
                    select(func.count(ProductAttributeValue.id)).where(
                        ProductAttributeValue.attribute_definition_id == attribute_id,
                        ProductAttributeValue.is_active.is_(True),
                    )
                )
                or 0
            ),
            "approved_values": int(
                await self.session.scalar(
                    select(func.count(ProductAttributeValue.id)).where(
                        ProductAttributeValue.attribute_definition_id == attribute_id,
                        ProductAttributeValue.approval_status == "APPROVED",
                        ProductAttributeValue.is_active.is_(True),
                    )
                )
                or 0
            ),
            "missing_values": (
                max(total_products - products, 0) if definition.is_required else 0
            ),
            "invalid_values": int(
                await self.session.scalar(
                    select(func.count(ProductAttributeValue.id)).where(
                        ProductAttributeValue.attribute_definition_id == attribute_id,
                        ProductAttributeValue.validation_status == "INVALID",
                        ProductAttributeValue.is_active.is_(True),
                    )
                )
                or 0
            ),
        }
