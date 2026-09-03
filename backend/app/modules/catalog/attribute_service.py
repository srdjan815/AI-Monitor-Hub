from __future__ import annotations

from app.modules.catalog.attribute_definition_service import (
    AttributeDefinitionService,
)
from app.modules.catalog.attribute_option_service import AttributeOptionService
from app.modules.catalog.category_attribute_service import (
    CategoryAttributeService,
)
from app.modules.catalog.product_attribute_value_service import (
    ProductAttributeValueService,
)


class ProductAttributeService(
    AttributeDefinitionService,
    CategoryAttributeService,
    AttributeOptionService,
    ProductAttributeValueService,
):
    """Backward-compatible façade over cohesive attribute services."""


__all__ = ["ProductAttributeService"]
